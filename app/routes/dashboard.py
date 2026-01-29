"""Rutas del Dashboard."""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from sqlalchemy import func, and_

from ..extensions import db
from ..models import Venta, Producto, Cliente, MovimientoCaja

bp = Blueprint('dashboard', __name__)


@bp.route('/')
@login_required
def index():
    """Página principal del dashboard."""
    # Obtener estadísticas del día
    hoy = datetime.utcnow().date()
    inicio_dia = datetime.combine(hoy, datetime.min.time())
    fin_dia = datetime.combine(hoy, datetime.max.time())

    # Ventas del día
    ventas_hoy = db.session.query(
        func.coalesce(func.sum(Venta.total), 0)
    ).filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).scalar()

    # Cantidad de operaciones hoy
    operaciones_hoy = Venta.query.filter(
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
        Venta.fecha >= inicio_ayer,
        Venta.fecha <= fin_ayer,
        Venta.estado == 'completada'
    ).scalar()

    # Productos con stock bajo
    productos_bajo_stock = Producto.query.filter(
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo
    ).count()

    # Cuentas por cobrar (clientes con deuda)
    cuentas_por_cobrar = db.session.query(
        func.coalesce(func.sum(Cliente.saldo_cuenta_corriente), 0)
    ).filter(
        Cliente.saldo_cuenta_corriente > 0,
        Cliente.activo == True
    ).scalar()

    clientes_con_deuda = Cliente.query.filter(
        Cliente.saldo_cuenta_corriente > 0,
        Cliente.activo == True
    ).count()

    # Calcular variación porcentual
    variacion_ventas = 0
    if ventas_ayer and ventas_ayer > 0:
        variacion_ventas = ((ventas_hoy - ventas_ayer) / ventas_ayer) * 100

    # Alertas recientes (productos con stock bajo)
    alertas = Producto.query.filter(
        Producto.activo == True,
        Producto.stock_actual < Producto.stock_minimo
    ).order_by(Producto.stock_actual).limit(5).all()

    # Ventas de los últimos 7 días para el gráfico
    ventas_semana = []
    for i in range(6, -1, -1):
        fecha = hoy - timedelta(days=i)
        inicio = datetime.combine(fecha, datetime.min.time())
        fin = datetime.combine(fecha, datetime.max.time())

        total = db.session.query(
            func.coalesce(func.sum(Venta.total), 0)
        ).filter(
            Venta.fecha >= inicio,
            Venta.fecha <= fin,
            Venta.estado == 'completada'
        ).scalar()

        ventas_semana.append({
            'fecha': fecha.strftime('%a'),
            'total': float(total)
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
    hoy = datetime.utcnow().date()
    inicio_dia = datetime.combine(hoy, datetime.min.time())
    fin_dia = datetime.combine(hoy, datetime.max.time())

    ventas_hoy = db.session.query(
        func.coalesce(func.sum(Venta.total), 0)
    ).filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).scalar()

    operaciones_hoy = Venta.query.filter(
        Venta.fecha >= inicio_dia,
        Venta.fecha <= fin_dia,
        Venta.estado == 'completada'
    ).count()

    return jsonify({
        'ventas_hoy': float(ventas_hoy),
        'operaciones_hoy': operaciones_hoy
    })
