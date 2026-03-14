"""Rutas de integración con Tienda Nube."""

import logging
import secrets

import requests as http_requests
from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..models import TiendaNubeCredencial
from ..services.tiendanube_service import (
    desvincular_producto,
    listar_productos_disponibles,
    listar_productos_vinculados,
    vincular_producto,
)
from ..tasks.tiendanube_tasks import encolar_sync_completo, encolar_sync_masivo
from ..utils.decorators import admin_required
from ..utils.helpers import es_peticion_htmx, respuesta_htmx_redirect

logger = logging.getLogger(__name__)

bp = Blueprint('tiendanube', __name__, url_prefix='/tiendanube')

TIENDANUBE_AUTH_URL = 'https://www.tiendanube.com/apps/{app_id}/authorize'
TIENDANUBE_TOKEN_URL = 'https://www.tiendanube.com/apps/authorize/token'


@bp.route('/configuracion')
@login_required
@admin_required
def configuracion():
    """Configuración de la integración con Tienda Nube."""
    credencial = TiendaNubeCredencial.query.filter_by(
        empresa_id=current_user.empresa_id,
    ).first()

    return render_template('tiendanube/configuracion.html', credencial=credencial)


@bp.route('/guardar-credenciales', methods=['POST'])
@login_required
@admin_required
def guardar_credenciales():
    """Guarda o actualiza las credenciales de la app de Tienda Nube."""
    tn_app_id = request.form.get('tn_app_id', '').strip()
    tn_app_secret = request.form.get('tn_app_secret', '').strip()

    if not tn_app_id or not tn_app_secret:
        flash('Debes completar el App ID y el App Secret.', 'danger')
        return redirect(url_for('tiendanube.configuracion'))

    credencial = TiendaNubeCredencial.query.filter_by(
        empresa_id=current_user.empresa_id,
    ).first()

    if credencial:
        credencial.tn_app_id = tn_app_id
        credencial.tn_app_secret = tn_app_secret
    else:
        credencial = TiendaNubeCredencial(
            empresa_id=current_user.empresa_id,
            tn_app_id=tn_app_id,
            tn_app_secret=tn_app_secret,
        )
        db.session.add(credencial)

    db.session.commit()
    flash('Credenciales guardadas correctamente.', 'success')
    return redirect(url_for('tiendanube.configuracion'))


@bp.route('/conectar')
@login_required
@admin_required
def conectar():
    """Inicia el flujo OAuth con Tienda Nube."""
    credencial = TiendaNubeCredencial.query.filter_by(
        empresa_id=current_user.empresa_id,
    ).first()

    if not credencial or not credencial.tn_app_id:
        flash(
            'Primero debés guardar las credenciales de la app.',
            'danger',
        )
        return redirect(url_for('tiendanube.configuracion'))

    state = secrets.token_urlsafe(32)
    session['tn_oauth_state'] = state

    auth_url = TIENDANUBE_AUTH_URL.format(app_id=credencial.tn_app_id)
    url_completa = f'{auth_url}?state={state}'

    return redirect(url_completa)


@bp.route('/callback')
@login_required
def callback():
    """Callback de OAuth de Tienda Nube."""
    code = request.args.get('code')
    state = request.args.get('state')

    # Validar state contra CSRF
    estado_esperado = session.pop('tn_oauth_state', None)
    if not state or state != estado_esperado:
        flash('Error de seguridad en la autenticación.', 'danger')
        return redirect(url_for('tiendanube.configuracion'))

    credencial = TiendaNubeCredencial.query.filter_by(
        empresa_id=current_user.empresa_id,
    ).first()

    if not credencial:
        flash('No se encontraron credenciales configuradas.', 'danger')
        return redirect(url_for('tiendanube.configuracion'))

    try:
        respuesta = http_requests.post(
            TIENDANUBE_TOKEN_URL,
            json={
                'client_id': credencial.tn_app_id,
                'client_secret': credencial.tn_app_secret,
                'grant_type': 'authorization_code',
                'code': code,
            },
            timeout=30,
        )
        respuesta.raise_for_status()
        datos = respuesta.json()

        credencial.access_token = datos.get('access_token')
        credencial.tienda_id_externo = str(datos.get('user_id', ''))
        credencial.usuario_id_externo = str(datos.get('user_id', ''))
        credencial.token_type = datos.get('token_type', 'bearer')
        credencial.scope = datos.get('scope', '')
        credencial.activo = True
        db.session.commit()

        flash('Tienda Nube conectada exitosamente.', 'success')

    except http_requests.RequestException:
        logger.exception('Error al intercambiar código OAuth con Tienda Nube')
        flash(
            'Error al conectar con Tienda Nube. Intentá nuevamente.',
            'danger',
        )

    return redirect(url_for('tiendanube.configuracion'))


