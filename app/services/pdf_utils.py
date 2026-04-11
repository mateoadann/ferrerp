"""Utilidades compartidas para generacion de PDFs."""

import base64
import os

from flask import current_app

from ..models import Configuracion


def obtener_logo_base64(empresa_id=None):
    """Obtiene el logo de la empresa como data URI base64.

    Args:
        empresa_id: ID de la empresa. Si no se pasa, usa la del usuario actual.

    Returns:
        String con data URI base64 o None si no hay logo.
    """
    logo_filename = Configuracion.get('logo_filename', default='', empresa_id=empresa_id)
    if not logo_filename:
        return None

    logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'logos', logo_filename)
    if not os.path.exists(logo_path):
        return None

    with open(logo_path, 'rb') as f:
        logo_data = f.read()

    ext = logo_filename.rsplit('.', 1)[-1].lower()
    mime = 'image/png' if ext == 'png' else 'image/jpeg'
    return f'data:{mime};base64,{base64.b64encode(logo_data).decode()}'


def obtener_config_negocio(**extras):
    """Obtiene la configuracion del negocio para PDFs, incluyendo logo.

    Args:
        **extras: Campos adicionales para agregar al dict de configuracion.

    Returns:
        Dict con nombre, cuit, direccion, telefono, email, logo_base64 y extras.
    """
    config = {
        'nombre': Configuracion.get('nombre_negocio', 'FerrERP'),
        'cuit': Configuracion.get('cuit', ''),
        'direccion': Configuracion.get('direccion', ''),
        'telefono': Configuracion.get('telefono', ''),
        'email': Configuracion.get('email', ''),
        'logo_base64': obtener_logo_base64(),
    }
    config.update(extras)
    return config
