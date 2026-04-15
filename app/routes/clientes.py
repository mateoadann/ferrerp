"""Rutas de clientes."""

from decimal import Decimal

from flask import (
    Blueprint,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..forms.cliente_forms import (
    AdelantoCuentaCorrienteForm,
    ClienteForm,
    PagoCuentaCorrienteForm,
)
from ..models import Caja, Cliente, MovimientoCaja, MovimientoCuentaCorriente
from ..services import cuenta_corriente_service
from ..services.cumpleanos_service import (
    contar_cumpleanos_hoy,
    generar_url_whatsapp_cumpleanos,
    obtener_cumpleanos_hoy,
)
from ..utils.decorators import admin_required, empresa_aprobada_required
from ..utils.helpers import es_peticion_htmx, paginar_query

bp = Blueprint('clientes', __name__, url_prefix='/clientes')


@bp.route('/')
@login_required
def index():
    """Listado de clientes."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    solo_activos = request.args.get('activos', '1') == '1'

    query = Cliente.query_empresa()

    if busqueda:
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(f'%{busqueda}%'),
                Cliente.dni_cuit.ilike(f'%{busqueda}%'),
                Cliente.email.ilike(f'%{busqueda}%'),
            )
        )

    if solo_activos:
        query = query.filter(Cliente.activo.is_(True))

    query = query.order_by(Cliente.nombre)
    clientes = paginar_query(query, page)

    if es_peticion_htmx():
        return render_template(
            'clientes/_tabla.html',
            clientes=clientes,
            busqueda=busqueda,
            pagination=clientes,
        )

    cantidad_cumpleanos = contar_cumpleanos_hoy(current_user.empresa_id)

    return render_template(
        'clientes/index.html',
        clientes=clientes,
        busqueda=busqueda,
        solo_activos=solo_activos,
        cumpleanos_hoy=cantidad_cumpleanos,
    )


@bp.route('/cumpleanos')
@login_required
def cumpleanos():
    """Retorna contenido parcial del modal de cumpleaños del día."""
    clientes = obtener_cumpleanos_hoy(current_user.empresa_id)

    datos_cumpleanos = []
    for cliente in clientes:
        url_whatsapp = generar_url_whatsapp_cumpleanos(cliente, current_user.empresa_id)
        datos_cumpleanos.append(
            {
                'cliente': cliente,
                'url_whatsapp': url_whatsapp,
            }
        )

    return render_template(
        'clientes/_contenido_cumpleanos.html',
        datos_cumpleanos=datos_cumpleanos,
    )


@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def nuevo():
    """Crear nuevo cliente."""
    form = ClienteForm()

    if form.validate_on_submit():
        cliente = Cliente(
            nombre=form.nombre.data,
            dni_cuit=form.dni_cuit.data,
            telefono=form.telefono.data,
            email=form.email.data,
            direccion=form.direccion.data,
            limite_credito=form.limite_credito.data or 0,
            notas=form.notas.data,
            fecha_nacimiento=form.fecha_nacimiento.data,
            activo=form.activo.data,
            empresa_id=current_user.empresa_id,
        )

        db.session.add(cliente)
        db.session.commit()

        flash(f'Cliente "{cliente.nombre}" creado correctamente.', 'success')
        return redirect(url_for('clientes.index'))

    return render_template('clientes/form.html', form=form, titulo='Nuevo Cliente')


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def editar(id):
    """Editar cliente."""
    cliente = Cliente.get_o_404(id)
    form = ClienteForm(obj=cliente)

    if form.validate_on_submit():
        cliente.nombre = form.nombre.data
        cliente.dni_cuit = form.dni_cuit.data
        cliente.telefono = form.telefono.data
        cliente.email = form.email.data
        cliente.direccion = form.direccion.data
        cliente.limite_credito = form.limite_credito.data or 0
        cliente.notas = form.notas.data
        cliente.fecha_nacimiento = form.fecha_nacimiento.data
        cliente.activo = form.activo.data

        db.session.commit()

        flash(f'Cliente "{cliente.nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('clientes.index'))

    return render_template(
        'clientes/form.html', form=form, titulo='Editar Cliente', cliente=cliente
    )


@bp.route('/<int:id>/cuenta-corriente')
@login_required
def cuenta_corriente(id):
    """Ver cuenta corriente del cliente."""
    cliente = Cliente.get_o_404(id)
    page = request.args.get('page', 1, type=int)

    movimientos = (
        MovimientoCuentaCorriente.query_empresa()
        .filter_by(cliente_id=id)
        .order_by(MovimientoCuentaCorriente.created_at.desc())
        .paginate(page=page, per_page=20)
    )

    movimientos_ids = [mov.id for mov in movimientos.items if mov.tipo == 'pago']
    formas_pago = {}
    if movimientos_ids:
        movimientos_caja = MovimientoCaja.query.filter(
            MovimientoCaja.referencia_tipo == 'pago_cc',
            MovimientoCaja.referencia_id.in_(movimientos_ids),
        ).all()
        formas_pago = {mov.referencia_id: mov.forma_pago_display for mov in movimientos_caja}

    form = PagoCuentaCorrienteForm()
    form_adelanto = AdelantoCuentaCorrienteForm()

    return render_template(
        'clientes/cuenta_corriente.html',
        cliente=cliente,
        movimientos=movimientos,
        form=form,
        form_adelanto=form_adelanto,
        formas_pago=formas_pago,
    )


@bp.route('/<int:id>/estado-cuenta-pdf')
@login_required
@empresa_aprobada_required
def estado_cuenta_pdf(id):
    """Descargar PDF del estado de cuenta del cliente."""
    cliente = Cliente.get_o_404(id)

    pdf_bytes = cuenta_corriente_service.generar_estado_cuenta_pdf(cliente)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=estado_cuenta_{cliente.id}.pdf'
    return response


@bp.route('/<int:id>/registrar-pago', methods=['POST'])
@login_required
@empresa_aprobada_required
def registrar_pago(id):
    """Registrar pago de cuenta corriente."""
    cliente = Cliente.get_o_404(id)
    form = PagoCuentaCorrienteForm()

    if form.validate_on_submit():
        monto = Decimal(str(form.monto.data or 0))

        # Leer monto de saldo a favor
        usar_saldo_favor = request.form.get('usar_saldo_favor')
        monto_saldo_favor = Decimal('0')
        if usar_saldo_favor and cliente.tiene_saldo_a_favor:
            monto_saldo_favor_raw = request.form.get('monto_saldo_favor', '0')
            try:
                monto_saldo_favor = Decimal(str(monto_saldo_favor_raw))
            except Exception:
                monto_saldo_favor = Decimal('0')

            # Validaciones de saldo a favor
            if monto_saldo_favor < 0:
                monto_saldo_favor = Decimal('0')
            if monto_saldo_favor > cliente.saldo_a_favor:
                monto_saldo_favor = cliente.saldo_a_favor

        monto_total = monto + monto_saldo_favor

        # Verificar que se pague algo
        if monto_total <= 0:
            flash('Debe ingresar un monto a pagar.', 'danger')
            return redirect(url_for('clientes.cuenta_corriente', id=id))

        # Verificar que el monto total no exceda la deuda
        if monto_total > cliente.saldo_cuenta_corriente:
            flash('El monto total no puede ser mayor que la deuda.', 'danger')
            return redirect(url_for('clientes.cuenta_corriente', id=id))

        # Verificar caja abierta si hay pago en efectivo/tarjeta
        caja = None
        if monto > 0:
            caja = Caja.query.filter_by(
                estado='abierta', empresa_id=current_user.empresa_id
            ).first()
            if not caja:
                flash(
                    'No hay caja abierta. Abre la caja para registrar el pago.',
                    'warning',
                )
                return redirect(url_for('caja.index'))

        descripcion_base = form.descripcion.data or 'Pago de cuenta corriente'

        # 1) Consumir saldo a favor (no pasa por caja)
        if monto_saldo_favor > 0:
            sf_anterior, sf_nuevo = cliente.actualizar_saldo_favor(monto_saldo_favor, 'cargo')
            saldo_ant, saldo_post = cliente.actualizar_saldo(monto_saldo_favor, tipo='pago')
            mov_sf = MovimientoCuentaCorriente(
                cliente_id=cliente.id,
                tipo='pago',
                monto=monto_saldo_favor,
                saldo_anterior=saldo_ant,
                saldo_posterior=saldo_post,
                referencia_tipo='consumo_saldo_favor',
                descripcion='Pago con saldo a favor',
                usuario_id=current_user.id,
                empresa_id=current_user.empresa_id,
            )
            db.session.add(mov_sf)

        # 2) Pago en efectivo/tarjeta (pasa por caja)
        if monto > 0:
            saldo_anterior, saldo_posterior = cliente.actualizar_saldo(monto, tipo='pago')

            movimiento_cc = MovimientoCuentaCorriente(
                cliente_id=cliente.id,
                tipo='pago',
                monto=monto,
                saldo_anterior=saldo_anterior,
                saldo_posterior=saldo_posterior,
                referencia_tipo='pago',
                descripcion=descripcion_base,
                usuario_id=current_user.id,
                empresa_id=current_user.empresa_id,
            )
            db.session.add(movimiento_cc)
            db.session.flush()

            forma_pago = form.forma_pago.data or 'efectivo'
            movimiento_caja = MovimientoCaja(
                caja_id=caja.id,
                tipo='ingreso',
                concepto='cobro_cuenta_corriente',
                descripcion=f'Pago de {cliente.nombre}',
                monto=monto,
                forma_pago=forma_pago,
                referencia_tipo='pago_cc',
                referencia_id=movimiento_cc.id,
                usuario_id=current_user.id,
            )
            db.session.add(movimiento_caja)

        db.session.commit()

        # Mensaje flash descriptivo
        partes = []
        if monto_saldo_favor > 0:
            partes.append(f'${monto_saldo_favor:.2f} de saldo a favor')
        if monto > 0:
            partes.append(f'${monto:.2f} en efectivo/tarjeta')
        detalle = ' + '.join(partes)
        flash(f'Pago registrado: {detalle}.', 'success')

    return redirect(url_for('clientes.cuenta_corriente', id=id))


@bp.route('/<int:id>/registrar-adelanto', methods=['POST'])
@login_required
@empresa_aprobada_required
def registrar_adelanto(id):
    """Registrar adelanto de cuenta corriente."""
    cliente = Cliente.get_o_404(id)
    form = AdelantoCuentaCorrienteForm()

    if form.validate_on_submit():
        monto = Decimal(str(form.monto.data))

        # Verificar caja abierta
        caja = Caja.query.filter_by(estado='abierta', empresa_id=current_user.empresa_id).first()
        if not caja:
            flash(
                'Necesitás tener una caja abierta para registrar' ' un adelanto.',
                'warning',
            )
            return redirect(url_for('caja.index'))

        # Actualizar saldo a favor del cliente (adelanto suma saldo a favor)
        saldo_anterior, saldo_posterior = cliente.actualizar_saldo_favor(monto, tipo='adelanto')

        # Registrar movimiento de cuenta corriente
        movimiento_cc = MovimientoCuentaCorriente(
            cliente_id=cliente.id,
            tipo='pago',
            monto=monto,
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_posterior,
            referencia_tipo='adelanto',
            descripcion=form.motivo.data or 'Adelanto de cliente',
            usuario_id=current_user.id,
            empresa_id=current_user.empresa_id,
        )
        db.session.add(movimiento_cc)
        db.session.flush()

        # Registrar ingreso en caja
        movimiento_caja = MovimientoCaja(
            caja_id=caja.id,
            tipo='ingreso',
            concepto='adelanto_cliente',
            descripcion=f'Adelanto CC - {cliente.nombre}',
            monto=monto,
            forma_pago=form.forma_pago.data,
            referencia_tipo='pago_cc',
            referencia_id=movimiento_cc.id,
            usuario_id=current_user.id,
        )
        db.session.add(movimiento_caja)

        db.session.commit()

        flash(
            f'Adelanto de ${monto:.2f} registrado correctamente.',
            'success',
        )

    return redirect(url_for('clientes.cuenta_corriente', id=id))


@bp.route(
    '/<int:id>/anular-adelanto/<int:movimiento_id>',
    methods=['POST'],
)
@login_required
@empresa_aprobada_required
@admin_required
def anular_adelanto(id, movimiento_id):
    """Anular un adelanto de cuenta corriente."""
    cliente = Cliente.get_o_404(id)

    movimiento = MovimientoCuentaCorriente.query.filter_by(
        id=movimiento_id,
        cliente_id=cliente.id,
        empresa_id=current_user.empresa_id,
    ).first_or_404()

    # Validar que sea un adelanto
    if movimiento.referencia_tipo != 'adelanto':
        flash('El movimiento seleccionado no es un adelanto.', 'danger')
        return redirect(url_for('clientes.cuenta_corriente', id=id))

    # Verificar que no esté ya anulado
    anulacion_existente = MovimientoCuentaCorriente.query.filter_by(
        referencia_tipo='anulacion_adelanto',
        referencia_id=movimiento.id,
        empresa_id=current_user.empresa_id,
    ).first()
    if anulacion_existente:
        flash('Este adelanto ya fue anulado.', 'warning')
        return redirect(url_for('clientes.cuenta_corriente', id=id))

    # Verificar caja abierta
    caja = Caja.query.filter_by(estado='abierta', empresa_id=current_user.empresa_id).first()
    if not caja:
        flash(
            'Necesitás tener una caja abierta para anular' ' un adelanto.',
            'warning',
        )
        return redirect(url_for('caja.index'))

    # Revertir saldo a favor (cargo consume saldo a favor)
    saldo_anterior, saldo_posterior = cliente.actualizar_saldo_favor(movimiento.monto, tipo='cargo')

    # Registrar movimiento de anulación en cuenta corriente
    movimiento_cc = MovimientoCuentaCorriente(
        cliente_id=cliente.id,
        tipo='cargo',
        monto=movimiento.monto,
        saldo_anterior=saldo_anterior,
        saldo_posterior=saldo_posterior,
        referencia_tipo='anulacion_adelanto',
        referencia_id=movimiento.id,
        descripcion=f'Anulación de adelanto #{movimiento.id}',
        usuario_id=current_user.id,
        empresa_id=current_user.empresa_id,
    )
    db.session.add(movimiento_cc)
    db.session.flush()

    # Registrar egreso en caja
    movimiento_caja = MovimientoCaja(
        caja_id=caja.id,
        tipo='egreso',
        concepto='adelanto_cliente',
        descripcion=(f'Anulación adelanto CC - {cliente.nombre}'),
        monto=movimiento.monto,
        forma_pago='efectivo',
        referencia_tipo='pago_cc',
        referencia_id=movimiento_cc.id,
        usuario_id=current_user.id,
    )
    db.session.add(movimiento_caja)

    db.session.commit()

    flash(
        f'Adelanto #{movimiento.id} anulado correctamente.',
        'success',
    )
    return redirect(url_for('clientes.cuenta_corriente', id=id))


@bp.route('/con-saldo-a-favor')
@login_required
@empresa_aprobada_required
def con_saldo_a_favor():
    """Listado de clientes con saldo a favor."""
    page = request.args.get('page', 1, type=int)

    clientes = (
        Cliente.query_empresa()
        .filter(
            Cliente.activo.is_(True),
            Cliente.saldo_a_favor_monto > 0,
        )
        .order_by(Cliente.saldo_a_favor_monto.desc())
        .paginate(page=page, per_page=20)
    )

    # Total de saldo a favor
    total_saldo_a_favor = (
        db.session.query(func.sum(Cliente.saldo_a_favor_monto))
        .filter(
            Cliente.empresa_id == current_user.empresa_id,
            Cliente.activo.is_(True),
            Cliente.saldo_a_favor_monto > 0,
        )
        .scalar()
        or 0
    )

    return render_template(
        'clientes/con_saldo_a_favor.html',
        clientes=clientes,
        total_saldo_a_favor=total_saldo_a_favor,
    )


@bp.route('/deudores')
@login_required
def deudores():
    """Listado de clientes con deuda."""
    page = request.args.get('page', 1, type=int)

    clientes = (
        Cliente.query_empresa()
        .filter(Cliente.activo.is_(True), Cliente.saldo_cuenta_corriente > 0)
        .order_by(Cliente.saldo_cuenta_corriente.desc())
        .paginate(page=page, per_page=20)
    )

    # Total de deudas
    total_deudas = (
        db.session.query(func.sum(Cliente.saldo_cuenta_corriente))
        .filter(
            Cliente.empresa_id == current_user.empresa_id,
            Cliente.activo.is_(True),
            Cliente.saldo_cuenta_corriente > 0,
        )
        .scalar()
        or 0
    )

    return render_template('clientes/deudores.html', clientes=clientes, total_deudas=total_deudas)


@bp.route('/buscar')
@login_required
def buscar():
    """Búsqueda de clientes para autocompletado (AJAX)."""
    q = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)

    if len(q) < 2:
        return jsonify([])

    clientes = (
        Cliente.query_empresa()
        .filter(
            Cliente.activo.is_(True),
            db.or_(Cliente.nombre.ilike(f'%{q}%'), Cliente.dni_cuit.ilike(f'%{q}%')),
        )
        .limit(limit)
        .all()
    )

    return jsonify([c.to_dict() for c in clientes])


@bp.route('/<int:id>/toggle-activo', methods=['POST'])
@login_required
@empresa_aprobada_required
def toggle_activo(id):
    """Activar/desactivar cliente."""
    cliente = Cliente.get_o_404(id)
    cliente.activo = not cliente.activo
    db.session.commit()

    estado = 'activado' if cliente.activo else 'desactivado'
    flash(f'Cliente "{cliente.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('clientes.index'))
