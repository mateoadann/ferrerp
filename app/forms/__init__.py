"""Formularios de la aplicación."""

from .auth_forms import LoginForm
from .producto_forms import ProductoForm, CategoriaForm
from .cliente_forms import ClienteForm
from .proveedor_forms import ProveedorForm
from .venta_forms import VentaForm
from .caja_forms import AperturaCajaForm, CierreCajaForm, EgresoCajaForm
from .usuario_forms import UsuarioForm, UsuarioEditForm
from .configuracion_forms import ConfiguracionForm

__all__ = [
    'LoginForm',
    'ProductoForm',
    'CategoriaForm',
    'ClienteForm',
    'ProveedorForm',
    'VentaForm',
    'AperturaCajaForm',
    'CierreCajaForm',
    'EgresoCajaForm',
    'UsuarioForm',
    'UsuarioEditForm',
    'ConfiguracionForm'
]
