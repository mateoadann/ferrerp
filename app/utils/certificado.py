"""Utilidades para extraer información de certificados X.509."""

import logging

from cryptography import x509
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def _extraer_cn(nombre):
    """Extrae el Common Name (CN) de un x509.Name, o retorna el string completo."""
    try:
        attrs = nombre.get_attributes_for_oid(NameOID.COMMON_NAME)
        if attrs:
            return attrs[0].value
    except Exception:
        pass
    # Fallback: representación completa del nombre
    return nombre.rfc4514_string()


def _cargar_certificado(cert_data):
    """Intenta cargar un certificado en formato PEM o DER.

    Args:
        cert_data: bytes del certificado.

    Returns:
        Objeto x509.Certificate.

    Raises:
        ValueError: si no se puede parsear el certificado.
    """
    # Intentar PEM primero (los .crt de ARCA suelen ser PEM)
    try:
        return x509.load_pem_x509_certificate(cert_data)
    except Exception:
        pass

    # Intentar DER
    try:
        return x509.load_der_x509_certificate(cert_data)
    except Exception:
        pass

    raise ValueError(
        'No se pudo parsear el certificado. '
        'Verificá que sea un archivo .crt válido en formato PEM o DER.'
    )


def extraer_info_certificado(cert_data):
    """Extrae información de un certificado X.509.

    Acepta certificados en formato PEM o DER.

    Args:
        cert_data: bytes con el contenido del certificado.

    Returns:
        dict con las claves:
            - vencimiento (datetime): fecha de expiración del certificado
            - emisor (str): Common Name del emisor
            - sujeto (str): Common Name del sujeto
            - numero_serie (str): número de serie en hexadecimal
            - valido_desde (datetime): fecha desde la cual es válido

    Raises:
        ValueError: si cert_data no es un certificado válido.
    """
    if not cert_data:
        raise ValueError('No se proporcionaron datos del certificado.')

    cert = _cargar_certificado(cert_data)

    return {
        'vencimiento': cert.not_valid_after_utc.replace(tzinfo=None),
        'emisor': _extraer_cn(cert.issuer),
        'sujeto': _extraer_cn(cert.subject),
        'numero_serie': format(cert.serial_number, 'X'),
        'valido_desde': cert.not_valid_before_utc.replace(tzinfo=None),
    }
