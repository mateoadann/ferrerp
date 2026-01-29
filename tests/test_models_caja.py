from decimal import Decimal

from app.extensions import db
from app.models import Caja, MovimientoCaja, Usuario


def _crear_usuario():
    usuario = Usuario(
        email='caja@ferrerp.test',
        nombre='Usuario Caja',
        rol='administrador',
        activo=True,
    )
    usuario.set_password('clave')
    return usuario


def test_caja_totales_y_cierre(app):
    usuario = _crear_usuario()
    db.session.add(usuario)
    db.session.commit()

    caja = Caja(
        usuario_apertura_id=usuario.id,
        monto_inicial=Decimal('100.00'),
    )
    db.session.add(caja)
    db.session.commit()

    ingreso = MovimientoCaja(
        caja_id=caja.id,
        tipo='ingreso',
        concepto='venta',
        monto=Decimal('50.00'),
        forma_pago='efectivo',
        usuario_id=usuario.id,
    )
    egreso = MovimientoCaja(
        caja_id=caja.id,
        tipo='egreso',
        concepto='gasto',
        monto=Decimal('20.00'),
        forma_pago='efectivo',
        usuario_id=usuario.id,
    )
    ingreso_tarjeta = MovimientoCaja(
        caja_id=caja.id,
        tipo='ingreso',
        concepto='venta',
        monto=Decimal('15.00'),
        forma_pago='tarjeta_debito',
        usuario_id=usuario.id,
    )
    db.session.add_all([ingreso, egreso, ingreso_tarjeta])
    db.session.commit()

    assert caja.esta_abierta is True
    assert caja.total_ingresos == Decimal('50.00')
    assert caja.total_egresos == Decimal('20.00')

    monto_esperado = caja.calcular_monto_esperado()
    assert monto_esperado == Decimal('130.00')

    caja.cerrar(monto_real=Decimal('125.00'), usuario_cierre_id=usuario.id, observaciones='Cierre')
    assert caja.estado == 'cerrada'
    assert caja.diferencia == Decimal('-5.00')
