"""Servicio de ventas."""

from flask import render_template

from ..models import Configuracion


def generar_pdf(venta, sin_precios=False):
    """Genera el PDF de comprobante de venta usando WeasyPrint."""
    from weasyprint import HTML

    detalles = list(venta.detalles)

    config_negocio = {
        'nombre': Configuracion.get('nombre_negocio', 'FerrERP'),
        'cuit': Configuracion.get('cuit', ''),
        'direccion': Configuracion.get('direccion', ''),
        'telefono': Configuracion.get('telefono', ''),
        'email': Configuracion.get('email', ''),
        'precios_con_iva': Configuracion.get('precios_con_iva', True),
    }

    html_string = render_template(
        'ventas/pdf/venta.html',
        venta=venta,
        detalles=detalles,
        config_negocio=config_negocio,
        sin_precios=sin_precios,
    )

    pdf = HTML(string=html_string).write_pdf()
    return pdf
