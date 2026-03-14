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
from ..utils.decorators import admin_required

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
