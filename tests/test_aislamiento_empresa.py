"""Tests de aislamiento multi-tenant para modelos core."""

from decimal import Decimal

from app.extensions import db
from app.models import (
    Categoria,
    Cliente,
    Configuracion,
    Empresa,
    Producto,
    Proveedor,
)


def _crear_empresas():
    """Crea dos empresas de prueba."""
    empresa_1 = Empresa(nombre='Ferretería Norte', activa=True)
    empresa_2 = Empresa(nombre='Ferretería Sur', activa=True)
    db.session.add_all([empresa_1, empresa_2])
    db.session.flush()
    return empresa_1, empresa_2


def test_productos_aislados_por_empresa(app):
    """Productos con mismo código en diferentes empresas no colisionan."""
    emp1, emp2 = _crear_empresas()

    prod_1 = Producto(
        codigo='PRD-001', nombre='Martillo Norte',
        unidad_medida='unidad', precio_costo=Decimal('10'),
        precio_venta=Decimal('20'), stock_actual=Decimal('5'),
        stock_minimo=Decimal('1'), activo=True, empresa_id=emp1.id,
    )
    prod_2 = Producto(
        codigo='PRD-001', nombre='Martillo Sur',
        unidad_medida='unidad', precio_costo=Decimal('12'),
        precio_venta=Decimal('22'), stock_actual=Decimal('3'),
        stock_minimo=Decimal('1'), activo=True, empresa_id=emp2.id,
    )
    db.session.add_all([prod_1, prod_2])
    db.session.commit()

    assert prod_1.id != prod_2.id
    assert prod_1.codigo == prod_2.codigo
    assert prod_1.empresa_id != prod_2.empresa_id


def test_categorias_aisladas_por_empresa(app):
    """Categorías con mismo nombre en diferentes empresas no colisionan."""
    emp1, emp2 = _crear_empresas()

    cat_1 = Categoria(
        nombre='Herramientas', activa=True, empresa_id=emp1.id
    )
    cat_2 = Categoria(
        nombre='Herramientas', activa=True, empresa_id=emp2.id
    )
    db.session.add_all([cat_1, cat_2])
    db.session.commit()

    assert cat_1.id != cat_2.id


def test_clientes_aislados_por_empresa(app):
    """Clientes en diferentes empresas son independientes."""
    emp1, emp2 = _crear_empresas()

    cli_1 = Cliente(
        nombre='Juan Pérez', activo=True, empresa_id=emp1.id,
        limite_credito=Decimal('1000'), saldo_cuenta_corriente=Decimal('0'),
    )
    cli_2 = Cliente(
        nombre='Juan Pérez', activo=True, empresa_id=emp2.id,
        limite_credito=Decimal('2000'), saldo_cuenta_corriente=Decimal('0'),
    )
    db.session.add_all([cli_1, cli_2])
    db.session.commit()

    assert cli_1.id != cli_2.id
    assert cli_1.limite_credito != cli_2.limite_credito


def test_proveedores_aislados_por_empresa(app):
    """Proveedores en diferentes empresas son independientes."""
    emp1, emp2 = _crear_empresas()

    prov_1 = Proveedor(
        nombre='Stanley', activo=True, empresa_id=emp1.id
    )
    prov_2 = Proveedor(
        nombre='Stanley', activo=True, empresa_id=emp2.id
    )
    db.session.add_all([prov_1, prov_2])
    db.session.commit()

    assert prov_1.id != prov_2.id


def test_configuracion_aislada_por_empresa(app):
    """Configuración con misma clave en diferentes empresas no colisionan."""
    emp1, emp2 = _crear_empresas()

    config_1 = Configuracion(
        clave='nombre_negocio', valor='Ferretería Norte',
        tipo='string', empresa_id=emp1.id,
    )
    config_2 = Configuracion(
        clave='nombre_negocio', valor='Ferretería Sur',
        tipo='string', empresa_id=emp2.id,
    )
    db.session.add_all([config_1, config_2])
    db.session.commit()

    assert config_1.id != config_2.id
    assert config_1.get_valor() == 'Ferretería Norte'
    assert config_2.get_valor() == 'Ferretería Sur'


def test_producto_requiere_empresa_id(app):
    """Producto sin empresa_id no se puede crear (NOT NULL)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    prod = Producto(
        codigo='SIN-EMP', nombre='Sin empresa',
        unidad_medida='unidad', precio_costo=Decimal('1'),
        precio_venta=Decimal('2'), stock_actual=Decimal('0'),
        stock_minimo=Decimal('0'), activo=True,
    )
    db.session.add(prod)
    with pytest.raises(IntegrityError):
        db.session.commit()
