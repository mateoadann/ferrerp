"""Formularios de productos y categorías."""

from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, DecimalField,
    BooleanField, SubmitField
)
from wtforms.validators import DataRequired, Length, Optional, NumberRange


class ProductoForm(FlaskForm):
    """Formulario de producto."""

    codigo = StringField(
        'Código',
        validators=[
            DataRequired(message='El código es requerido'),
            Length(max=20, message='El código no puede exceder 20 caracteres')
        ],
        render_kw={'placeholder': 'Ej: PRD-001'}
    )

    codigo_barras = StringField(
        'Código de Barras',
        validators=[
            Optional(),
            Length(max=50, message='El código de barras no puede exceder 50 caracteres')
        ],
        render_kw={'placeholder': 'Escanear o ingresar manualmente'}
    )

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres')
        ],
        render_kw={'placeholder': 'Nombre del producto'}
    )

    descripcion = TextAreaField(
        'Descripción',
        validators=[Optional()],
        render_kw={'placeholder': 'Descripción detallada del producto', 'rows': 3}
    )

    categoria_id = SelectField(
        'Categoría',
        coerce=int,
        validators=[Optional()]
    )

    unidad_medida = SelectField(
        'Unidad de Medida',
        choices=[
            ('unidad', 'Unidad'),
            ('metro', 'Metro'),
            ('kilo', 'Kilogramo'),
            ('litro', 'Litro'),
            ('par', 'Par')
        ],
        default='unidad'
    )

    precio_costo = DecimalField(
        'Precio de Costo',
        validators=[
            DataRequired(message='El precio de costo es requerido'),
            NumberRange(min=0, message='El precio debe ser mayor o igual a 0')
        ],
        places=2,
        render_kw={'placeholder': '0.00', 'step': '0.01'}
    )

    precio_venta = DecimalField(
        'Precio de Venta',
        validators=[
            DataRequired(message='El precio de venta es requerido'),
            NumberRange(min=0, message='El precio debe ser mayor o igual a 0')
        ],
        places=2,
        render_kw={'placeholder': '0.00', 'step': '0.01'}
    )

    stock_actual = DecimalField(
        'Stock Actual',
        validators=[
            Optional(),
            NumberRange(min=0, message='El stock no puede ser negativo')
        ],
        places=3,
        default=0,
        render_kw={'placeholder': '0'}
    )

    stock_minimo = DecimalField(
        'Stock Mínimo',
        validators=[
            Optional(),
            NumberRange(min=0, message='El stock mínimo no puede ser negativo')
        ],
        places=3,
        default=0,
        render_kw={'placeholder': '0'}
    )

    proveedor_id = SelectField(
        'Proveedor',
        coerce=int,
        validators=[Optional()]
    )

    ubicacion = StringField(
        'Ubicación',
        validators=[
            Optional(),
            Length(max=50, message='La ubicación no puede exceder 50 caracteres')
        ],
        render_kw={'placeholder': 'Ej: Estante A-3'}
    )

    activo = BooleanField('Producto activo', default=True)

    submit = SubmitField('Guardar Producto')

    def __init__(self, *args, **kwargs):
        super(ProductoForm, self).__init__(*args, **kwargs)
        self._cargar_opciones()

    def _cargar_opciones(self):
        """Carga las opciones de categorías y proveedores."""
        from ..models import Categoria, Proveedor

        # Categorías
        categorias = Categoria.query.filter_by(activa=True).order_by(Categoria.nombre).all()
        self.categoria_id.choices = [(0, 'Sin categoría')] + [
            (c.id, c.nombre) for c in categorias
        ]

        # Proveedores
        proveedores = Proveedor.query.filter_by(activo=True).order_by(Proveedor.nombre).all()
        self.proveedor_id.choices = [(0, 'Sin proveedor')] + [
            (p.id, p.nombre) for p in proveedores
        ]


class CategoriaForm(FlaskForm):
    """Formulario de categoría."""

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=50, message='El nombre no puede exceder 50 caracteres')
        ],
        render_kw={'placeholder': 'Nombre de la categoría'}
    )

    descripcion = StringField(
        'Descripción',
        validators=[
            Optional(),
            Length(max=200, message='La descripción no puede exceder 200 caracteres')
        ],
        render_kw={'placeholder': 'Descripción breve'}
    )

    activa = BooleanField('Categoría activa', default=True)

    submit = SubmitField('Guardar Categoría')


class AjusteStockForm(FlaskForm):
    """Formulario de ajuste de stock."""

    producto_id = SelectField(
        'Producto',
        coerce=int,
        validators=[DataRequired(message='Selecciona un producto')]
    )

    tipo_ajuste = SelectField(
        'Tipo de Ajuste',
        choices=[
            ('ajuste_positivo', 'Aumentar Stock'),
            ('ajuste_negativo', 'Disminuir Stock')
        ]
    )

    cantidad = DecimalField(
        'Cantidad',
        validators=[
            DataRequired(message='La cantidad es requerida'),
            NumberRange(min=0.001, message='La cantidad debe ser mayor a 0')
        ],
        places=3,
        render_kw={'placeholder': '0', 'step': '0.001'}
    )

    motivo = TextAreaField(
        'Motivo del Ajuste',
        validators=[
            DataRequired(message='El motivo es requerido'),
            Length(max=500, message='El motivo no puede exceder 500 caracteres')
        ],
        render_kw={'placeholder': 'Explica el motivo del ajuste', 'rows': 3}
    )

    submit = SubmitField('Realizar Ajuste')

    def __init__(self, *args, **kwargs):
        super(AjusteStockForm, self).__init__(*args, **kwargs)
        self._cargar_productos()

    def _cargar_productos(self):
        """Carga las opciones de productos."""
        from ..models import Producto

        productos = Producto.query.filter_by(activo=True).order_by(Producto.nombre).all()
        self.producto_id.choices = [(0, 'Seleccionar producto...')] + [
            (p.id, f'{p.codigo} - {p.nombre}') for p in productos
        ]
