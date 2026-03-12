"""Constantes y catálogos para integración con ARCA (ex-AFIP)."""

# Tipos de comprobante
TIPO_COMPROBANTE = {
    1: 'Factura A',
    2: 'Nota de Débito A',
    3: 'Nota de Crédito A',
    6: 'Factura B',
    7: 'Nota de Débito B',
    8: 'Nota de Crédito B',
    11: 'Factura C',
    12: 'Nota de Débito C',
    13: 'Nota de Crédito C',
}

# Clase de comprobante por tipo
CLASE_POR_TIPO = {
    1: 'A',
    2: 'A',
    3: 'A',
    6: 'B',
    7: 'B',
    8: 'B',
    11: 'C',
    12: 'C',
    13: 'C',
}

# Tipos de factura por clase (para seleccionar el tipo base)
FACTURA_POR_CLASE = {'A': 1, 'B': 6, 'C': 11}
NOTA_DEBITO_POR_CLASE = {'A': 2, 'B': 7, 'C': 12}
NOTA_CREDITO_POR_CLASE = {'A': 3, 'B': 8, 'C': 13}

# Alícuotas IVA — mapeo de porcentaje a ID ARCA
ALICUOTA_IVA = {
    '0': 3,  # 0%
    '2.5': 9,  # 2.5%
    '5': 8,  # 5%
    '10.5': 4,  # 10.5%
    '21': 5,  # 21%
    '27': 6,  # 27%
}

# Inverso: ID ARCA a porcentaje
ALICUOTA_IVA_INVERSO = {v: k for k, v in ALICUOTA_IVA.items()}

# Tipo de documento
TIPO_DOCUMENTO = {
    80: 'CUIT',
    86: 'CUIL',
    96: 'DNI',
    99: 'Sin identificar / Otro',
}

# Condición frente al IVA
CONDICION_IVA = {
    1: 'IVA Responsable Inscripto',
    4: 'IVA Sujeto Exento',
    5: 'Consumidor Final',
    6: 'Responsable Monotributo',
    8: 'Proveedor del Exterior',
    9: 'Cliente del Exterior',
    10: 'IVA Liberado',
    11: 'IVA Responsable Inscripto - Agente de Percepción',
}

# Concepto de factura
CONCEPTO = {
    1: 'Productos',
    2: 'Servicios',
    3: 'Productos y Servicios',
}

# Monedas
MONEDA = {
    'PES': 'Pesos Argentinos',
    'DOL': 'Dólares Estadounidenses',
    'EUR': 'Euros',
}

# Estados de factura electrónica
ESTADO_FACTURA = {
    'pendiente': 'Pendiente de autorización',
    'autorizada': 'Autorizada (con CAE)',
    'rechazada': 'Rechazada por ARCA',
    'error': 'Error de comunicación',
}


def determinar_clase_comprobante(condicion_iva_emisor_id, condicion_iva_receptor_id):
    """
    Determina la clase de comprobante (A, B o C) según condición IVA
    del emisor y receptor.

    Args:
        condicion_iva_emisor_id: ID condición IVA del emisor (empresa)
        condicion_iva_receptor_id: ID condición IVA del receptor (cliente)

    Returns:
        str: 'A', 'B' o 'C'

    Raises:
        ValueError: Si la combinación no es válida
    """
    # Emisor Responsable Inscripto (1) o Agente de Percepción (11)
    if condicion_iva_emisor_id in (1, 11):
        if condicion_iva_receptor_id in (1, 11):
            return 'A'  # RI -> RI = Clase A
        elif condicion_iva_receptor_id in (4, 5, 6, 8, 9, 10):
            return 'B'  # RI -> CF/Mono/Exento/Exterior = Clase B
        else:
            raise ValueError(f'Condición IVA del receptor no válida: {condicion_iva_receptor_id}')

    # Emisor Monotributo (6)
    elif condicion_iva_emisor_id == 6:
        return 'C'  # Monotributo siempre emite C

    # Emisor Exento (4)
    elif condicion_iva_emisor_id == 4:
        return 'C'  # Exento emite C

    else:
        raise ValueError(
            f'Condición IVA del emisor no válida para facturación: {condicion_iva_emisor_id}'
        )


def porcentaje_a_alicuota_id(porcentaje):
    """
    Convierte un porcentaje de IVA al ID de alícuota ARCA.

    Args:
        porcentaje: Porcentaje de IVA (ej: 21, 10.5, 0)

    Returns:
        int: ID de alícuota ARCA

    Raises:
        ValueError: Si el porcentaje no tiene alícuota válida
    """
    # Normalizar: quitar decimales innecesarios (21.00 -> '21')
    key = str(porcentaje).rstrip('0').rstrip('.')
    if key == '':
        key = '0'

    alicuota_id = ALICUOTA_IVA.get(key)
    if alicuota_id is None:
        raise ValueError(
            f'Porcentaje de IVA no válido para ARCA: {porcentaje}%. '
            f'Valores válidos: {list(ALICUOTA_IVA.keys())}'
        )
    return alicuota_id


# Ambientes ARCA
AMBIENTE_TESTING = 'testing'
AMBIENTE_PRODUCCION = 'production'

# WSDL URLs
WSDL_WSAA_TESTING = 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL'
WSDL_WSAA_PRODUCCION = 'https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL'
WSDL_WSFE_TESTING = 'https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL'
WSDL_WSFE_PRODUCCION = 'https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL'
WSDL_PADRON_TESTING = 'https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA13?WSDL'
WSDL_PADRON_PRODUCCION = 'https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA13?WSDL'
