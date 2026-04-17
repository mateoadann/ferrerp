"""Rutas de clientes."""

from decimal import Decimal

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..forms.cliente_forms import ClienteForm, PagoCuentaCorrienteForm
from ..models import Caja, Cheque, Cliente, MovimientoCaja, MovimientoCuentaCorriente
from ..services.cumpleanos_service import (
    contar_cumpleanos_hoy,
    generar_url_whatsapp_cumpleanos,
    obtener_cumpleanos_hoy,
)
from ..utils.decorators import empresa_aprobada_required
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
                Cliente.email.ilike(f'%{busqueda}%')
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
        url_whatsapp = generar_url_whatsapp_cumpleanos(
            cliente, current_user.empresa_id
        )
        datos_cumpleanos.append({
            'cliente': cliente,
            'url_whatsapp': url_whatsapp,
        })

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
        'clientes/form.html',
        form=form,
        titulo='Editar Cliente',
        cliente=cliente
    )


@bp.route('/<int:id>/cuenta-corriente')
@login_required
def cuenta_corriente(id):
    """Ver cuenta corriente del cliente."""
    cliente = Cliente.get_o_404(id)
    page = request.args.get('page', 1, type=int)

    movimientos = MovimientoCuentaCorriente.query_empresa().filter_by(
        cliente_id=id
    ).order_by(
        MovimientoCuentaCorriente.created_at.desc()
    ).paginate(page=page, per_page=20)

    movimientos_ids = [mov.id for mov in movimientos.items if mov.tipo == 'pago']
    formas_pago = {}
    if movimientos_ids:
        movimientos_caja = MovimientoCaja.query.filter(
            MovimientoCaja.referencia_tipo == 'pago_cc',
            MovimientoCaja.referencia_id.in_(movimientos_ids)
        ).all()
        formas_pago = {mov.referencia_id: mov.forma_pago_display for mov in movimientos_caja}

    form = PagoCuentaCorrienteForm()

    return render_template(
        'clientes/cuenta_corriente.html',
        cliente=cliente,
        movimientos=movimientos,
        form=form,
        formas_pago=formas_pago
    )


@bp.route('/<int:id>/registrar-pago', methods=['POST'])
@login_required
@empresa_aprobada_required
def registrar_pago(id):
    """Registrar pago de cuenta corriente."""
    cliente = Cliente.get_o_404(id)
    form = PagoCuentaCorrienteForm()

    if form.validate_on_submit():
        monto = Decimal(str(form.monto.data))

        # Verificar que el monto no exceda la deuda
        if monto > cliente.saldo_cuenta_corriente:
            flash('El monto no puede ser mayor que la deuda.', 'danger')
            return redirect(url_for('clientes.cuenta_corriente', id=id))

        # Verificar caja abierta
        caja = Caja.query.filter_by(
            estado='abierta', empresa_id=current_user.empresa_id
        ).first()
        if not caja:
            flash('No hay caja abierta. Abre la caja para registrar el pago.', 'warning')
            return redirect(url_for('caja.index'))

        # Actualizar saldo del cliente
        saldo_anterior, saldo_posterior = cliente.actualizar_saldo(monto, tipo='pago')

        # Registrar movimiento de cuenta corriente
        movimiento_cc = MovimientoCuentaCorriente(
            cliente_id=cliente.id,
            tipo='pago',
            monto=monto,
            saldo_anterior=saldo_anterior,
            saldo_posterior=saldo_posterior,
            referencia_tipo='pago',
            descripcion=form.descripcion.data or 'Pago de cuenta corriente',
            usuario_id=current_user.id,
            empresa_id=current_user.empresa_id,
        )
        db.session.add(movimiento_cc)
        db.session.flush()

        # Registrar ingreso en caja
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
            usuario_id=current_user.id
        )
        db.session.add(movimiento_caja)

        # Crear cheque si la forma de pago es cheque
        if forma_pago == 'cheque':
            from datetime import datetime

            cheque_numero = (request.form.get('cheque_numero') or '').strip()
            cheque_banco = (request.form.get('cheque_banco') or '').strip()
            cheque_fecha_str = (
                request.form.get('cheque_fecha_vencimiento') or ''
            ).strip()

            if not cheque_numero or not cheque_banco or not cheque_fecha_str:
                db.session.rollback()
                flash(
                    'Los datos del cheque son obligatorios '
                    '(número, banco y fecha de vencimiento).',
                    'danger',
                )
                return redirect(url_for('clientes.cuenta_corriente', id=id))

            try:
                cheque_fecha = datetime.strptime(
                    cheque_fecha_str, '%Y-%m-%d'
                ).date()
            except ValueError:
                db.session.rollback()
                flash(
                    'La fecha de vencimiento del cheque no es válida.',
                    'danger',
                )
                return redirect(url_for('clientes.cuenta_corriente', id=id))

            cheque = Cheque(
                numero_cheque=cheque_numero,
                banco=cheque_banco,
                fecha_vencimiento=cheque_fecha,
                importe=monto,
                referencia_tipo='pago_cc',
                referencia_id=movimiento_cc.id,
                empresa_id=current_user.empresa_id,
                usuario_id=current_user.id,
            )
            db.session.add(cheque)

        db.session.commit()

        flash(f'Pago de ${monto:.2f} registrado correctamente.', 'success')

    return redirect(url_for('clientes.cuenta_corriente', id=id))


@bp.route('/deudores')
@login_required
def deudores():
    """Listado de clientes con deuda."""
    page = request.args.get('page', 1, type=int)

    clientes = Cliente.query_empresa().filter(
        Cliente.activo.is_(True),
        Cliente.saldo_cuenta_corriente > 0
    ).order_by(
        Cliente.saldo_cuenta_corriente.desc()
    ).paginate(page=page, per_page=20)

    # Total de deudas
    total_deudas = db.session.query(
        func.sum(Cliente.saldo_cuenta_corriente)
    ).filter(
        Cliente.empresa_id == current_user.empresa_id,
        Cliente.activo.is_(True),
        Cliente.saldo_cuenta_corriente > 0
    ).scalar() or 0

    return render_template(
        'clientes/deudores.html',
        clientes=clientes,
        total_deudas=total_deudas
    )


@bp.route('/buscar')
@login_required
def buscar():
    """Búsqueda de clientes para autocompletado (AJAX)."""
    q = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)

    if len(q) < 2:
        return jsonify([])

    clientes = Cliente.query_empresa().filter(
        Cliente.activo.is_(True),
        db.or_(
            Cliente.nombre.ilike(f'%{q}%'),
            Cliente.dni_cuit.ilike(f'%{q}%')
        )
    ).limit(limit).all()

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
