"""Rutas de facturación."""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.configuracion_forms import ConfiguracionArcaForm
from ..forms.facturador_forms import FacturadorForm
from ..models import Factura, Venta
from ..models.facturador import Facturador
from ..services.arca_constants import CONDICION_IVA
from ..services.arca_exceptions import ArcaAuthError, ArcaNetworkError, ArcaValidationError
from ..services.facturacion_service import FacturacionService
from ..services.padron_service import PadronService
from ..utils.certificado import extraer_info_certificado
from ..utils.crypto import encriptar
from ..utils.decorators import admin_required, empresa_aprobada_required
from ..utils.helpers import paginar_query

logger = logging.getLogger(__name__)

bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')


def _normalizar_cuit(cuit):
    """Normaliza CUIT al formato XX-XXXXXXXX-X."""
    if not cuit:
        return None

    digitos = ''.join(ch for ch in str(cuit) if ch.isdigit())
    if len(digitos) != 11:
        raise ValueError('El CUIT debe contener 11 dígitos.')

    return f'{digitos[:2]}-{digitos[2:10]}-{digitos[10:]}'


def _normalizar_ambiente_arca(ambiente):
    """Normaliza alias históricos del ambiente ARCA."""
    if ambiente == 'produccion':
        return 'production'
    return ambiente


# =============================================================================
# Facturas — listado y detalle
# =============================================================================


@bp.route('/')
@login_required
@empresa_aprobada_required
def index():
    """Listado de facturas electrónicas emitidas."""
    page = request.args.get('page', 1, type=int)

    facturas = paginar_query(
        Factura.query_empresa().order_by(Factura.fecha_emision.desc(), Factura.id.desc()),
        page,
    )
    return render_template('facturacion/index.html', facturas=facturas)


@bp.route('/<int:id>')
@login_required
@empresa_aprobada_required
def detalle(id):
    """Detalle de una factura electrónica."""
    factura = Factura.get_o_404(id)
    return render_template('facturacion/detalle.html', factura=factura)


# =============================================================================
# Emisión de facturas
# =============================================================================


@bp.route('/emitir/<int:venta_id>', methods=['POST'])
@login_required
@empresa_aprobada_required
def emitir_desde_venta(venta_id):
    """Emite una factura electrónica para una venta."""
    venta = Venta.get_o_404(venta_id)
    facturador_id = request.form.get('facturador_id', type=int)

    try:
        factura = FacturacionService().emitir_factura_desde_venta(
            venta_id=venta.id,
            empresa_id=current_user.empresa_id,
            facturador_id=facturador_id,
        )
    except ArcaValidationError as exc:
        flash(f'No se pudo emitir la factura: {exc.mensaje}', 'danger')
        return redirect(url_for('ventas.detalle', id=venta.id))
    except (ArcaAuthError, ArcaNetworkError) as exc:
        flash(f'Error de conexión con ARCA: {exc.mensaje}', 'warning')
        return redirect(url_for('ventas.detalle', id=venta.id))
    except Exception:
        logger.exception('Error al emitir factura para venta %s', venta_id)
        flash('Error inesperado al emitir la factura electrónica.', 'danger')
        return redirect(url_for('ventas.detalle', id=venta.id))

    if factura.estado == 'autorizada':
        flash(f'Factura emitida correctamente. CAE: {factura.cae}', 'success')
    elif factura.estado == 'rechazada':
        flash(
            f'ARCA rechazó la factura. {factura.error_mensaje or "Revisá el detalle."}',
            'warning',
        )
    else:
        flash('Factura registrada con estado pendiente de confirmación.', 'info')

    return redirect(url_for('facturacion.detalle', id=factura.id))


