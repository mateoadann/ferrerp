"""Rutas de caja."""

from datetime import date
from decimal import Decimal
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Caja, MovimientoCaja, Venta, VentaPago
from ..forms.caja_forms import AperturaCajaForm, CierreCajaForm, EgresoCajaForm
from ..utils.helpers import ahora_argentina, paginar_query
from ..utils.decorators import admin_required, empresa_aprobada_required

bp = Blueprint('caja', __name__, url_prefix='/caja')


def _agrupar_movimientos_divididos(movimientos):
    """Agrupa movimientos de pagos divididos de una misma venta en una sola fila.

    Los movimientos con el mismo venta_id (no None) y que NO son informativos
    se consolidan en un unico registro con multiples formas de pago.
    """
    agrupados = []
    venta_grupos = {}  # venta_id -> indice en agrupados

    for mov in movimientos:
        vid = mov.get('venta_id')
        # Solo agrupar movimientos de caja reales (no informativos) con venta_id
        if vid and not mov['es_informativo']:
            if vid in venta_grupos:
                # Agregar esta forma de pago al movimiento existente
                idx = venta_grupos[vid]
                agrupados[idx]['formas_pago'].append({
                    'forma_pago': mov['forma_pago'],
                    'forma_pago_display': mov['forma_pago_display'],
                    'monto': mov['monto'],
                })
                agrupados[idx]['monto'] += mov['monto']
            else:
                # Primer movimiento de esta venta
                mov['formas_pago'] = [{
                    'forma_pago': mov['forma_pago'],
                    'forma_pago_display': mov['forma_pago_display'],
                    'monto': mov['monto'],
                }]
                # Limpiar "(pago parcial)" de la descripcion
                if mov['descripcion']:
                    mov['descripcion'] = mov['descripcion'].replace(
                        ' (pago parcial)', ''
                    )
                venta_grupos[vid] = len(agrupados)
                agrupados.append(mov)
        else:
            # Movimiento sin venta o informativo: agregar tal cual
            mov['formas_pago'] = [{
                'forma_pago': mov['forma_pago'],
                'forma_pago_display': mov['forma_pago_display'],
                'monto': mov['monto'],
            }]
            agrupados.append(mov)

    # Para movimientos informativos (CC) de ventas divididas que ya tienen
    # su contraparte agrupada, consolidar en la misma fila
    for mov in agrupados:
        vid = mov.get('venta_id')
        if vid and mov['es_informativo'] and vid in venta_grupos:
            idx = venta_grupos[vid]
            if agrupados[idx] is not mov:
                agrupados[idx]['formas_pago'].append({
                    'forma_pago': mov['forma_pago'],
                    'forma_pago_display': mov['forma_pago_display'],
                    'monto': mov['monto'],
                })
                agrupados[idx]['monto'] += mov['monto']
                mov['_eliminar'] = True

    return [m for m in agrupados if not m.get('_eliminar')]


@bp.route('/')
@login_required
def index():
    """Vista principal de caja (caja del día)."""
    # Buscar caja abierta
    caja = Caja.query_empresa().filter_by(estado='abierta').first()

    if caja:
        # Calcular totales
        movimientos_caja = caja.movimientos.order_by(MovimientoCaja.created_at.desc()).all()

        # Ventas CC puras
        ventas_cc = Venta.query.filter_by(
            caja_id=caja.id,
            forma_pago='cuenta_corriente',
            estado='completada'
        ).order_by(Venta.fecha.desc()).all()

        # Ventas divididas con componente CC
        ventas_divididas_cc = (
            Venta.query.join(VentaPago)
            .filter(
                Venta.caja_id == caja.id,
                Venta.forma_pago == 'dividido',
                Venta.estado == 'completada',
                VentaPago.forma_pago == 'cuenta_corriente',
            )
            .order_by(Venta.fecha.desc())
            .all()
        )

        # Total CC: ventas CC puras + montos parciales CC de divididas
        total_cc_ventas = sum((v.total for v in ventas_cc), Decimal('0'))
        for venta_div in ventas_divididas_cc:
            for pago in venta_div.pagos:
                if pago.forma_pago == 'cuenta_corriente':
                    total_cc_ventas += pago.monto

        # Combinar ventas CC para mostrar en movimientos
        todas_ventas_cc = list(ventas_cc)
        for venta_div in ventas_divididas_cc:
            if venta_div not in todas_ventas_cc:
                todas_ventas_cc.append(venta_div)

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
                'es_informativo': False,
                'venta_id': (
                    mov.referencia_id
                    if mov.referencia_tipo == 'venta' else None
                ),
            }
            for mov in movimientos_caja
        ]

        for venta in todas_ventas_cc:
            if venta.forma_pago == 'dividido':
                # Mostrar solo el monto parcial CC
                monto_cc = sum(
                    p.monto for p in venta.pagos
                    if p.forma_pago == 'cuenta_corriente'
                )
            else:
                monto_cc = venta.total
            movimientos.append({
                'fecha': venta.fecha,
                'tipo': 'informativo',
                'tipo_display': 'Venta',
                'concepto_display': 'Venta',
                'forma_pago': 'cuenta_corriente',
                'forma_pago_display': 'Cuenta Corriente',
                'descripcion': f'Venta #{venta.numero_completo}',
                'monto': monto_cc,
                'es_informativo': True,
                'venta_id': venta.id,
            })

        movimientos.sort(key=lambda mov: mov['fecha'], reverse=True)
        movimientos = _agrupar_movimientos_divididos(movimientos)

        # Totales por forma de pago
        totales_forma_pago = {}
        for mov in movimientos_caja:
            if mov.tipo == 'ingreso':
                if mov.forma_pago not in totales_forma_pago:
                    totales_forma_pago[mov.forma_pago] = {
                        'ingresos': Decimal('0'), 'egresos': Decimal('0'),
                    }
                totales_forma_pago[mov.forma_pago]['ingresos'] += mov.monto
            else:
                if mov.forma_pago not in totales_forma_pago:
                    totales_forma_pago[mov.forma_pago] = {
                        'ingresos': Decimal('0'), 'egresos': Decimal('0'),
                    }
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
@empresa_aprobada_required
def abrir():
    """Abrir caja del día."""
    # Verificar si ya hay una caja abierta
    caja_existente = Caja.query_empresa().filter_by(estado='abierta').first()
    if caja_existente:
        flash('Ya hay una caja abierta.', 'warning')
        return redirect(url_for('caja.index'))

    form = AperturaCajaForm()

    if form.validate_on_submit():
        caja = Caja(
            fecha_apertura=ahora_argentina(),
            usuario_apertura_id=current_user.id,
            monto_inicial=form.monto_inicial.data,
            estado='abierta',
            empresa_id=current_user.empresa_id,
        )

        db.session.add(caja)
        db.session.commit()

        flash(f'Caja abierta con ${form.monto_inicial.data:.2f}', 'success')
        return redirect(url_for('caja.index'))

    return render_template('caja/apertura.html', form=form)


