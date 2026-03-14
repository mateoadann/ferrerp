"""Tests para el módulo de encriptación de datos sensibles."""

import os

import pytest
from cryptography.fernet import Fernet

from app.utils.crypto import (
    PREFIJO_ENCRIPTADO,
    desencriptar,
    encriptar,
    generar_clave,
    obtener_fernet,
)


@pytest.fixture(autouse=True)
def _limpiar_env():
    """Limpia ENCRYPTION_KEY antes y después de cada test."""
    original = os.environ.pop('ENCRYPTION_KEY', None)
    yield
    if original is not None:
        os.environ['ENCRYPTION_KEY'] = original
    else:
        os.environ.pop('ENCRYPTION_KEY', None)


@pytest.fixture
def clave_test():
    """Genera y setea una clave válida para tests."""
    clave = Fernet.generate_key().decode()
    os.environ['ENCRYPTION_KEY'] = clave
    return clave


class TestEncriptarDesencriptar:
    """Tests de roundtrip encriptar → desencriptar."""

    def test_roundtrip(self, clave_test):
        """Encriptar y desencriptar produce los datos originales."""
        datos = b'-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----'
        encriptado = encriptar(datos)
        resultado = desencriptar(encriptado)
        assert resultado == datos

    def test_roundtrip_clave_privada(self, clave_test):
        """Funciona con datos de clave privada RSA."""
        datos = b'-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----'
        encriptado = encriptar(datos)
        resultado = desencriptar(encriptado)
        assert resultado == datos

    def test_datos_binarios_grandes(self, clave_test):
        """Funciona con datos binarios grandes como certificados reales."""
        datos = os.urandom(8192)  # 8KB, tamaño típico de un cert
        encriptado = encriptar(datos)
        resultado = desencriptar(encriptado)
        assert resultado == datos
        assert len(encriptado) > len(datos)  # El encriptado es más grande


class TestPassthrough:
    """Tests de modo passthrough (sin ENCRYPTION_KEY)."""

    def test_encriptar_sin_clave_passthrough(self):
        """Sin ENCRYPTION_KEY, los datos pasan sin modificar."""
        datos = b'datos-sensibles-sin-encriptar'
        resultado = encriptar(datos)
        assert resultado == datos

    def test_desencriptar_sin_clave_passthrough(self):
        """Sin ENCRYPTION_KEY, desencriptar retorna los datos sin cambios."""
        datos = b'datos-planos'
        resultado = desencriptar(datos)
        assert resultado == datos

    def test_encriptar_none_retorna_none(self):
        """encriptar(None) retorna None."""
        assert encriptar(None) is None

    def test_desencriptar_none_retorna_none(self):
        """desencriptar(None) retorna None."""
        assert desencriptar(None) is None

    def test_encriptar_bytes_vacios(self):
        """encriptar(b'') retorna b''."""
        assert encriptar(b'') == b''

    def test_desencriptar_bytes_vacios(self):
        """desencriptar(b'') retorna b''."""
        assert desencriptar(b'') == b''


class TestBackwardCompatibility:
    """Tests de compatibilidad con datos existentes sin encriptar."""

    def test_desencriptar_datos_sin_encriptar(self, clave_test):
        """Datos sin prefijo mágico pasan tal cual (migración gradual)."""
        datos_planos = b'-----BEGIN CERTIFICATE-----\ncontenido-legacy\n-----END CERTIFICATE-----'
        resultado = desencriptar(datos_planos)
        assert resultado == datos_planos

    def test_desencriptar_datos_encriptados(self, clave_test):
        """Datos encriptados se desencriptan correctamente."""
        datos = b'contenido-secreto'
        encriptado = encriptar(datos)
        resultado = desencriptar(encriptado)
        assert resultado == datos

    def test_no_doble_encriptacion(self, clave_test):
        """Encriptar datos ya encriptados no los re-encripta."""
        datos = b'contenido-original'
        encriptado1 = encriptar(datos)
        encriptado2 = encriptar(encriptado1)
        assert encriptado1 == encriptado2


class TestPrefijoMagico:
    """Tests del prefijo mágico ENCRYPTED:."""

    def test_prefijo_presente(self, clave_test):
        """Datos encriptados empiezan con el prefijo mágico."""
        datos = b'test-data'
        encriptado = encriptar(datos)
        assert encriptado.startswith(PREFIJO_ENCRIPTADO)

    def test_prefijo_no_presente_sin_clave(self):
        """Sin clave, no se agrega prefijo."""
        datos = b'test-data'
        resultado = encriptar(datos)
        assert not resultado.startswith(PREFIJO_ENCRIPTADO)

    def test_contenido_despues_de_prefijo_es_fernet_token(self, clave_test):
        """El contenido después del prefijo es un token Fernet válido."""
        datos = b'test-data'
        encriptado = encriptar(datos)
        token = encriptado[len(PREFIJO_ENCRIPTADO) :]
        fernet = Fernet(clave_test.encode())
        assert fernet.decrypt(token) == datos


class TestGenerarClave:
    """Tests para generar_clave()."""

    def test_genera_clave_valida(self):
        """Genera una clave Fernet válida."""
        clave = generar_clave()
        assert isinstance(clave, str)
        # Verificar que es una clave Fernet válida creando instancia
        fernet = Fernet(clave.encode())
        assert fernet is not None

    def test_claves_unicas(self):
        """Cada llamada genera una clave diferente."""
        clave1 = generar_clave()
        clave2 = generar_clave()
        assert clave1 != clave2

    def test_clave_base64_url_safe(self):
        """La clave es base64 URL-safe (44 caracteres)."""
        clave = generar_clave()
        assert len(clave) == 44  # Fernet key length in base64


class TestObtenerFernet:
    """Tests para obtener_fernet()."""

    def test_sin_clave_retorna_none(self):
        """Sin ENCRYPTION_KEY retorna None."""
        assert obtener_fernet() is None

    def test_con_clave_valida(self, clave_test):
        """Con clave válida retorna instancia Fernet."""
        fernet = obtener_fernet()
        assert fernet is not None
        assert isinstance(fernet, Fernet)

    def test_con_clave_invalida_retorna_none(self):
        """Con clave inválida retorna None (no explota)."""
        os.environ['ENCRYPTION_KEY'] = 'clave-invalida-no-base64'
        assert obtener_fernet() is None


class TestErrores:
    """Tests de manejo de errores."""

    def test_desencriptar_con_clave_incorrecta(self):
        """Desencriptar con clave diferente lanza InvalidToken."""
        from cryptography.fernet import InvalidToken

        # Encriptar con una clave
        clave1 = Fernet.generate_key().decode()
        os.environ['ENCRYPTION_KEY'] = clave1
        datos = b'datos-secretos'
        encriptado = encriptar(datos)

        # Intentar desencriptar con otra clave
        clave2 = Fernet.generate_key().decode()
        os.environ['ENCRYPTION_KEY'] = clave2
        with pytest.raises(InvalidToken):
            desencriptar(encriptado)

    def test_desencriptar_encriptado_sin_clave_retorna_encriptado(self, clave_test):
        """Si hay datos encriptados pero no hay clave, retorna los datos tal cual."""
        datos = b'datos-originales'
        encriptado = encriptar(datos)

        # Quitar la clave
        del os.environ['ENCRYPTION_KEY']
        resultado = desencriptar(encriptado)
        # Sin clave, retorna los datos encriptados sin modificar
        assert resultado == encriptado
