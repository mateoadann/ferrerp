"""Rutas de caja."""

from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Caja, MovimientoCaja, Venta
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
        movimientos_caja = caja.movimientos.order_by(MovimientoCaja.created_at.desc()).all()
        ventas_cc = Venta.query.filter_by(
            caja_id=caja.id,
            forma_pago='cuenta_corriente',
            estado='completada'
        ).order_by(Venta.fecha.desc()).all()

        total_cc_ventas = sum((v.total for v in ventas_cc), Decimal('0'))

        movimientos = [
            {
                'fecha': mov.created_at,
                'tipo': mov.tipo,
                'tipo_display': mov.tipo_display,
                'concepto_display': mov.concepto_display,
                'forma_pago': mov.forma_pago,
                'forma_pago_display': mov.forma_pago_display,
                'descripcion': mov.descripcion,
                'monto': mov.monto,
                'es_informativo': False
            }
            for mov in movimientos_caja
        ]

        movimientos += [
            {
                'fecha': venta.fecha,
                'tipo': 'informativo',
                'tipo_display': 'Venta',
                'concepto_display': 'Venta',
                'forma_pago': 'cuenta_corriente',
                'forma_pago_display': 'Cuenta Corriente',
                'descripcion': f'Venta #{venta.numero_completo}',
                'monto': venta.total,
                'es_informativo': True
            }
            for venta in ventas_cc
        ]

        movimientos.sort(key=lambda mov: mov['fecha'], reverse=True)

        # Totales por forma de pago
        totales_forma_pago = {}
        for mov in movimientos_caja:
            if mov.tipo == 'ingreso':
                if mov.forma_pago not in totales_forma_pago:
                    totales_forma_pago[mov.forma_pago] = {'ingresos': Decimal('0'), 'egresos': Decimal('0')}
                totales_forma_pago[mov.forma_pago]['ingresos'] += mov.monto
            else:
                if mov.forma_pago not in totales_forma_pago:
                    totales_forma_pago[mov.forma_pago] = {'ingresos': Decimal('0'), 'egresos': Decimal('0')}
                totales_forma_pago[mov.forma_pago]['egresos'] += mov.monto

        if total_cc_ventas > 0:
            totales_forma_pago['cuenta_corriente'] = {
                'ingresos': total_cc_ventas,
                'egresos': Decimal('0')
            }

        total_ingresos_forma = sum(
            (totales['ingresos'] for totales in totales_forma_pago.values()),
            Decimal('0')
        )
        total_egresos_forma = sum(
            (totales['egresos'] for totales in totales_forma_pago.values()),
            Decimal('0')
        )

        return render_template(
            'caja/index.html',
            caja=caja,
            movimientos=movimientos,
            totales_forma_pago=totales_forma_pago,
            total_cc_ventas=total_cc_ventas,
            total_ingresos_forma=total_ingresos_forma,
            total_egresos_forma=total_egresos_forma
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

    movimientos_caja = caja.movimientos.order_by(MovimientoCaja.created_at.desc()).all()
    ventas_cc = Venta.query.filter_by(
        caja_id=caja.id,
        forma_pago='cuenta_corriente',
        estado='completada'
    ).order_by(Venta.fecha.desc()).all()

    total_cc_ventas = sum((v.total for v in ventas_cc), Decimal('0'))

    movimientos = [
        {
            'fecha': mov.created_at,
            'tipo': mov.tipo,
            'tipo_display': mov.tipo_display,
            'concepto_display': mov.concepto_display,
            'forma_pago': mov.forma_pago,
            'forma_pago_display': mov.forma_pago_display,
            'descripcion': mov.descripcion,
            'monto': mov.monto,
            'es_informativo': False
        }
        for mov in movimientos_caja
    ]

    movimientos += [
        {
            'fecha': venta.fecha,
            'tipo': 'informativo',
            'tipo_display': 'Venta',
            'concepto_display': 'Venta',
            'forma_pago': 'cuenta_corriente',
            'forma_pago_display': 'Cuenta Corriente',
            'descripcion': f'Venta #{venta.numero_completo}',
            'monto': venta.total,
            'es_informativo': True
        }
        for venta in ventas_cc
    ]

    movimientos.sort(key=lambda mov: mov['fecha'], reverse=True)

    # Totales por forma de pago
    totales_forma_pago = {}
    for mov in movimientos_caja:
        if mov.forma_pago not in totales_forma_pago:
            totales_forma_pago[mov.forma_pago] = {'ingresos': Decimal('0'), 'egresos': Decimal('0')}

        if mov.tipo == 'ingreso':
            totales_forma_pago[mov.forma_pago]['ingresos'] += mov.monto
        else:
            totales_forma_pago[mov.forma_pago]['egresos'] += mov.monto

    if total_cc_ventas > 0:
        totales_forma_pago['cuenta_corriente'] = {
            'ingresos': total_cc_ventas,
            'egresos': Decimal('0')
        }

    total_ingresos_forma = sum(
        (totales['ingresos'] for totales in totales_forma_pago.values()),
        Decimal('0')
    )
    total_egresos_forma = sum(
        (totales['egresos'] for totales in totales_forma_pago.values()),
        Decimal('0')
    )

    return render_template(
        'caja/detalle.html',
        caja=caja,
        movimientos=movimientos,
        totales_forma_pago=totales_forma_pago,
        total_cc_ventas=total_cc_ventas,
        total_ingresos_forma=total_ingresos_forma,
        total_egresos_forma=total_egresos_forma
    )
