"""Cliente HTTP para la API de Tienda Nube."""

import hashlib
import hmac
import logging
import time

import requests

logger = logging.getLogger(__name__)


class TiendaNubeAPIError(Exception):
    """Error en la comunicación con la API de Tienda Nube."""

    def __init__(self, status_code, message, response_body=None):
        self.status_code = status_code
        self.message = message
        self.response_body = response_body
        super().__init__(str(self))

    def __str__(self):
        return f'TiendaNube API Error {self.status_code}: {self.message}'


class TiendaNubeClient:
    """Cliente HTTP para interactuar con la API REST de Tienda Nube.

    Maneja autenticación, rate limiting, reintentos automáticos
    y verificación HMAC de webhooks.
    """

    MAX_REINTENTOS_5XX = 3

    def __init__(self, store_id, access_token, app_secret=None):
        """Inicializa el cliente con las credenciales de la tienda.

        Args:
            store_id: ID de la tienda en Tienda Nube.
            access_token: Token de acceso OAuth.
            app_secret: Secreto de la app para verificación HMAC (opcional).
        """
        self.base_url = f'https://api.tiendanube.com/v1/{store_id}'
        self.app_secret = app_secret
        self.session = requests.Session()
        self.session.headers.update(
            {
                'Authentication': f'bearer {access_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'FerrERP (soporte@ferrerp.com.ar)',
            }
        )

    def _manejar_rate_limit(self, response):
        """Aplica throttle preventivo si quedan pocas peticiones disponibles."""
        remaining = response.headers.get('x-rate-limit-remaining')
        if remaining is not None:
            try:
                remaining = int(remaining)
            except (ValueError, TypeError):
                return
            logger.debug(
                'Rate limit restante: %d',
                remaining,
            )
            if remaining < 3:
                logger.debug(
                    'Rate limit bajo (%d), esperando 1s preventivo',
                    remaining,
                )
                time.sleep(1)

    def _request(self, method, path, **kwargs):
        """Ejecuta una petición HTTP contra la API con reintentos y rate limiting.

        Args:
            method: Método HTTP (GET, POST, PUT, PATCH, DELETE).
            path: Ruta relativa al base_url (ej. 'products').
            **kwargs: Argumentos adicionales para requests.Session.request.

        Returns:
            requests.Response con status 2xx.

        Raises:
            TiendaNubeAPIError: Si la API responde con un error no recuperable.
            requests.exceptions.RequestException: Si falla la conexión.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"

        # Intento inicial + reintentos por 5xx
        for intento in range(self.MAX_REINTENTOS_5XX):
            response = self.session.request(
                method,
                url,
                timeout=15,
                **kwargs,
            )
            self._manejar_rate_limit(response)

            # 2xx — éxito
            if response.ok:
                return response

            # 429 — rate limited, reintentar una vez
            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                espera = int(retry_after) if retry_after else 2
                logger.warning(
                    'Rate limited (429) en %s %s, esperando %ds',
                    method,
                    path,
                    espera,
                )
                time.sleep(espera)
                response = self.session.request(
                    method,
                    url,
                    timeout=15,
                    **kwargs,
                )
                self._manejar_rate_limit(response)
                if response.ok:
                    return response
                # Si sigue fallando después del reintento, levantar error
                self._raise_api_error(response)

            # 4xx (no 429) — error del cliente, no reintentar
            if 400 <= response.status_code < 500:
                self._raise_api_error(response)

            # 5xx — error del servidor, reintentar con backoff exponencial
            if response.status_code >= 500:
                espera = 2**intento  # 1s, 2s, 4s
                logger.warning(
                    'Error %d en %s %s, reintento %d/%d en %ds',
                    response.status_code,
                    method,
                    path,
                    intento + 1,
                    self.MAX_REINTENTOS_5XX,
                    espera,
                )
                time.sleep(espera)

        # Agotados los reintentos por 5xx
        self._raise_api_error(response)

    def _raise_api_error(self, response):
        """Construye y lanza TiendaNubeAPIError a partir de la respuesta."""
        try:
            body = response.json()
            message = body.get('description', body.get('message', response.text))
        except (ValueError, AttributeError):
            body = response.text
            message = response.text

        raise TiendaNubeAPIError(
            status_code=response.status_code,
            message=message,
            response_body=body,
        )

    # -------------------------------------------------------------------
    # Verificación HMAC para webhooks
    # -------------------------------------------------------------------

    @staticmethod
    def verificar_hmac(payload_body, hmac_header, app_secret):
        """Verifica la firma HMAC de un webhook de Tienda Nube.

        Args:
            payload_body: Cuerpo crudo del webhook (bytes).
            hmac_header: Valor del header de firma enviado por TN.
            app_secret: Secreto de la aplicación.

        Returns:
            True si la firma es válida, False en caso contrario.
        """
        if isinstance(payload_body, str):
            payload_body = payload_body.encode('utf-8')
        if isinstance(app_secret, str):
            app_secret = app_secret.encode('utf-8')

        digest = hmac.new(
            app_secret,
            payload_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(digest, hmac_header)

    # -------------------------------------------------------------------
    # Tienda
    # -------------------------------------------------------------------

    def get_tienda(self):
        """Obtiene la información de la tienda."""
        return self._request('GET', '/store').json()

    # -------------------------------------------------------------------
    # Productos
    # -------------------------------------------------------------------

    def listar_productos(self, page=1, per_page=50):
        """Lista productos de la tienda paginados."""
        return self._request(
            'GET',
            '/products',
            params={'page': page, 'per_page': per_page},
        ).json()

    def obtener_producto(self, product_id):
        """Obtiene un producto por su ID en Tienda Nube."""
        return self._request('GET', f'/products/{product_id}').json()

    def obtener_producto_por_sku(self, sku):
        """Obtiene un producto por su SKU."""
        return self._request('GET', f'/products/sku/{sku}').json()

    def crear_producto(self, data):
        """Crea un nuevo producto en Tienda Nube."""
        return self._request('POST', '/products', json=data).json()

    def actualizar_producto(self, product_id, data):
        """Actualiza un producto existente en Tienda Nube."""
        return self._request(
            'PUT',
            f'/products/{product_id}',
            json=data,
        ).json()

    def eliminar_producto(self, product_id):
        """Elimina un producto de Tienda Nube."""
        return self._request('DELETE', f'/products/{product_id}').json()

    def actualizar_stock_precio(self, data):
        """Actualiza stock y/o precio de productos en lote."""
        return self._request(
            'PATCH',
            '/products/stock-price',
            json=data,
        ).json()

    def actualizar_stock_variante(self, product_id, data):
        """Actualiza el stock de variantes de un producto."""
        return self._request(
            'POST',
            f'/products/{product_id}/variants/stock',
            json=data,
        ).json()

    # -------------------------------------------------------------------
    # Órdenes
    # -------------------------------------------------------------------

    def listar_ordenes(self, **params):
        """Lista órdenes de la tienda con filtros opcionales."""
        return self._request('GET', '/orders', params=params).json()

    def obtener_orden(self, order_id):
        """Obtiene una orden por su ID en Tienda Nube."""
        return self._request('GET', f'/orders/{order_id}').json()

    # -------------------------------------------------------------------
    # Webhooks
    # -------------------------------------------------------------------

    def crear_webhook(self, event, url):
        """Registra un nuevo webhook en Tienda Nube."""
        return self._request(
            'POST',
            '/webhooks',
            json={'event': event, 'url': url},
        ).json()

    def listar_webhooks(self):
        """Lista los webhooks registrados."""
        return self._request('GET', '/webhooks').json()

    def eliminar_webhook(self, webhook_id):
        """Elimina un webhook registrado."""
        return self._request('DELETE', f'/webhooks/{webhook_id}').json()
