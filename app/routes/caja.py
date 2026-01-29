"""Rutas de caja."""

from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Caja, MovimientoCaja
from ..forms.caja_forms import AperturaCajaForm, CierreCajaForm, EgresoCajaForm
from ..utils.helpers import paginar_query
from ..utils.decorators import admin_required

bp = Blueprint('caja', __name__, url_prefix='/caja')


@bp.route('/')
@login_required
def index():
    """Vista principal de caja (caja del día)."""
    # Buscar caja abierta
    caja = Caja.query.filter_by(estado='abierta').first()

    if caja:
        # Calcular totales
        movimientos = caja.movimientos.order_by(MovimientoCaja.created_at.desc()).all()

        # Totales por forma de pago
        totales_forma_pago = {}
        for mov in movimientos:
            if mov.tipo == 'ingreso':
                if mov.forma_pago not in totales_forma_pago:
                    totales_forma_pago[mov.forma_pago] = {'ingresos': Decimal('0'), 'egresos': Decimal('0')}
                totales_forma_pago[mov.forma_pago]['ingresos'] += mov.monto
            else:
                if mov.forma_pago not in totales_forma_pago:
                    totales_forma_pago[mov.forma_pago] = {'ingresos': Decimal('0'), 'egresos': Decimal('0')}
                totales_forma_pago[mov.forma_pago]['egresos'] += mov.monto

        return render_template(
            'caja/index.html',
            caja=caja,
            movimientos=movimientos,
            totales_forma_pago=totales_forma_pago
        )

    # No hay caja abierta
    return render_template('caja/sin_caja.html')


@bp.route('/abrir', methods=['GET', 'POST'])
@login_required
def abrir():
    """Abrir caja del día."""
    # Verificar si ya hay una caja abierta
    caja_existente = Caja.query.filter_by(estado='abierta').first()
    if caja_existente:
        flash('Ya hay una caja abierta.', 'warning')
        return redirect(url_for('caja.index'))

    form = AperturaCajaForm()

    if form.validate_on_submit():
        caja = Caja(
            fecha_apertura=datetime.utcnow(),
            usuario_apertura_id=current_user.id,
            monto_inicial=form.monto_inicial.data,
            estado='abierta'
        )

        db.session.add(caja)
        db.session.commit()

        flash(f'Caja abierta con ${form.monto_inicial.data:.2f}', 'success')
        return redirect(url_for('caja.index'))

    return render_template('caja/apertura.html', form=form)


@bp.route('/cerrar', methods=['GET', 'POST'])
@login_required
def cerrar():
    """Cerrar caja del día."""
    caja = Caja.query.filter_by(estado='abierta').first()

    if not caja:
        flash('No hay caja abierta para cerrar.', 'warning')
        return redirect(url_for('caja.index'))

    # Calcular monto esperado
    caja.calcular_monto_esperado()

    form = CierreCajaForm()

    if form.validate_on_submit():
        caja.cerrar(
            monto_real=form.monto_real.data,
            usuario_cierre_id=current_user.id,
            observaciones=form.observaciones.data
        )

        db.session.commit()

        diferencia = caja.diferencia
        if diferencia > 0:
            mensaje = f'Caja cerrada. Sobrante: ${diferencia:.2f}'
        elif diferencia < 0:
            mensaje = f'Caja cerrada. Faltante: ${abs(diferencia):.2f}'
        else:
            mensaje = 'Caja cerrada correctamente. Sin diferencias.'

        flash(mensaje, 'success')
        return redirect(url_for('caja.detalle', id=caja.id))

    return render_template(
        'caja/cierre.html',
        form=form,
        caja=caja
    )


@bp.route('/egreso', methods=['POST'])
@login_required
def egreso():
    """Registrar egreso de caja."""
    caja = Caja.query.filter_by(estado='abierta').first()

    if not caja:
        flash('No hay caja abierta.', 'warning')
        return redirect(url_for('caja.index'))

    form = EgresoCajaForm()

    if form.validate_on_submit():
        movimiento = MovimientoCaja(
            caja_id=caja.id,
            tipo='egreso',
            concepto=form.concepto.data,
            descripcion=form.descripcion.data,
            monto=form.monto.data,
            forma_pago='efectivo',
            usuario_id=current_user.id
        )

        db.session.add(movimiento)
        db.session.commit()

        flash(f'Egreso de ${form.monto.data:.2f} registrado.', 'success')

    return redirect(url_for('caja.index'))


@bp.route('/historial')
@login_required
def historial():
    """Historial de cajas."""
    page = request.args.get('page', 1, type=int)

    cajas = Caja.query.order_by(
        Caja.fecha_apertura.desc()
    ).paginate(page=page, per_page=20)

    return render_template('caja/historial.html', cajas=cajas)


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de una caja."""
    caja = Caja.query.get_or_404(id)

    movimientos = caja.movimientos.order_by(MovimientoCaja.created_at.desc()).all()

    # Totales por forma de pago
    totales_forma_pago = {}
    for mov in movimientos:
        if mov.forma_pago not in totales_forma_pago:
            totales_forma_pago[mov.forma_pago] = {'ingresos': Decimal('0'), 'egresos': Decimal('0')}

        if mov.tipo == 'ingreso':
            totales_forma_pago[mov.forma_pago]['ingresos'] += mov.monto
        else:
            totales_forma_pago[mov.forma_pago]['egresos'] += mov.monto

    return render_template(
        'caja/detalle.html',
        caja=caja,
        movimientos=movimientos,
        totales_forma_pago=totales_forma_pago
    )
