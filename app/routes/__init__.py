"""
Blueprints de la aplicación FerrERP.
"""

from .auth import bp as auth_bp
from .caja import bp as caja_bp
from .clientes import bp as clientes_bp
from .compras import bp as compras_bp
from .configuracion import bp as configuracion_bp
from .dashboard import bp as dashboard_bp
from .facturacion import bp as facturacion_bp
from .inventario import bp as inventario_bp
from .presupuestos import bp as presupuestos_bp
from .productos import bp as productos_bp
from .proveedores import bp as proveedores_bp
from .reportes import bp as reportes_bp
from .superadmin import bp as superadmin_bp
from .tiendanube import bp as tiendanube_bp
from .ventas import bp as ventas_bp

__all__ = [
    'auth_bp',
    'dashboard_bp',
    'productos_bp',
    'inventario_bp',
    'proveedores_bp',
    'compras_bp',
    'clientes_bp',
    'ventas_bp',
    'presupuestos_bp',
    'caja_bp',
    'reportes_bp',
    'configuracion_bp',
    'facturacion_bp',
    'superadmin_bp',
    'tiendanube_bp',
]
