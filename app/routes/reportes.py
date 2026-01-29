"""Rutas de reportes."""

from datetime import datetime, timedelta
from decimal import Decimal
from flask import Blueprint, render_template, request, make_response
from flask_login import login_required
from sqlalchemy import func

from ..extensions import db
from ..models import Venta, VentaDetalle, Producto, Cliente, Categoria
from ..utils.decorators import admin_required

bp = Blueprint('reportes', __name__, url_prefix='/reportes')


@bp.route('/ventas')
@login_required
def ventas():
    """Reporte de ventas."""
    # Fechas por defecto: último mes
    fecha_hasta = datetime.utcnow().date()
    fecha_desde = fecha_hasta - timedelta(days=30)

    # Obtener parámetros
    if request.args.get('fecha_desde'):
        fecha_desde = datetime.strptime(request.args.get('fecha_desde'), '%Y-%m-%d').date()
    if request.args.get('fecha_hasta'):
        fecha_hasta = datetime.strptime(request.args.get('fecha_hasta'), '%Y-%m-%d').date()

    inicio = datetime.combine(fecha_desde, datetime.min.time())
    fin = datetime.combine(fecha_hasta, datetime.max.time())

    # Total de ventas
    total_ventas = db.session.query(
        func.coalesce(func.sum(Venta.total), 0)
    ).filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).scalar()

    # Cantidad de ventas
    cantidad_ventas = Venta.query.filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).count()

    # Ticket promedio
    ticket_promedio = total_ventas / cantidad_ventas if cantidad_ventas > 0 else 0

    # Ventas por día para gráfico
    ventas_por_dia_query = db.session.query(
        func.date(Venta.fecha).label('fecha'),
        func.sum(Venta.total).label('total'),
        func.count(Venta.id).label('cantidad')
    ).filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).group_by(
        func.date(Venta.fecha)
    ).order_by(
        func.date(Venta.fecha)
    ).all()

    # Convertir a lista de diccionarios para JSON
    ventas_por_dia = [
        {
            'fecha': str(row.fecha),
            'total': float(row.total) if row.total else 0,
            'cantidad': row.cantidad
        }
        for row in ventas_por_dia_query
    ]

    # Ventas por forma de pago
    ventas_por_forma_pago_query = db.session.query(
        Venta.forma_pago,
        func.sum(Venta.total).label('total'),
        func.count(Venta.id).label('cantidad')
    ).filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).group_by(
        Venta.forma_pago
    ).all()

    # Convertir a lista de diccionarios
    forma_pago_labels = {
        'efectivo': 'Efectivo',
        'tarjeta_debito': 'Tarjeta Debito',
        'tarjeta_credito': 'Tarjeta Credito',
        'transferencia': 'Transferencia',
        'cuenta_corriente': 'Cuenta Corriente'
    }
    ventas_por_forma_pago = [
        {
            'forma_pago': row.forma_pago,
            'forma_pago_label': forma_pago_labels.get(row.forma_pago, row.forma_pago),
            'total': float(row.total) if row.total else 0,
            'cantidad': row.cantidad
        }
        for row in ventas_por_forma_pago_query
    ]

    # Top 10 productos más vendidos
    productos_mas_vendidos_query = db.session.query(
        Producto.nombre,
        func.sum(VentaDetalle.cantidad).label('cantidad'),
        func.sum(VentaDetalle.subtotal).label('total')
    ).join(
        VentaDetalle, Producto.id == VentaDetalle.producto_id
    ).join(
        Venta, VentaDetalle.venta_id == Venta.id
    ).filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).group_by(
        Producto.id
    ).order_by(
        func.sum(VentaDetalle.subtotal).desc()
    ).limit(10).all()

    # Convertir a lista de diccionarios
    productos_mas_vendidos = [
        {
            'nombre': row.nombre,
            'cantidad': float(row.cantidad) if row.cantidad else 0,
            'total': float(row.total) if row.total else 0
        }
        for row in productos_mas_vendidos_query
    ]

    return render_template(
        'reportes/ventas.html',
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        total_ventas=total_ventas,
        cantidad_ventas=cantidad_ventas,
        ticket_promedio=ticket_promedio,
        ventas_por_dia=ventas_por_dia,
        ventas_por_forma_pago=ventas_por_forma_pago,
        productos_mas_vendidos=productos_mas_vendidos
    )


@bp.route('/stock')
@login_required
def stock():
    """Reporte de stock."""
    # Parámetros
    categoria_id = request.args.get('categoria', 0, type=int)
    solo_bajo_minimo = request.args.get('bajo_minimo', '0') == '1'

    query = Producto.query.filter(Producto.activo == True)

    if categoria_id:
        query = query.filter(Producto.categoria_id == categoria_id)

    if solo_bajo_minimo:
        query = query.filter(Producto.stock_actual < Producto.stock_minimo)

    productos = query.order_by(Producto.nombre).all()

    # Valor total del inventario
    valor_costo = sum(p.stock_actual * p.precio_costo for p in productos)
    valor_venta = sum(p.stock_actual * p.precio_venta for p in productos)

    # Productos bajo mínimo
    bajo_minimo = [p for p in productos if p.stock_bajo]

    # Categorías para filtro
    categorias = Categoria.query.filter_by(activa=True).order_by(Categoria.nombre).all()

    return render_template(
        'reportes/stock.html',
        productos=productos,
        categorias=categorias,
        categoria_id=categoria_id,
        solo_bajo_minimo=solo_bajo_minimo,
        valor_costo=valor_costo,
        valor_venta=valor_venta,
        bajo_minimo=bajo_minimo
    )


