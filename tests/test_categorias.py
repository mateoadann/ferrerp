"""Tests de edición y eliminación de categorías."""

from decimal import Decimal

from app.extensions import db
from app.models import Categoria, Empresa, Producto


def _crear_empresa():
    """Helper: crea una empresa de prueba."""
    empresa = Empresa(nombre='Empresa Test', activa=True)
    db.session.add(empresa)
    db.session.flush()
    return empresa


def _crear_categoria(empresa, nombre='Cat Test', padre=None):
    """Helper: crea una categoría de prueba."""
    categoria = Categoria(
        nombre=nombre,
        empresa_id=empresa.id,
        padre_id=padre.id if padre else None,
        activa=True,
    )
    db.session.add(categoria)
    db.session.flush()
    return categoria


def _crear_producto(empresa, categoria, activo=True):
    """Helper: crea un producto asociado a una categoría."""
    producto = Producto(
        codigo=f'PRD-{categoria.id}',
        nombre=f'Producto de {categoria.nombre}',
        unidad_medida='unidad',
        precio_costo=Decimal('100.00'),
        precio_venta=Decimal('150.00'),
        stock_actual=Decimal('10.000'),
        stock_minimo=Decimal('5.000'),
        activo=activo,
        empresa_id=empresa.id,
        categoria_id=categoria.id,
    )
    db.session.add(producto)
    db.session.flush()
    return producto


# --------------------------------------------------------------------------
# Tests de tiene_productos
# --------------------------------------------------------------------------


def test_tiene_productos_sin_productos(app):
    """Categoría sin productos retorna False."""
    empresa = _crear_empresa()
    cat = _crear_categoria(empresa)
    db.session.commit()

    assert cat.tiene_productos is False


def test_tiene_productos_con_producto_activo(app):
    """Categoría con producto activo retorna True."""
    empresa = _crear_empresa()
    cat = _crear_categoria(empresa)
    _crear_producto(empresa, cat, activo=True)
    db.session.commit()

    assert cat.tiene_productos is True


def test_tiene_productos_con_producto_inactivo(app):
    """Categoría con producto inactivo también retorna True."""
    empresa = _crear_empresa()
    cat = _crear_categoria(empresa)
    _crear_producto(empresa, cat, activo=False)
    db.session.commit()

    assert cat.tiene_productos is True


# --------------------------------------------------------------------------
# Tests de puede_eliminarse
# --------------------------------------------------------------------------


def test_puede_eliminarse_sin_productos(app):
    """Categoría sin productos puede eliminarse."""
    empresa = _crear_empresa()
    cat = _crear_categoria(empresa)
    db.session.commit()

    assert cat.puede_eliminarse is True


def test_no_puede_eliminarse_con_productos_activos(app):
    """Categoría con productos activos no puede eliminarse."""
    empresa = _crear_empresa()
    cat = _crear_categoria(empresa)
    _crear_producto(empresa, cat, activo=True)
    db.session.commit()

    assert cat.puede_eliminarse is False


def test_no_puede_eliminarse_con_productos_inactivos(app):
    """Categoría con productos inactivos tampoco puede eliminarse."""
    empresa = _crear_empresa()
    cat = _crear_categoria(empresa)
    _crear_producto(empresa, cat, activo=False)
    db.session.commit()

    assert cat.puede_eliminarse is False


def test_puede_eliminarse_padre_con_subs_vacias(app):
    """Padre con subcategorías vacías puede eliminarse."""
    empresa = _crear_empresa()
    padre = _crear_categoria(empresa, nombre='Padre')
    _crear_categoria(empresa, nombre='Sub 1', padre=padre)
    _crear_categoria(empresa, nombre='Sub 2', padre=padre)
    db.session.commit()

    assert padre.puede_eliminarse is True


def test_no_puede_eliminarse_padre_con_sub_con_productos(app):
    """Padre no puede eliminarse si una subcategoría tiene productos."""
    empresa = _crear_empresa()
    padre = _crear_categoria(empresa, nombre='Padre')
    sub_vacia = _crear_categoria(empresa, nombre='Sub Vacía', padre=padre)
    sub_con_prod = _crear_categoria(empresa, nombre='Sub Con Prod', padre=padre)
    _crear_producto(empresa, sub_con_prod)
    db.session.commit()

    assert sub_vacia.puede_eliminarse is True
    assert sub_con_prod.puede_eliminarse is False
    assert padre.puede_eliminarse is False


def test_puede_eliminarse_subcategoria_sin_productos(app):
    """Subcategoría sin productos puede eliminarse independientemente."""
    empresa = _crear_empresa()
    padre = _crear_categoria(empresa, nombre='Padre')
    sub = _crear_categoria(empresa, nombre='Sub', padre=padre)
    db.session.commit()

    assert sub.puede_eliminarse is True


# --------------------------------------------------------------------------
# Tests de eliminación en cascada (SQLAlchemy)
# --------------------------------------------------------------------------


def test_eliminar_padre_borra_subcategorias(app):
    """Eliminar categoría padre borra sus subcategorías en cascada."""
    empresa = _crear_empresa()
    padre = _crear_categoria(empresa, nombre='Padre')
    sub1 = _crear_categoria(empresa, nombre='Sub 1', padre=padre)
    sub2 = _crear_categoria(empresa, nombre='Sub 2', padre=padre)
    db.session.commit()

    padre_id = padre.id
    sub1_id = sub1.id
    sub2_id = sub2.id

    db.session.delete(padre)
    db.session.commit()

    assert db.session.get(Categoria, padre_id) is None
    assert db.session.get(Categoria, sub1_id) is None
    assert db.session.get(Categoria, sub2_id) is None


def test_eliminar_subcategoria_no_borra_padre(app):
    """Eliminar subcategoría no afecta al padre."""
    empresa = _crear_empresa()
    padre = _crear_categoria(empresa, nombre='Padre')
    sub = _crear_categoria(empresa, nombre='Sub', padre=padre)
    db.session.commit()

    sub_id = sub.id
    padre_id = padre.id

    db.session.delete(sub)
    db.session.commit()

    assert db.session.get(Categoria, sub_id) is None
    assert db.session.get(Categoria, padre_id) is not None
