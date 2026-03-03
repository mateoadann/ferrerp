"""Formularios de productos y categorías."""

from flask_wtf import FlaskForm
from wtforms import BooleanField, DecimalField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError


class ProductoForm(FlaskForm):
    """Formulario de producto."""

    codigo = StringField(
        'Código',
        validators=[
            DataRequired(message='El código es requerido'),
            Length(max=20, message='El código no puede exceder 20 caracteres'),
        ],
        render_kw={'placeholder': 'Ej: PRD-001'},
    )

    codigo_barras = StringField(
        'Código de Barras',
        validators=[
            Optional(),
            Length(max=50, message='El código de barras no puede exceder 50 caracteres'),
        ],
        render_kw={'placeholder': 'Escanear o ingresar manualmente'},
    )

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=100, message='El nombre no puede exceder 100 caracteres'),
        ],
        render_kw={'placeholder': 'Nombre del producto'},
    )

    descripcion = TextAreaField(
        'Descripción',
        validators=[Optional()],
        render_kw={'placeholder': 'Descripción detallada del producto', 'rows': 3},
    )

    categoria_padre_id = SelectField('Categoría', coerce=int, validators=[Optional()])

    subcategoria_id = SelectField('Subcategoría', coerce=int, validators=[Optional()])

    unidad_medida = SelectField(
        'Unidad de Medida',
        choices=[
            ('unidad', 'Unidad'),
            ('metro', 'Metro'),
            ('kilo', 'Kilogramo'),
            ('litro', 'Litro'),
            ('par', 'Par'),
        ],
        default='unidad',
    )

    precio_costo = DecimalField(
        'Precio de Costo',
        validators=[
            DataRequired(message='El precio de costo es requerido'),
            NumberRange(min=0, message='El precio debe ser mayor o igual a 0'),
        ],
        places=2,
        render_kw={
            'placeholder': '0,00',
            'step': '0.01',
            'data-mask': 'money',
            'inputmode': 'decimal',
        },
    )

    precio_venta = DecimalField(
        'Precio de Venta',
        validators=[
            DataRequired(message='El precio de venta es requerido'),
            NumberRange(min=0, message='El precio debe ser mayor o igual a 0'),
        ],
        places=2,
        render_kw={
            'placeholder': '0,00',
            'step': '0.01',
            'data-mask': 'money',
            'inputmode': 'decimal',
        },
    )

    iva_porcentaje = SelectField(
        'IVA', choices=[('21', '21%'), ('10.5', '10.5%'), ('27', '27%')], default='21'
    )

    stock_actual = DecimalField(
        'Stock Actual',
        validators=[Optional(), NumberRange(min=0, message='El stock no puede ser negativo')],
        places=3,
        default=0,
        render_kw={'placeholder': '0'},
    )

    stock_minimo = DecimalField(
        'Stock Mínimo',
        validators=[
            Optional(),
            NumberRange(min=0, message='El stock mínimo no puede ser negativo'),
        ],
        places=3,
        default=0,
        render_kw={'placeholder': '0'},
    )

    proveedor_id = SelectField('Proveedor', coerce=int, validators=[Optional()])

    ubicacion = StringField(
        'Ubicación',
        validators=[
            Optional(),
            Length(max=50, message='La ubicación no puede exceder 50 caracteres'),
        ],
        render_kw={'placeholder': 'Ej: Estante A-3'},
    )

    activo = BooleanField('Producto activo', default=True)

    submit = SubmitField('Guardar Producto')

    UNIDADES_ENTERAS = ('unidad', 'par')

    def validate_stock_actual(self, field):
        """Valida que el stock sea entero para unidades discretas."""
        if (
            field.data is not None
            and self.unidad_medida.data in self.UNIDADES_ENTERAS
            and field.data != int(field.data)
        ):
            raise ValidationError(
                'El stock debe ser un número entero para esta unidad de medida.'
            )

    def validate_stock_minimo(self, field):
        """Valida que el stock mínimo sea entero para unidades discretas."""
        if (
            field.data is not None
            and self.unidad_medida.data in self.UNIDADES_ENTERAS
            and field.data != int(field.data)
        ):
            raise ValidationError(
                'El stock mínimo debe ser un número entero para esta unidad de medida.'
            )

    def __init__(self, *args, **kwargs):
        super(ProductoForm, self).__init__(*args, **kwargs)
        self._cargar_opciones()

    def _cargar_opciones(self):
        """Carga las opciones de categorías y proveedores filtradas por empresa."""
        from ..models import Categoria, Proveedor

        # Categorías padre
        categorias_padre = (
            Categoria.query_empresa()
            .filter_by(activa=True, padre_id=None)
            .order_by(Categoria.nombre)
            .all()
        )
        self.categoria_padre_id.choices = [(0, 'Sin categoría')] + [
            (c.id, c.nombre) for c in categorias_padre
        ]

        # Subcategorías (todas para validación WTForms)
        subcategorias = (
            Categoria.query_empresa()
            .filter(
                Categoria.activa.is_(True),
                Categoria.padre_id.isnot(None),
            )
            .order_by(Categoria.nombre)
            .all()
        )
        self.subcategoria_id.choices = [(0, 'Sin subcategoría')] + [
            (c.id, c.nombre_completo) for c in subcategorias
        ]

        # Proveedores
        proveedores = (
            Proveedor.query_empresa()
            .filter_by(activo=True)
            .order_by(Proveedor.nombre)
            .all()
        )
        self.proveedor_id.choices = [(0, 'Sin proveedor')] + [
            (p.id, p.nombre) for p in proveedores
        ]