@bp.route('/desconectar', methods=['POST'])
@login_required
@admin_required
def desconectar():
    """Desconecta la integración con Tienda Nube."""
    credencial = TiendaNubeCredencial.query.filter_by(
        empresa_id=current_user.empresa_id,
    ).first()

    if credencial:
        credencial.access_token = None
        credencial.activo = False
        db.session.commit()

    flash('Tienda Nube desconectada.', 'info')
    return redirect(url_for('tiendanube.configuracion'))


# -------------------------------------------------------------------
# Mapeo de productos
# -------------------------------------------------------------------


def _credencial_activa_o_redirigir():
    """Verifica que la empresa tenga una credencial TN activa.

    Returns:
        TiendaNubeCredencial si está activa, o una respuesta de redirección.
    """
    credencial = TiendaNubeCredencial.query.filter_by(
        empresa_id=current_user.empresa_id,
        activo=True,
    ).first()

    if not credencial:
        flash(
            'Primero debés conectar tu tienda de Tienda Nube.',
            'warning',
        )
        return None

    return credencial


def _render_productos(vinculados, disponibles):
    """Renderiza la página o partial de productos según el tipo de request."""
    if es_peticion_htmx():
        return render_template(
            'tiendanube/_tabla_productos.html',
            vinculados=vinculados,
            disponibles=disponibles,
        )

    return render_template(
        'tiendanube/productos.html',
        vinculados=vinculados,
        disponibles=disponibles,
    )


@bp.route('/productos')
@login_required
@admin_required
def productos():
    """Página de mapeo de productos con Tienda Nube."""
    credencial = _credencial_activa_o_redirigir()
    if not credencial:
        return redirect(url_for('tiendanube.configuracion'))

    vinculados = listar_productos_vinculados(current_user.empresa_id)
    disponibles = listar_productos_disponibles(current_user.empresa_id)

    return render_template(
        'tiendanube/productos.html',
        vinculados=vinculados,
        disponibles=disponibles,
    )


@bp.route('/productos/vincular', methods=['POST'])
@login_required
@admin_required
def vincular():
    """Vincula un producto local con Tienda Nube."""
    producto_id = request.form.get('producto_id', type=int)

    if not producto_id:
        flash('No se indicó el producto a vincular.', 'danger')
        if es_peticion_htmx():
            return respuesta_htmx_redirect(url_for('tiendanube.productos'))
        return redirect(url_for('tiendanube.productos'))

    try:
        vincular_producto(producto_id, current_user.empresa_id)
        flash('Producto vinculado a Tienda Nube correctamente.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    if es_peticion_htmx():
        vinculados = listar_productos_vinculados(current_user.empresa_id)
        disponibles = listar_productos_disponibles(current_user.empresa_id)
        return _render_productos(vinculados, disponibles)

    return redirect(url_for('tiendanube.productos'))


@bp.route('/productos/desvincular', methods=['POST'])
@login_required
@admin_required
def desvincular():
    """Desvincula un producto de Tienda Nube."""
    producto_id = request.form.get('producto_id', type=int)

    if not producto_id:
        flash('No se indicó el producto a desvincular.', 'danger')
        if es_peticion_htmx():
            return respuesta_htmx_redirect(url_for('tiendanube.productos'))
        return redirect(url_for('tiendanube.productos'))

    try:
        desvincular_producto(producto_id, current_user.empresa_id)
        flash('Producto desvinculado de Tienda Nube.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    if es_peticion_htmx():
        vinculados = listar_productos_vinculados(current_user.empresa_id)
        disponibles = listar_productos_disponibles(current_user.empresa_id)
        return _render_productos(vinculados, disponibles)

    return redirect(url_for('tiendanube.productos'))


@bp.route('/productos/sincronizar/<int:producto_id>', methods=['POST'])
@login_required
@admin_required
def sincronizar_producto(producto_id):
    """Encola la sincronización completa de un producto."""
    try:
        encolar_sync_completo(producto_id, current_user.empresa_id)
        flash('Sincronización en cola.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    if es_peticion_htmx():
        return respuesta_htmx_redirect(url_for('tiendanube.productos'))
    return redirect(url_for('tiendanube.productos'))


@bp.route('/productos/sincronizar-todo', methods=['POST'])
@login_required
@admin_required
def sincronizar_todo():
    """Encola la sincronización masiva de todos los productos vinculados."""
    try:
        encolar_sync_masivo(current_user.empresa_id)
        flash('Sincronización masiva en cola.', 'success')
    except ValueError as e:
        flash(str(e), 'danger')

    if es_peticion_htmx():
        return respuesta_htmx_redirect(url_for('tiendanube.productos'))
    return redirect(url_for('tiendanube.productos'))
