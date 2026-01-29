from datetime import datetime, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Presupuesto, PresupuestoDetalle, Producto, Usuario


def _crear_usuario():
    usuario = Usuario(
        email='presupuesto@ferrerp.test',
        nombre='Usuario Presupuesto',
        rol='vendedor',
        activo=True,
    )
    usuario.set_password('clave')
    return usuario


def _crear_producto():
    return Producto(
        codigo='PRD-PRE',
        nombre='Producto Presupuesto',
        unidad_medida='unidad',
        precio_costo=Decimal('5.00'),
        precio_venta=Decimal('10.00'),
        stock_actual=Decimal('20.000'),
        stock_minimo=Decimal('1.000'),
        activo=True,
    )


def test_presupuesto_totales_y_estado(app):
    usuario = _crear_usuario()
    producto = _crear_producto()
    db.session.add_all([usuario, producto])
    db.session.commit()

    fecha = datetime.utcnow()
    presupuesto = Presupuesto(
        numero=1,
        fecha=fecha,
        fecha_vencimiento=fecha + timedelta(days=10),
        usuario_id=usuario.id,
        cliente_nombre='Cliente Presupuesto',
        descuento_porcentaje=Decimal('10.00'),
    )

    detalle = PresupuestoDetalle(
        producto_id=producto.id,
        cantidad=Decimal('3.000'),
        precio_unitario=Decimal('10.00'),
        subtotal=Decimal('0.00'),
    )
    detalle.calcular_subtotal()
    presupuesto.detalles.append(detalle)

    db.session.add(presupuesto)
    db.session.commit()

    total = presupuesto.calcular_totales()
    assert total == Decimal('27.00')
    assert presupuesto.estado_display == 'Pendiente'
    assert presupuesto.nombre_cliente_display == 'Cliente Presupuesto'
    assert presupuesto.esta_vencido is False
    assert presupuesto.puede_aceptar is True
    assert presupuesto.puede_editar is True
    assert presupuesto.puede_convertir is False
    assert presupuesto.token
