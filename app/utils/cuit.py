"""Validación de CUIT argentino (módulo 11)."""

import re

from wtforms.validators import ValidationError

# Prefijos válidos de CUIT/CUIL
# 20, 23, 24, 27: personas físicas
# 30, 33, 34: personas jurídicas
PREFIJOS_VALIDOS = {20, 23, 24, 27, 30, 33, 34}

# Pesos para el algoritmo módulo 11
PESOS_MODULO_11 = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]


def limpiar_cuit(cuit: str) -> str:
    """Remueve guiones y espacios de un CUIT, devuelve solo dígitos."""
    return re.sub(r'[\s\-]', '', cuit.strip())


def formatear_cuit(cuit: str) -> str:
    """Formatea un CUIT a XX-XXXXXXXX-X.

    Si el valor no tiene 11 dígitos, devuelve el original sin modificar.
    """
    digitos = limpiar_cuit(cuit)
    if len(digitos) != 11 or not digitos.isdigit():
        return cuit
    return f'{digitos[:2]}-{digitos[2:10]}-{digitos[10]}'


def validar_cuit(cuit: str) -> tuple[bool, str]:
    """Valida un CUIT argentino usando el algoritmo módulo 11.

    Acepta formatos: XX-XXXXXXXX-X, XXXXXXXXXXX (11 dígitos).

    Args:
        cuit: Cadena con el CUIT a validar.

    Returns:
        tuple: (es_valido, mensaje_error). Si es válido, mensaje_error es cadena vacía.
    """
    if not cuit or not cuit.strip():
        return False, 'El CUIT es requerido'

    digitos = limpiar_cuit(cuit)

    if not digitos.isdigit():
        return False, 'El CUIT solo debe contener números y guiones'

    if len(digitos) != 11:
        return False, 'El CUIT debe tener exactamente 11 dígitos'

    prefijo = int(digitos[:2])
    if prefijo not in PREFIJOS_VALIDOS:
        return (
            False,
            f'Prefijo de CUIT inválido ({prefijo}). '
            f'Valores permitidos: {", ".join(str(p) for p in sorted(PREFIJOS_VALIDOS))}',
        )

    # Algoritmo módulo 11
    suma = sum(int(digitos[i]) * PESOS_MODULO_11[i] for i in range(10))
    resto = suma % 11
    verificador_calculado = 11 - resto

    if verificador_calculado == 11:
        verificador_calculado = 0
    elif verificador_calculado == 10:
        # Cuando el resultado es 10, el dígito verificador debería ser 9
        # pero algunos consideran el CUIT inválido. Aceptamos 9 como
        # verificador en este caso (comportamiento estándar ARCA/AFIP).
        verificador_calculado = 9

    digito_verificador = int(digitos[10])

    if digito_verificador != verificador_calculado:
        return (
            False,
            f'Dígito verificador inválido. '
            f'Se esperaba {verificador_calculado}, se recibió {digito_verificador}',
        )

    return True, ''


def cuit_valido(form, field):
    """Validador WTForms para CUIT.

    Valida el CUIT usando el algoritmo módulo 11. Solo valida si el campo
    tiene datos (para campos opcionales, combiná con Optional()).
    """
    if field.data:
        es_valido, mensaje = validar_cuit(field.data)
        if not es_valido:
            raise ValidationError(mensaje)