@bp.route('/clientes')
@login_required
def clientes():
    """Reporte de clientes."""
    # Clientes con mayor deuda
    clientes_deudores = Cliente.query.filter(
        Cliente.activo == True,
        Cliente.saldo_cuenta_corriente > 0
    ).order_by(
        Cliente.saldo_cuenta_corriente.desc()
    ).limit(20).all()

    # Total de deudas
    total_deudas = sum(c.saldo_cuenta_corriente for c in clientes_deudores)

    # Top clientes por ventas
    top_clientes = db.session.query(
        Cliente.nombre,
        func.sum(Venta.total).label('total_compras'),
        func.count(Venta.id).label('cantidad_compras')
    ).join(
        Venta, Cliente.id == Venta.cliente_id
    ).filter(
        Venta.estado == 'completada'
    ).group_by(
        Cliente.id
    ).order_by(
        func.sum(Venta.total).desc()
    ).limit(20).all()

    return render_template(
        'reportes/clientes.html',
        clientes_deudores=clientes_deudores,
        total_deudas=total_deudas,
        top_clientes=top_clientes
    )


@bp.route('/rentabilidad')
@login_required
@admin_required
def rentabilidad():
    """Reporte de rentabilidad."""
    # Fechas por defecto: último mes
    fecha_hasta = datetime.utcnow().date()
    fecha_desde = fecha_hasta - timedelta(days=30)

    if request.args.get('fecha_desde'):
        fecha_desde = datetime.strptime(request.args.get('fecha_desde'), '%Y-%m-%d').date()
    if request.args.get('fecha_hasta'):
        fecha_hasta = datetime.strptime(request.args.get('fecha_hasta'), '%Y-%m-%d').date()

    inicio = datetime.combine(fecha_desde, datetime.min.time())
    fin = datetime.combine(fecha_hasta, datetime.max.time())

    # Obtener ventas con detalles
    ventas = Venta.query.filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).all()

    # Calcular rentabilidad
    total_ingresos = Decimal('0')
    total_costos = Decimal('0')

    for venta in ventas:
        total_ingresos += venta.total
        for detalle in venta.detalles:
            total_costos += detalle.cantidad * detalle.producto.precio_costo

    ganancia_bruta = total_ingresos - total_costos
    margen = (ganancia_bruta / total_ingresos * 100) if total_ingresos > 0 else 0

    # Rentabilidad por categoría
    rentabilidad_categoria = db.session.query(
        Categoria.nombre,
        func.sum(VentaDetalle.subtotal).label('ingresos'),
        func.sum(VentaDetalle.cantidad * Producto.precio_costo).label('costos')
    ).join(
        Producto, VentaDetalle.producto_id == Producto.id
    ).join(
        Categoria, Producto.categoria_id == Categoria.id
    ).join(
        Venta, VentaDetalle.venta_id == Venta.id
    ).filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin,
        Venta.estado == 'completada'
    ).group_by(
        Categoria.id
    ).all()

    return render_template(
        'reportes/rentabilidad.html',
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        total_ingresos=total_ingresos,
        total_costos=total_costos,
        ganancia_bruta=ganancia_bruta,
        margen=margen,
        rentabilidad_categoria=rentabilidad_categoria
    )


@bp.route('/ventas/exportar')
@login_required
def exportar_ventas():
    """Exportar reporte de ventas a Excel."""
    from openpyxl import Workbook
    from io import BytesIO

    # Fechas
    fecha_hasta = datetime.utcnow().date()
    fecha_desde = fecha_hasta - timedelta(days=30)

    if request.args.get('fecha_desde'):
        fecha_desde = datetime.strptime(request.args.get('fecha_desde'), '%Y-%m-%d').date()
    if request.args.get('fecha_hasta'):
        fecha_hasta = datetime.strptime(request.args.get('fecha_hasta'), '%Y-%m-%d').date()

    inicio = datetime.combine(fecha_desde, datetime.min.time())
    fin = datetime.combine(fecha_hasta, datetime.max.time())

    # Obtener ventas
    ventas = Venta.query.filter(
        Venta.fecha >= inicio,
        Venta.fecha <= fin
    ).order_by(Venta.fecha).all()

    # Crear Excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas"

    # Encabezados
    headers = ['Número', 'Fecha', 'Cliente', 'Forma de Pago', 'Subtotal', 'Descuento', 'Total', 'Estado']
    ws.append(headers)

    # Datos
    for venta in ventas:
        ws.append([
            venta.numero_completo,
            venta.fecha.strftime('%d/%m/%Y %H:%M'),
            venta.cliente.nombre if venta.cliente else 'Consumidor Final',
            venta.forma_pago_display,
            float(venta.subtotal),
            float(venta.descuento_monto),
            float(venta.total),
            venta.estado_display
        ])

    # Guardar a buffer
    output = BytesIO()
    wb.save(output)
    output.seek(0)

    # Respuesta
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=ventas_{fecha_desde}_{fecha_hasta}.xlsx'

    return response
