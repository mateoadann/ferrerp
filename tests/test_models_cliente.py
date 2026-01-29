from decimal import Decimal

from app.extensions import db
from app.models import Cliente


def test_cliente_credito_y_saldo(app):
    cliente = Cliente(
        nombre='Cliente Prueba',
        limite_credito=Decimal('100.00'),
        saldo_cuenta_corriente=Decimal('20.00'),
        activo=True,
    )
    db.session.add(cliente)
    db.session.commit()

    assert cliente.tiene_deuda is True
    assert cliente.credito_disponible == Decimal('80.00')
    assert cliente.puede_comprar_a_credito(Decimal('70.00')) is True
    assert cliente.puede_comprar_a_credito(Decimal('90.00')) is False

    saldo_anterior, saldo_nuevo = cliente.actualizar_saldo(Decimal('30.00'), 'cargo')
    assert saldo_anterior == Decimal('20.00')
    assert saldo_nuevo == Decimal('50.00')

    saldo_anterior, saldo_nuevo = cliente.actualizar_saldo(Decimal('10.00'), 'pago')
    assert saldo_anterior == Decimal('50.00')
    assert saldo_nuevo == Decimal('40.00')