@bp.route('/cerrar', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def cerrar():
    """Cerrar caja del día."""
    caja = Caja.query_empresa().filter_by(estado='abierta').first()

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
@empresa_aprobada_required
def egreso():
    """Registrar egreso de caja."""
    caja = Caja.query_empresa().filter_by(estado='abierta').first()

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

    cajas = Caja.query_empresa().order_by(
        Caja.fecha_apertura.desc()
    ).paginate(page=page, per_page=20)

    return render_template('caja/historial.html', cajas=cajas)


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de una caja."""
    caja = Caja.get_o_404(id)

    movimientos_caja = caja.movimientos.order_by(MovimientoCaja.created_at.desc()).all()

    # Ventas CC puras
    ventas_cc = Venta.query.filter_by(
        caja_id=caja.id,
        forma_pago='cuenta_corriente',
        estado='completada'
    ).order_by(Venta.fecha.desc()).all()

    # Ventas divididas con componente CC
    ventas_divididas_cc = (
        Venta.query.join(VentaPago)
        .filter(
            Venta.caja_id == caja.id,
            Venta.forma_pago == 'dividido',
            Venta.estado == 'completada',
            VentaPago.forma_pago == 'cuenta_corriente',
        )
        .order_by(Venta.fecha.desc())
        .all()
    )

    # Total CC: ventas CC puras + montos parciales CC de divididas
    total_cc_ventas = sum((v.total for v in ventas_cc), Decimal('0'))
    for venta_div in ventas_divididas_cc:
        for pago in venta_div.pagos:
            if pago.forma_pago == 'cuenta_corriente':
                total_cc_ventas += pago.monto

    # Combinar ventas CC para mostrar en movimientos
    todas_ventas_cc = list(ventas_cc)
    for venta_div in ventas_divididas_cc:
        if venta_div not in todas_ventas_cc:
            todas_ventas_cc.append(venta_div)

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
            'es_informativo': False,
            'venta_id': (
                mov.referencia_id
                if mov.referencia_tipo == 'venta' else None
            ),
        }
        for mov in movimientos_caja
    ]

    for venta in todas_ventas_cc:
        if venta.forma_pago == 'dividido':
            monto_cc = sum(
                p.monto for p in venta.pagos
                if p.forma_pago == 'cuenta_corriente'
            )
        else:
            monto_cc = venta.total
        movimientos.append({
            'fecha': venta.fecha,
            'tipo': 'informativo',
            'tipo_display': 'Venta',
            'concepto_display': 'Venta',
            'forma_pago': 'cuenta_corriente',
            'forma_pago_display': 'Cuenta Corriente',
            'descripcion': f'Venta #{venta.numero_completo}',
            'monto': monto_cc,
            'es_informativo': True,
            'venta_id': venta.id,
        })

    movimientos.sort(key=lambda mov: mov['fecha'], reverse=True)
    movimientos = _agrupar_movimientos_divididos(movimientos)

    # Totales por forma de pago
    totales_forma_pago = {}
    for mov in movimientos_caja:
        if mov.forma_pago not in totales_forma_pago:
            totales_forma_pago[mov.forma_pago] = {
                'ingresos': Decimal('0'), 'egresos': Decimal('0'),
            }

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
