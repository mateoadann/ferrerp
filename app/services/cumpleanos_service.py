"""Servicio de cumpleaños de clientes."""

from datetime import date
from urllib.parse import quote

from sqlalchemy import extract, func

from ..extensions import db
from ..models import Cliente, Configuracion

TEMPLATE_CUMPLEANOS_DEFAULT = (
    '¡Feliz cumpleaños {cliente}! Te saluda {negocio}. ' '¡Que tengas un gran día!'
)


class SafeDict(dict):
    """Dict que retorna la clave como placeholder si no existe."""

    def __missing__(self, key):
        return '{' + key + '}'


def obtener_cumpleanos_hoy(empresa_id):
    """
    Retorna clientes activos cuyo día y mes de nacimiento coinciden con hoy.

    Soporta PostgreSQL (extract) y SQLite (strftime) de forma transparente.

    Args:
        empresa_id: ID de la empresa para filtrar (multi-tenant)

    Returns:
        Lista de objetos Cliente ordenados por nombre
    """
    hoy = date.today()
    mes_hoy = hoy.month
    dia_hoy = hoy.day

    query = Cliente.query.filter(
        Cliente.empresa_id == empresa_id,
        Cliente.activo.is_(True),
        Cliente.fecha_nacimiento.isnot(None),
    )

    dialecto = db.engine.dialect.name

    if dialecto == 'postgresql':
        query = query.filter(
            extract('month', Cliente.fecha_nacimiento) == mes_hoy,
            extract('day', Cliente.fecha_nacimiento) == dia_hoy,
        )
    else:
        # SQLite
        query = query.filter(
            func.cast(func.strftime('%m', Cliente.fecha_nacimiento), db.Integer) == mes_hoy,
            func.cast(func.strftime('%d', Cliente.fecha_nacimiento), db.Integer) == dia_hoy,
        )

    return query.order_by(Cliente.nombre).all()


def contar_cumpleanos_hoy(empresa_id):
    """
    Cuenta la cantidad de cumpleañeros del día para una empresa.

    Args:
        empresa_id: ID de la empresa

    Returns:
        int con la cantidad de cumpleañeros
    """
    return len(obtener_cumpleanos_hoy(empresa_id))


def generar_url_whatsapp_cumpleanos(cliente, empresa_id):
    """
    Genera URL de WhatsApp con mensaje de cumpleaños personalizado.

    Usa el template configurado en Configuracion (clave 'mensaje_cumpleanos')
    o el template por defecto. Reemplaza variables {cliente} y {negocio}.

    Args:
        cliente: Objeto Cliente
        empresa_id: ID de la empresa para obtener configuración

    Returns:
        URL de wa.me con mensaje encoded, o URL sin teléfono si el cliente
        no tiene número cargado
    """
    template = Configuracion.get(
        'mensaje_cumpleanos',
        default=TEMPLATE_CUMPLEANOS_DEFAULT,
        empresa_id=empresa_id,
    )

    nombre_negocio = Configuracion.get(
        'nombre_negocio',
        default='FerrERP',
        empresa_id=empresa_id,
    )

    # Reemplazo seguro de variables (claves faltantes quedan como placeholder)
    mensaje = template.format_map(
        SafeDict(
            cliente=cliente.nombre,
            negocio=nombre_negocio,
        )
    )

    mensaje_encoded = quote(mensaje)

    # Formatear teléfono
    tel = cliente.telefono or ''
    tel = tel.replace('-', '').replace(' ', '').replace('(', '').replace(')', '')

    if tel and not tel.startswith('+'):
        tel = '54' + tel.lstrip('0')

    if tel:
        return f'https://wa.me/{tel}?text={mensaje_encoded}'
    return f'https://wa.me/?text={mensaje_encoded}'
