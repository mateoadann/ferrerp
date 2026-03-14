"""Excepciones para integración con ARCA (ex-AFIP)."""


class ArcaError(Exception):
    """Error base para todas las excepciones de ARCA."""

    def __init__(self, mensaje, codigo=None, detalle=None):
        self.mensaje = mensaje
        self.codigo = codigo
        self.detalle = detalle
        super().__init__(mensaje)


class ArcaAuthError(ArcaError):
    """Error de autenticación con WSAA (certificado, token, etc.)."""

    pass


class ArcaValidationError(ArcaError):
    """
    Error de validación de datos antes de enviar a ARCA.
    Estos errores NUNCA deben reintentarse — los datos son incorrectos.
    """

    pass


class ArcaNetworkError(ArcaError):
    """Error de red/comunicación con los servicios de ARCA."""

    def __init__(self, mensaje, codigo=None, detalle=None, reintentable=True):
        super().__init__(mensaje, codigo, detalle)
        self.reintentable = reintentable


class ArcaRechazoError(ArcaError):
    """
    ARCA rechazó el comprobante (Resultado='R').
    Contiene los errores y observaciones devueltos por el servicio.
    """

    def __init__(self, mensaje, codigo=None, detalle=None, errores=None, observaciones=None):
        super().__init__(mensaje, codigo, detalle)
        self.errores = errores or []
        self.observaciones = observaciones or []
