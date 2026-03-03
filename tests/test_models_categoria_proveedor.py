from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Categoria, Empresa, Producto, Proveedor


def _crear_empresa():
    empresa = Empresa(nombre='Empresa Test', activa=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def test_categoria_cantidad_productos(app):
    empresa = _crear_empresa()
    categoria = Categoria(nombre='Herramientas', activa=True, empresa_id=empresa.id)
    db.session.add(categoria)
    db.session.commit()

    producto_activo = Producto(
        codigo='PRD-CAT-1',
        nombre='Producto Activo',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('1.000'),
        stock_minimo=Decimal('0.000'),
        categoria_id=categoria.id,
        activo=True,
        empresa_id=empresa.id,
    )
    producto_inactivo = Producto(
        codigo='PRD-CAT-2',
        nombre='Producto Inactivo',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('1.000'),
        stock_minimo=Decimal('0.000'),
        categoria_id=categoria.id,
        activo=False,
        empresa_id=empresa.id,
    )
    db.session.add_all([producto_activo, producto_inactivo])
    db.session.commit()

    assert categoria.cantidad_productos == 1


def test_categoria_jerarquia(app):
    empresa = _crear_empresa()
    categoria_padre = Categoria(
        nombre='Herramientas', activa=True, empresa_id=empresa.id
    )
    db.session.add(categoria_padre)
    db.session.flush()

    subcategoria = Categoria(
        nombre='Manuales', activa=True, padre_id=categoria_padre.id,
        empresa_id=empresa.id,
    )
    db.session.add(subcategoria)
    db.session.commit()

    assert categoria_padre.es_padre is True
    assert subcategoria.es_padre is False
    assert subcategoria.padre == categoria_padre
    assert subcategoria.nombre_completo == 'Herramientas > Manuales'


def test_categoria_cantidad_productos_total(app):
    empresa = _crear_empresa()
    categoria_padre = Categoria(
        nombre='Pintureria', activa=True, empresa_id=empresa.id
    )
    db.session.add(categoria_padre)
    db.session.flush()

    subcategoria = Categoria(
        nombre='Rodillos', activa=True, padre_id=categoria_padre.id,
        empresa_id=empresa.id,
    )
    db.session.add(subcategoria)
    db.session.flush()

    producto_padre = Producto(
        codigo='PRD-PADRE-1',
        nombre='Aguarras',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('1.000'),
        stock_minimo=Decimal('0.000'),
        categoria_id=categoria_padre.id,
        activo=True,
        empresa_id=empresa.id,
    )
    producto_hija = Producto(
        codigo='PRD-HIJA-1',
        nombre='Rodillo 22cm',
        unidad_medida='unidad',
        precio_costo=Decimal('1.00'),
        precio_venta=Decimal('2.00'),
        stock_actual=Decimal('1.000'),
        stock_minimo=Decimal('0.000'),
        categoria_id=subcategoria.id,
        activo=True,
        empresa_id=empresa.id,
    )
    db.session.add_all([producto_padre, producto_hija])
    db.session.commit()

    assert categoria_padre.cantidad_productos == 1
    assert categoria_padre.cantidad_productos_total == 2


def test_categoria_nombre_unico_por_nivel(app):
    empresa = _crear_empresa()
    padre_1 = Categoria(nombre='Herramientas', activa=True, empresa_id=empresa.id)
    padre_2 = Categoria(nombre='Pintureria', activa=True, empresa_id=empresa.id)
    db.session.add_all([padre_1, padre_2])
    db.session.flush()

    subcategoria_1 = Categoria(
        nombre='Manuales', activa=True, padre_id=padre_1.id,
        empresa_id=empresa.id,
    )
    db.session.add(subcategoria_1)
    db.session.commit()

    # Mismo nombre, mismo padre, misma empresa -> error
    subcategoria_mismo_nivel = Categoria(
        nombre='Manuales', activa=True, padre_id=padre_1.id,
        empresa_id=empresa.id,
    )
    db.session.add(subcategoria_mismo_nivel)

    with pytest.raises(IntegrityError):
        db.session.commit()

    db.session.rollback()

    # Mismo nombre, otro padre -> ok
    subcategoria_otro_padre = Categoria(
        nombre='Manuales', activa=True, padre_id=padre_2.id,
        empresa_id=empresa.id,
    )
    db.session.add(subcategoria_otro_padre)
    db.session.commit()

    assert subcategoria_otro_padre.id is not None


def test_categoria_mismo_nombre_otra_empresa(app):
    """Categorías con mismo nombre en diferentes empresas no colisionan."""
    empresa_1 = _crear_empresa()
    empresa_2 = Empresa(nombre='Empresa 2', activa=True)
    db.session.add(empresa_2)
    db.session.flush()

    cat_1 = Categoria(nombre='Herramientas', activa=True, empresa_id=empresa_1.id)
    cat_2 = Categoria(nombre='Herramientas', activa=True, empresa_id=empresa_2.id)
    db.session.add_all([cat_1, cat_2])
    db.session.commit()

    assert cat_1.id is not None
    assert cat_2.id is not None
    assert cat_1.id != cat_2.id


def test_proveedor_condicion_pago_display(app):
    empresa = _crear_empresa()
    proveedor = Proveedor(
        nombre='Proveedor Uno', condicion_pago='30_dias', activo=True,
        empresa_id=empresa.id,
    )
    db.session.add(proveedor)
    db.session.commit()

    assert proveedor.condicion_pago_display == '30 días'
