"""Servicios de ordenes de compra."""

from flask import render_template

from ..models import Configuracion


def generar_pdf(orden):
    """Genera el PDF de la orden de compra usando WeasyPrint."""
    from weasyprint import HTML

    detalles = list(orden.detalles)

    config_negocio = {
        'nombre': Configuracion.get('nombre_negocio', 'FerrERP'),
        'cuit': Configuracion.get('cuit', ''),
        'direccion': Configuracion.get('direccion', ''),
        'telefono': Configuracion.get('telefono', ''),
        'email': Configuracion.get('email', ''),
        'texto_pie': Configuracion.get('orden_compra_texto_pie', ''),
    }

    html_string = render_template(
        'compras/pdf/orden_compra.html',
        orden=orden,
        detalles=detalles,
        config_negocio=config_negocio,
    )

    pdf = HTML(string=html_string).write_pdf()
    return pdf
