"""Tests de validación decimal en formularios de productos y ajustes de stock."""

from decimal import Decimal
from unittest.mock import patch

from werkzeug.datastructures import MultiDict

from app.extensions import db
from app.forms.producto_forms import AjusteStockForm, ProductoForm
from app.models import Producto, Usuario


def _crear_usuario(empresa):
    """Helper: crea un usuario administrador para simular current_user."""
    usuario = Usuario(
        email='admin@test.com',
        nombre='Admin Test',
        rol='administrador',
        activo=True,
        empresa_id=empresa.id,
    )
    usuario.set_password('clave123')
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _crear_producto(empresa, unidad_medida='unidad', stock=Decimal('10.000')):
    """Helper: crea un producto de prueba."""
    producto = Producto(
        codigo=f'PRD-{unidad_medida[:3].upper()}',
        nombre=f'Producto {unidad_medida}',
        unidad_medida=unidad_medida,
        precio_costo=Decimal('100.00'),
        precio_venta=Decimal('150.00'),
        stock_actual=stock,
        stock_minimo=Decimal('5.000'),
        activo=True,
        empresa_id=empresa.id,
    )
    db.session.add(producto)
    db.session.commit()
    return producto


def _datos_producto_base(**kwargs):
    """Helper: datos base para un ProductoForm válido."""
    datos = {
        'codigo': 'PRD-001',
        'nombre': 'Producto Test',
        'unidad_medida': 'unidad',
        'precio_costo': '100.00',
        'precio_venta': '150.00',
        'stock_actual': '10',
        'stock_minimo': '5',
        'categoria_padre_id': '0',
        'subcategoria_id': '0',
        'proveedor_id': '0',
        'iva_porcentaje': '21',
        'activo': 'y',
    }
    datos.update(kwargs)
    return MultiDict(datos)


def _datos_ajuste_base(**kwargs):
    """Helper: datos base para un AjusteStockForm válido."""
    datos = {
        'producto_id': '1',
        'tipo_ajuste': 'ajuste_positivo',
        'cantidad': '5',
        'motivo': 'Ajuste de prueba',
    }
    datos.update(kwargs)
    return MultiDict(datos)


# --------------------------------------------------------------------------
# Tests de ProductoForm: validación de stock según unidad de medida
# --------------------------------------------------------------------------


class TestProductoFormStockEntero:
    """Tests de validación de stock para unidades enteras (unidad, par)."""

    def test_stock_entero_valido_para_unidad(self, app, empresa):
        """Stock entero es válido para unidad de medida 'unidad'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='unidad',
                        stock_actual='10',
                        stock_minimo='5',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_stock_entero_valido_para_par(self, app, empresa):
        """Stock entero es válido para unidad de medida 'par'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='par',
                        stock_actual='8',
                        stock_minimo='2',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_stock_decimal_rechazado_para_unidad(self, app, empresa):
        """Stock decimal es rechazado para unidad de medida 'unidad'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='unidad',
                        stock_actual='10.5',
                    )
                )
                assert not form.validate()
                assert 'stock_actual' in form.errors
                assert 'entero' in form.errors['stock_actual'][0].lower()

    def test_stock_minimo_decimal_rechazado_para_unidad(self, app, empresa):
        """Stock mínimo decimal es rechazado para unidad de medida 'unidad'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='unidad',
                        stock_minimo='3.7',
                    )
                )
                assert not form.validate()
                assert 'stock_minimo' in form.errors
                assert 'entero' in form.errors['stock_minimo'][0].lower()

    def test_stock_decimal_rechazado_para_par(self, app, empresa):
        """Stock decimal es rechazado para unidad de medida 'par'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='par',
                        stock_actual='3.5',
                    )
                )
                assert not form.validate()
                assert 'stock_actual' in form.errors

    def test_stock_cero_valido_para_unidad(self, app, empresa):
        """Stock cero es válido para unidades enteras."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='unidad',
                        stock_actual='0',
                        stock_minimo='0',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'


