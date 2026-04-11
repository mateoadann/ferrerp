"""Rutas del Dashboard."""

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Cliente, Producto, Venta
from ..utils.helpers import ahora_argentina

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    """Página principal del dashboard."""
    if current_user.es_superadmin:
        return redirect(url_for('superadmin.index'))

    # Obtener estadísticas del día
    hoy = ahora_argentina().date()
    inicio_dia = datetime.combine(hoy, datetime.min.time())
    fin_dia = datetime.combine(hoy, datetime.max.time())

    empresa_id = current_user.empresa_id

    # Ventas del día
    ventas_hoy = db.session.query(
        func.coalesce(func.sum(Venta.total), 0)
    ).filter(
        Venta.empresa_id == empresa_id,
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).scalar()

    # Cantidad de operaciones hoy
    operaciones_hoy = Venta.query.filter(
        Venta.empresa_id == empresa_id,
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).count()

    # Ventas de ayer para comparación
    ayer = hoy - timedelta(days=1)
    inicio_ayer = datetime.combine(ayer, datetime.min.time())
    fin_ayer = datetime.combine(ayer, datetime.max.time())

    ventas_ayer = db.session.query(
        func.coalesce(func.sum(Venta.total), 0)
    ).filter(
        Venta.empresa_id == empresa_id,
        Venta.fecha >= inicio_ayer,
        Venta.fecha <= fin_ayer,
        Venta.estado == 'completada'
    ).scalar()

    # Productos con stock bajo
    productos_bajo_stock = Producto.query.filter(
        Producto.empresa_id == empresa_id,
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo
    ).count()

    # Cuentas por cobrar (clientes con deuda)
    cuentas_por_cobrar = db.session.query(
        func.coalesce(func.sum(Cliente.saldo_cuenta_corriente), 0)
    ).filter(
        Cliente.empresa_id == empresa_id,
        Cliente.saldo_cuenta_corriente > 0,
        Cliente.activo == True
    ).scalar()

    clientes_con_deuda = Cliente.query.filter(
        Cliente.empresa_id == empresa_id,
        Cliente.saldo_cuenta_corriente > 0,
        Cliente.activo == True
    ).count()

    # Calcular variación porcentual
    variacion_ventas = 0
    if ventas_ayer and ventas_ayer > 0:
        variacion_ventas = ((ventas_hoy - ventas_ayer) / ventas_ayer) * 100

    # Alertas recientes (productos con stock bajo)
    alertas = Producto.query.filter(
        Producto.empresa_id == empresa_id,
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo
    ).order_by(Producto.stock_actual).limit(5).all()

    # Ventas de los últimos 7 días para el gráfico (una sola query con GROUP BY)
    inicio_semana = datetime.combine(hoy - timedelta(days=6), datetime.min.time())
    ventas_diarias = (
        db.session.query(
            func.date(Venta.fecha).label('dia'),
            func.coalesce(func.sum(Venta.total), 0).label('total'),
        )
        .filter(
            Venta.empresa_id == empresa_id,
            Venta.fecha >= inicio_semana,
            Venta.fecha <= fin_dia,
            Venta.estado == 'completada',
        )
        .group_by(func.date(Venta.fecha))
        .all()
    )

    # Dict para lookup rápido por fecha
    ventas_por_dia = {str(row.dia): float(row.total) for row in ventas_diarias}

    # Construir array de 7 días (con 0 para días sin ventas)
    ventas_semana = []
    for i in range(6, -1, -1):
        dia = hoy - timedelta(days=i)
        total = ventas_por_dia.get(str(dia), 0)
        ventas_semana.append({
            'fecha': dia.strftime('%a'),
            'total': total,
        })

    return render_template(
        'dashboard/index.html',
        ventas_hoy=ventas_hoy,
        ventas_ayer=ventas_ayer,
        variacion_ventas=variacion_ventas,
        operaciones_hoy=operaciones_hoy,
        productos_bajo_stock=productos_bajo_stock,
        cuentas_por_cobrar=cuentas_por_cobrar,
        clientes_con_deuda=clientes_con_deuda,
        alertas=alertas,
        ventas_semana=ventas_semana,
        fecha_hoy=hoy
    )


@bp.route('/api/stats')
@login_required
def api_stats():
    """API para obtener estadísticas actualizadas (HTMX)."""
    hoy = ahora_argentina().date()
    inicio_dia = datetime.combine(hoy, datetime.min.time())
    fin_dia = datetime.combine(hoy, datetime.max.time())

    empresa_id = current_user.empresa_id

    ventas_hoy = db.session.query(
        func.coalesce(func.sum(Venta.total), 0)
    ).filter(
        Venta.empresa_id == empresa_id,
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).scalar()

    operaciones_hoy = Venta.query.filter(
        Venta.empresa_id == empresa_id,
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).count()

    return jsonify({
        'ventas_hoy': float(ventas_hoy),
        'operaciones_hoy': operaciones_hoy
    })
