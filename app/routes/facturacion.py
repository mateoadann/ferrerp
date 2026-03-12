"""Rutas de facturación."""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.configuracion_forms import ConfiguracionArcaForm
from ..models import Factura, Venta
from ..services.arca_exceptions import ArcaAuthError, ArcaNetworkError, ArcaValidationError
from ..services.facturacion_service import FacturacionService
from ..services.padron_service import PadronService
from ..utils.decorators import admin_required, empresa_aprobada_required
from ..utils.helpers import paginar_query

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


@bp.route('/emitir/<int:venta_id>', methods=['POST'])
@login_required
@empresa_aprobada_required
def emitir_desde_venta(venta_id):
    """Emite una factura electrónica para una venta."""
    venta = Venta.get_o_404(venta_id)

    try:
        factura = FacturacionService().emitir_factura_desde_venta(
            venta_id=venta.id,
            empresa_id=current_user.empresa_id,
        )
    except ArcaValidationError as exc:
        flash(f'No se pudo emitir la factura: {exc.mensaje}', 'danger')
        return redirect(url_for('ventas.detalle', id=venta.id))
    except (ArcaAuthError, ArcaNetworkError) as exc:
        flash(f'Error de conexión con ARCA: {exc.mensaje}', 'warning')
        return redirect(url_for('ventas.detalle', id=venta.id))
    except Exception:
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
            tipo_comprobante=factura.tipo_comprobante,
            punto_venta=factura.punto_venta,
            concepto=factura.concepto,
        )
    except ArcaValidationError as exc:
        flash(f'No se pudo reintentar la factura: {exc.mensaje}', 'danger')
        return redirect(url_for('facturacion.detalle', id=factura.id))
    except (ArcaAuthError, ArcaNetworkError) as exc:
        flash(f'Error de conexión con ARCA: {exc.mensaje}', 'warning')
        return redirect(url_for('facturacion.detalle', id=factura.id))
    except Exception:
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


@bp.route('/configuracion-arca', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
@admin_required
def configuracion_arca():
    """Configuración ARCA de la empresa actual."""
    empresa = current_user.empresa
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
            empresa.certificado_arca = form.certificado_arca.data.read()

        if form.clave_privada_arca.data and form.clave_privada_arca.data.filename:
            empresa.clave_privada_arca = form.clave_privada_arca.data.read()

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

    return render_template('facturacion/configuracion_arca.html', form=form, empresa=empresa)


@bp.route('/padron/consultar', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def consultar_padron():
    """Consulta manual de padrón ARCA por CUIT."""
    cuit_consulta = (request.form.get('cuit') or '').strip()

    try:
        resultado = PadronService().consultar_cliente(cuit_consulta, current_user.empresa)
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
        return jsonify(
            {'success': False, 'error': 'Error inesperado al consultar padrón ARCA.'}
        ), 500
