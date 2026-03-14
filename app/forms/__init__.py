"""Formularios de la aplicación."""

from .auth_forms import LoginForm
from .caja_forms import AperturaCajaForm, CierreCajaForm, EgresoCajaForm
from .cliente_forms import ClienteForm
from .configuracion_forms import ConfiguracionArcaForm, ConfiguracionForm
from .facturador_forms import FacturadorForm
from .producto_forms import CategoriaForm, ProductoForm
from .proveedor_forms import ProveedorForm
from .usuario_forms import UsuarioEditForm, UsuarioForm
from .venta_forms import VentaForm

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
    'ConfiguracionForm',
    'ConfiguracionArcaForm',
    'FacturadorForm',
]
