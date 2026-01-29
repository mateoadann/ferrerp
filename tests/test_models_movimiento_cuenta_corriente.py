from decimal import Decimal

from app.extensions import db
from app.models import Cliente, MovimientoCuentaCorriente, Usuario


def test_movimiento_cuenta_corriente_props(app):
    usuario = Usuario(
        email='cc@ferrerp.test',
        nombre='Usuario CC',
        rol='administrador',
        activo=True,
    )
    usuario.set_password('clave')
    cliente = Cliente(
        nombre='Cliente CC',
        limite_credito=Decimal('100.00'),
        saldo_cuenta_corriente=Decimal('0.00'),
        activo=True,
    )
    db.session.add_all([usuario, cliente])
    db.session.commit()

    movimiento = MovimientoCuentaCorriente(
        cliente_id=cliente.id,
        tipo='cargo',
        monto=Decimal('25.00'),
        saldo_anterior=Decimal('0.00'),
        saldo_posterior=Decimal('25.00'),
        usuario_id=usuario.id,
    )
    db.session.add(movimiento)
    db.session.commit()

    assert movimiento.tipo_display == 'Cargo'
    assert movimiento.es_cargo is True
    assert movimiento.es_pago is False
