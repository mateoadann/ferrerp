"""
Utilidades de encriptación para datos sensibles.

Usa Fernet (AES-128-CBC con HMAC) del paquete cryptography.
La clave se obtiene de la variable de entorno ENCRYPTION_KEY.
Si no hay clave configurada, los datos se almacenan sin encriptar (modo desarrollo).
"""

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# Prefijo mágico para distinguir datos encriptados de datos en texto plano.
# Permite migración gradual: desencriptar() detecta automáticamente si los
# datos ya están encriptados o son plaintext (backward compatibility).
PREFIJO_ENCRIPTADO = b'ENCRYPTED:'


def obtener_fernet():
    """Obtiene la instancia Fernet. Retorna None si no hay clave configurada."""
    clave = os.environ.get('ENCRYPTION_KEY')
    if not clave:
        return None

    try:
        return Fernet(clave.encode() if isinstance(clave, str) else clave)
    except Exception:
        logger.error(
            'ENCRYPTION_KEY configurada pero inválida. '
            'Generar una nueva con: python -c '
            '"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
        return None


def encriptar(datos):
    """Encripta datos binarios. Si no hay clave, retorna los datos sin cambios.

    Args:
        datos: bytes a encriptar.

    Returns:
        bytes encriptados con prefijo mágico, o los datos originales si no
        hay clave configurada.
    """
    if not datos:
        return datos

    if not isinstance(datos, bytes):
        datos = bytes(datos)

    fernet = obtener_fernet()
    if fernet is None:
        return datos

    # No re-encriptar datos que ya están encriptados
    if datos.startswith(PREFIJO_ENCRIPTADO):
        return datos

    token = fernet.encrypt(datos)
    return PREFIJO_ENCRIPTADO + token


def desencriptar(datos):
    """Desencripta datos binarios. Si no hay clave o los datos no están
    encriptados, retorna los datos sin cambios (backward compatibility).

    Args:
        datos: bytes posiblemente encriptados.

    Returns:
        bytes desencriptados, o los datos originales si no están encriptados.
    """
    if not datos:
        return datos

    if not isinstance(datos, bytes):
        datos = bytes(datos)

    # Si no tiene el prefijo mágico, son datos sin encriptar (migración gradual)
    if not datos.startswith(PREFIJO_ENCRIPTADO):
        return datos

    fernet = obtener_fernet()
    if fernet is None:
        logger.warning(
            'Datos encriptados encontrados pero ENCRYPTION_KEY no está configurada. '
            'No se pueden desencriptar.'
        )
        return datos

    payload = datos[len(PREFIJO_ENCRIPTADO) :]
    try:
        return fernet.decrypt(payload)
    except InvalidToken:
        logger.error('No se pudieron desencriptar los datos. ' 'Posible cambio de ENCRYPTION_KEY.')
        raise


def generar_clave():
    """Genera una nueva clave de encriptación Fernet (para setup inicial).

    Returns:
        str con la clave en base64, lista para usar como ENCRYPTION_KEY.
    """
    return Fernet.generate_key().decode()