@bp.route('/<int:id>/reintentar', methods=['POST'])
@login_required
@empresa_aprobada_required
def reintentar_emision(id):
    """Reintenta emisión de una factura en estado error/rechazada."""
    factura = Factura.get_o_404(id)

    if factura.estado not in ('rechazada', 'error'):
        flash('Solo se pueden reintentar facturas rechazadas o con error.', 'info')
        return redirect(url_for('facturacion.detalle', id=factura.id))

    if not factura.venta_id:
        flash('No es posible reintentar esta factura porque no tiene venta asociada.', 'danger')
        return redirect(url_for('facturacion.detalle', id=factura.id))

    try:
        nueva_factura = FacturacionService().emitir_factura_desde_venta(
            venta_id=factura.venta_id,
            empresa_id=current_user.empresa_id,
            facturador_id=factura.facturador_id,
            tipo_comprobante=factura.tipo_comprobante,
            concepto=factura.concepto,
        )
    except ArcaValidationError as exc:
        flash(f'No se pudo reintentar la factura: {exc.mensaje}', 'danger')
        return redirect(url_for('facturacion.detalle', id=factura.id))
    except (ArcaAuthError, ArcaNetworkError) as exc:
        flash(f'Error de conexión con ARCA: {exc.mensaje}', 'warning')
        return redirect(url_for('facturacion.detalle', id=factura.id))
    except Exception:
        logger.exception(
            'Error al reintentar emision de factura %s (venta %s)',
            factura.id,
            factura.venta_id,
        )
        flash('Error inesperado al reintentar la emisión.', 'danger')
        return redirect(url_for('facturacion.detalle', id=factura.id))

    if nueva_factura.estado == 'autorizada':
        flash(f'Reintento exitoso. CAE: {nueva_factura.cae}', 'success')
    elif nueva_factura.estado == 'rechazada':
        flash(
            f'ARCA volvió a rechazar la factura. {nueva_factura.error_mensaje or "Revisá el detalle."}',
            'warning',
        )
    else:
        flash('Reintento registrado con estado pendiente.', 'info')

    return redirect(url_for('facturacion.detalle', id=nueva_factura.id))


# =============================================================================
# Configuración ARCA (empresa) — retrocompatibilidad, redirige a facturadores
# =============================================================================