class CategoriaForm(FlaskForm):
    """Formulario de categoría."""

    nombre = StringField(
        'Nombre',
        validators=[
            DataRequired(message='El nombre es requerido'),
            Length(max=50, message='El nombre no puede exceder 50 caracteres'),
        ],
        render_kw={'placeholder': 'Nombre de la categoría'},
    )

    descripcion = StringField(
        'Descripción',
        validators=[
            Optional(),
            Length(max=200, message='La descripción no puede exceder 200 caracteres'),
        ],
        render_kw={'placeholder': 'Descripción breve'},
    )

    padre_id = SelectField('Categoría Padre', coerce=int, validators=[Optional()])

    activa = BooleanField('Categoría activa', default=True)

    submit = SubmitField('Guardar Categoría')

    def __init__(self, *args, **kwargs):
        super(CategoriaForm, self).__init__(*args, **kwargs)
        self._cargar_padres()

    def _cargar_padres(self):
        """Carga categorías padre disponibles filtradas por empresa."""
        from ..models import Categoria

        categorias_padre = (
            Categoria.query_empresa()
            .filter_by(activa=True, padre_id=None)
            .order_by(Categoria.nombre)
            .all()
        )

        self.padre_id.choices = [(0, '-- Es categoría padre --')] + [
            (categoria.id, categoria.nombre) for categoria in categorias_padre
        ]


class AjusteStockForm(FlaskForm):
    """Formulario de ajuste de stock."""

    producto_id = SelectField(
        'Producto', coerce=int, validators=[DataRequired(message='Selecciona un producto')]
    )

    tipo_ajuste = SelectField(
        'Tipo de Ajuste',
        choices=[('ajuste_positivo', 'Aumentar Stock'), ('ajuste_negativo', 'Disminuir Stock')],
    )

    cantidad = DecimalField(
        'Cantidad',
        validators=[
            DataRequired(message='La cantidad es requerida'),
            NumberRange(min=0.001, message='La cantidad debe ser mayor a 0'),
        ],
        places=3,
        render_kw={'placeholder': '0', 'step': '0.001'},
    )

    motivo = TextAreaField(
        'Motivo del Ajuste',
        validators=[
            DataRequired(message='El motivo es requerido'),
            Length(max=500, message='El motivo no puede exceder 500 caracteres'),
        ],
        render_kw={'placeholder': 'Explica el motivo del ajuste', 'rows': 3},
    )

    submit = SubmitField('Realizar Ajuste')

    def __init__(self, *args, **kwargs):
        super(AjusteStockForm, self).__init__(*args, **kwargs)
        self._cargar_productos()

    def _cargar_productos(self):
        """Carga las opciones de productos filtradas por empresa."""
        from ..models import Producto

        productos = (
            Producto.query_empresa()
            .filter_by(activo=True)
            .order_by(Producto.nombre)
            .all()
        )
        self.producto_id.choices = [(0, 'Seleccionar producto...')] + [
            (p.id, f'{p.codigo} - {p.nombre}') for p in productos
        ]