class TestProductoFormStockDecimal:
    """Tests de validación de stock para unidades decimales (kilo, metro, litro)."""

    def test_stock_decimal_valido_para_kilo(self, app, empresa):
        """Stock decimal es válido para unidad de medida 'kilo'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='kilo',
                        stock_actual='5.50',
                        stock_minimo='2.25',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_stock_decimal_valido_para_metro(self, app, empresa):
        """Stock decimal es válido para unidad de medida 'metro'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='metro',
                        stock_actual='12.75',
                        stock_minimo='3.50',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_stock_decimal_valido_para_litro(self, app, empresa):
        """Stock decimal es válido para unidad de medida 'litro'."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='litro',
                        stock_actual='0.75',
                        stock_minimo='0.25',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_stock_entero_valido_para_kilo(self, app, empresa):
        """Stock entero también es válido para unidades decimales."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='kilo',
                        stock_actual='10',
                        stock_minimo='5',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_stock_negativo_rechazado(self, app, empresa):
        """Stock negativo es rechazado sin importar la unidad de medida."""
        usuario = _crear_usuario(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = ProductoForm(
                    _datos_producto_base(
                        unidad_medida='kilo',
                        stock_actual='-1.5',
                    )
                )
                assert not form.validate()
                assert 'stock_actual' in form.errors


# --------------------------------------------------------------------------
# Tests de AjusteStockForm: validación de cantidad
# --------------------------------------------------------------------------


class TestAjusteStockFormCantidad:
    """Tests de validación de cantidad en ajustes de stock."""

    def test_cantidad_positiva_entera_valida(self, app, empresa):
        """Cantidad positiva entera es válida."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        cantidad='5',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_cantidad_positiva_decimal_valida(self, app, empresa):
        """Cantidad positiva decimal es válida."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa, unidad_medida='kilo')
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        cantidad='2.50',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_cantidad_cero_rechazada(self, app, empresa):
        """Cantidad cero es rechazada."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        cantidad='0',
                    )
                )
                assert not form.validate()
                assert 'cantidad' in form.errors

    def test_cantidad_negativa_rechazada(self, app, empresa):
        """Cantidad negativa es rechazada."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        cantidad='-3',
                    )
                )
                assert not form.validate()
                assert 'cantidad' in form.errors

    def test_cantidad_decimal_pequena_valida(self, app, empresa):
        """Cantidad decimal pequeña (ej: 0.01) es válida."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa, unidad_medida='litro')
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        cantidad='0.01',
                    )
                )
                assert form.validate(), f'Errores: {form.errors}'

    def test_cantidad_vacia_rechazada(self, app, empresa):
        """Cantidad vacía es rechazada por DataRequired."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        cantidad='',
                    )
                )
                assert not form.validate()
                assert 'cantidad' in form.errors

    def test_motivo_requerido(self, app, empresa):
        """El motivo del ajuste es requerido."""
        usuario = _crear_usuario(empresa)
        producto = _crear_producto(empresa)
        with app.test_request_context():
            with patch('app.models.mixins.current_user', usuario):
                form = AjusteStockForm(
                    _datos_ajuste_base(
                        producto_id=str(producto.id),
                        motivo='',
                    )
                )
                assert not form.validate()
                assert 'motivo' in form.errors


# --------------------------------------------------------------------------
# Tests del filtro Jinja |stock
# --------------------------------------------------------------------------


class TestFiltroStock:
    """Tests del filtro Jinja |stock para formateo de cantidades."""

    def test_stock_entero_para_unidad(self, app):
        """Unidad de medida 'unidad' muestra sin decimales."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('12.000'), 'unidad') == '12'

    def test_stock_entero_para_par(self, app):
        """Unidad de medida 'par' muestra sin decimales."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('5.000'), 'par') == '5'

    def test_stock_decimal_para_kilo(self, app):
        """Unidad de medida 'kilo' siempre muestra 2 decimales."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('5.500'), 'kilo') == '5.50'

    def test_stock_decimal_para_metro(self, app):
        """Unidad de medida 'metro' siempre muestra 2 decimales."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('12.000'), 'metro') == '12.00'

    def test_stock_decimal_para_litro(self, app):
        """Unidad de medida 'litro' siempre muestra 2 decimales."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('0.750'), 'litro') == '0.75'

    def test_stock_none_retorna_cero(self, app):
        """Valor None retorna '0'."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(None, 'unidad') == '0'
            assert filtro(None, 'kilo') == '0'

    def test_stock_sin_unidad_usa_unidad_por_defecto(self, app):
        """Sin unidad de medida, usa 'unidad' por defecto (entero)."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('7.000')) == '7'

    def test_stock_entero_con_kilo_muestra_dos_decimales(self, app):
        """Valor entero con unidad decimal muestra .00."""
        with app.app_context():
            filtro = app.jinja_env.filters['stock']
            assert filtro(Decimal('10'), 'kilo') == '10.00'