@bp.route('/configuracion-arca', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
@admin_required
def configuracion_arca():
    """Configuración ARCA de la empresa actual.

    Si la empresa ya tiene facturadores configurados, redirige al listado
    de facturadores.  Mantiene la página original para empresas que aún
    no migraron.
    """
    empresa = current_user.empresa

    # Si ya tiene facturadores, redirigir
    tiene_facturadores = (
        Facturador.query.filter_by(
            empresa_id=empresa.id,
        ).first()
        is not None
    )

    if tiene_facturadores:
        flash(
            'La configuración de facturación se gestiona desde Facturadores.',
            'info',
        )
        return redirect(url_for('facturacion.listar_facturadores'))

    form = ConfiguracionArcaForm()

    if form.validate_on_submit():
        try:
            empresa.cuit = _normalizar_cuit(form.cuit.data)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template(
                'facturacion/configuracion_arca.html',
                form=form,
                empresa=empresa,
            )

        empresa.condicion_iva_id = form.condicion_iva_id.data or None
        empresa.condicion_iva = (form.condicion_iva.data or '').strip() or None
        if empresa.condicion_iva_id and not empresa.condicion_iva:
            empresa.condicion_iva = dict(form.condicion_iva_id.choices).get(
                empresa.condicion_iva_id
            )

        empresa.punto_venta_arca = form.punto_venta_arca.data or None
        empresa.ambiente_arca = _normalizar_ambiente_arca(form.ambiente_arca.data)
        empresa.arca_habilitado = bool(form.arca_habilitado.data)
        empresa.inicio_actividades = form.inicio_actividades.data

        if form.certificado_arca.data and form.certificado_arca.data.filename:
            empresa.certificado_arca = encriptar(form.certificado_arca.data.read())

        if form.clave_privada_arca.data and form.clave_privada_arca.data.filename:
            empresa.clave_privada_arca = encriptar(form.clave_privada_arca.data.read())

        db.session.commit()
        flash('Configuración ARCA actualizada correctamente.', 'success')
        return redirect(url_for('facturacion.configuracion_arca'))

    if not form.is_submitted():
        form.cuit.data = empresa.cuit
        form.condicion_iva_id.data = empresa.condicion_iva_id or 0
        form.condicion_iva.data = empresa.condicion_iva
        form.punto_venta_arca.data = empresa.punto_venta_arca
        form.ambiente_arca.data = _normalizar_ambiente_arca(empresa.ambiente_arca) or 'testing'
        form.arca_habilitado.data = bool(empresa.arca_habilitado)
        form.inicio_actividades.data = empresa.inicio_actividades

    return render_template(
        'facturacion/configuracion_arca.html',
        form=form,
        empresa=empresa,
        deprecado=True,
    )


# =============================================================================
# Padrón ARCA — consulta manual
# =============================================================================


@bp.route('/padron/consultar', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def consultar_padron():
    """Consulta manual de padrón ARCA por CUIT.

    Si se provee facturador_id, usa el facturador; de lo contrario
    usa la empresa (compatibilidad).
    """
    cuit_consulta = (request.form.get('cuit') or '').strip()
    facturador_id = request.form.get('facturador_id', type=int)

    if facturador_id:
        emisor = Facturador.query.filter_by(
            id=facturador_id,
            empresa_id=current_user.empresa_id,
        ).first()
        if not emisor:
            return jsonify({'success': False, 'error': 'Facturador no encontrado.'}), 404
    else:
        emisor = current_user.empresa

    try:
        resultado = PadronService().consultar_cliente(cuit_consulta, emisor)
        if resultado.get('success'):
            return jsonify(
                {
                    'success': True,
                    'data': resultado.get('data') or {},
                }
            )

        return jsonify(
            {
                'success': False,
                'error': resultado.get('error') or 'No se pudo consultar el padrón ARCA.',
            }
        )
    except ArcaValidationError as exc:
        return jsonify({'success': False, 'error': exc.mensaje}), 400
    except ArcaAuthError as exc:
        return jsonify(
            {'success': False, 'error': f'Error de autenticación ARCA: {exc.mensaje}'}
        ), 502
    except ArcaNetworkError as exc:
        return jsonify(
            {'success': False, 'error': f'Error de conexión con ARCA: {exc.mensaje}'}
        ), 503
    except Exception:
        logger.exception('Error al consultar padron ARCA para CUIT %s', cuit_consulta)
        return jsonify(
            {'success': False, 'error': 'Error inesperado al consultar padrón ARCA.'}
        ), 500


# =============================================================================
# Facturadores — CRUD
# =============================================================================


@bp.route('/facturadores')
@login_required
@empresa_aprobada_required
@admin_required
def listar_facturadores():
    """Listado de facturadores de la empresa actual."""
    facturadores = (
        Facturador.query_empresa().order_by(Facturador.activo.desc(), Facturador.nombre.asc()).all()
    )
    return render_template('facturacion/facturadores/index.html', facturadores=facturadores)


@bp.route('/facturadores/nuevo', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
@admin_required
def crear_facturador():
    """Crear un nuevo facturador."""
    if request.method == 'POST':
        return _guardar_facturador(facturador=None)

    form = FacturadorForm()
    return render_template(
        'facturacion/facturadores/form.html',
        facturador=None,
        form=form,
        titulo='Nuevo Facturador',
    )


@bp.route('/facturadores/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
@admin_required
def editar_facturador(id):
    """Editar un facturador existente."""
    facturador = Facturador.get_o_404(id)

    if request.method == 'POST':
        return _guardar_facturador(facturador=facturador)

    form = FacturadorForm(obj=facturador)
    return render_template(
        'facturacion/facturadores/form.html',
        facturador=facturador,
        form=form,
        titulo='Editar Facturador',
    )


@bp.route('/facturadores/<int:id>/toggle', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def toggle_facturador(id):
    """Activa o desactiva un facturador."""
    facturador = Facturador.get_o_404(id)
    accion = request.form.get('accion')
    facturador.activo = accion == 'activar'
    db.session.commit()

    estado = 'activado' if facturador.activo else 'desactivado'
    flash(f'Facturador "{facturador.nombre}" {estado} correctamente.', 'success')
    return redirect(url_for('facturacion.listar_facturadores'))


@bp.route('/facturadores/<int:id>/probar-conexion', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def probar_conexion_facturador(id):
    """Prueba la conexión ARCA del facturador. Retorna JSON."""
    facturador = Facturador.get_o_404(id)

    resultado = FacturacionService().probar_conexion(facturador)
    status_code = 200 if resultado.get('success') else 400
    return jsonify(resultado), status_code


@bp.route('/facturadores/<int:id>/padron', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def consultar_padron_facturador(id):
    """Consulta el CUIT propio del facturador en el padrón ARCA."""
    facturador = Facturador.get_o_404(id)

    if not facturador.cuit:
        return jsonify({'success': False, 'error': 'El facturador no tiene CUIT configurado.'}), 400

    try:
        resultado = PadronService().consultar_cliente(facturador.cuit, facturador)
        if resultado.get('success'):
            return jsonify({'success': True, 'data': resultado.get('data') or {}})
        return jsonify(
            {
                'success': False,
                'error': resultado.get('error') or 'No se pudo consultar el padrón ARCA.',
            }
        )
    except ArcaValidationError as exc:
        return jsonify({'success': False, 'error': exc.mensaje}), 400
    except (ArcaAuthError, ArcaNetworkError) as exc:
        return jsonify({'success': False, 'error': exc.mensaje}), 502
    except Exception:
        logger.exception('Error al consultar padron del facturador %s', id)
        return jsonify({'success': False, 'error': 'Error inesperado al consultar padrón.'}), 500


# =============================================================================
# Helpers internos para facturadores
# =============================================================================


def _guardar_facturador(facturador=None):
    """Crea o actualiza un facturador usando WTForms con validación y CSRF."""
    es_nuevo = facturador is None

    if es_nuevo:
        facturador = Facturador(empresa_id=current_user.empresa_id)

    form = FacturadorForm(obj=facturador if not es_nuevo else None)
    titulo = 'Nuevo Facturador' if es_nuevo else 'Editar Facturador'

    if not form.validate_on_submit():
        return render_template(
            'facturacion/facturadores/form.html',
            facturador=facturador,
            form=form,
            titulo=titulo,
        )

    # Campos de texto desde el formulario validado
    facturador.nombre = form.nombre.data.strip()
    facturador.razon_social = form.razon_social.data.strip()
    facturador.domicilio_fiscal = (form.domicilio_fiscal.data or '').strip() or None
    facturador.numero_iibb = (form.numero_iibb.data or '').strip() or None
    facturador.email_fiscal = (form.email_fiscal.data or '').strip() or None

    # CUIT — normalizar formato
    try:
        facturador.cuit = _normalizar_cuit(form.cuit.data)
    except ValueError as exc:
        form.cuit.errors.append(str(exc))
        return render_template(
            'facturacion/facturadores/form.html',
            facturador=facturador,
            form=form,
            titulo=titulo,
        )

    # Condición IVA — id y texto descriptivo
    facturador.condicion_iva_id = form.condicion_iva_id.data
    facturador.condicion_iva = CONDICION_IVA.get(int(form.condicion_iva_id.data), '')

    # Punto de venta
    facturador.punto_venta = form.punto_venta.data

    # Ambiente
    facturador.ambiente = _normalizar_ambiente_arca(form.ambiente.data or 'testing')

    # Habilitado
    facturador.habilitado = bool(form.habilitado.data)

    # Inicio de actividades
    facturador.inicio_actividades = form.inicio_actividades.data

    # Archivos: certificado y clave privada (FileField, procesados aparte)
    # Se encriptan antes de persistir en la DB (encryption at rest).
    cert_file = form.certificado.data
    if cert_file and hasattr(cert_file, 'read'):
        cert_bytes = cert_file.read()

        # Extraer info del certificado X.509 antes de encriptar
        try:
            info_cert = extraer_info_certificado(cert_bytes)
            facturador.certificado_vencimiento = info_cert['vencimiento']
            facturador.certificado_emisor = info_cert['emisor']
            facturador.certificado_sujeto = info_cert['sujeto']
        except (ValueError, Exception) as exc:
            logger.warning('No se pudo extraer info del certificado: %s', exc)
            # No bloquear la subida; el cert se guarda igual

        facturador.certificado = encriptar(cert_bytes)

    key_file = form.clave_privada.data
    if key_file and hasattr(key_file, 'read'):
        facturador.clave_privada = encriptar(key_file.read())

    if es_nuevo:
        db.session.add(facturador)

    db.session.commit()

    accion = 'creado' if es_nuevo else 'actualizado'
    flash(f'Facturador "{facturador.nombre}" {accion} correctamente.', 'success')
    return redirect(url_for('facturacion.listar_facturadores'))
