"""Tests de validación de CUIT argentino (módulo 11)."""

import pytest
from werkzeug.datastructures import MultiDict

from app.forms.configuracion_forms import ConfiguracionArcaForm, ConfiguracionForm
from app.forms.facturador_forms import FacturadorForm
from app.utils.cuit import cuit_valido, formatear_cuit, limpiar_cuit, validar_cuit

# --------------------------------------------------------------------------
# Tests de limpiar_cuit
# --------------------------------------------------------------------------


class TestLimpiarCuit:
    """Tests de limpieza de CUIT."""

    def test_remueve_guiones(self):
        """Remueve guiones del CUIT."""
        assert limpiar_cuit('20-27964483-3') == '20279644833'

    def test_remueve_espacios(self):
        """Remueve espacios del CUIT."""
        assert limpiar_cuit('20 27964483 3') == '20279644833'

    def test_remueve_guiones_y_espacios(self):
        """Remueve tanto guiones como espacios."""
        assert limpiar_cuit(' 20-27964483-3 ') == '20279644833'

    def test_solo_digitos_sin_cambio(self):
        """Cadena con solo dígitos no cambia."""
        assert limpiar_cuit('20279644833') == '20279644833'

    def test_cadena_vacia(self):
        """Cadena vacía retorna cadena vacía."""
        assert limpiar_cuit('') == ''


# --------------------------------------------------------------------------
# Tests de formatear_cuit
# --------------------------------------------------------------------------


class TestFormatearCuit:
    """Tests de formateo de CUIT."""

    def test_formatea_11_digitos(self):
        """Formatea 11 dígitos al patrón XX-XXXXXXXX-X."""
        assert formatear_cuit('20279644833') == '20-27964483-3'

    def test_formatea_con_guiones_existentes(self):
        """CUIT ya formateado se re-formatea correctamente."""
        assert formatear_cuit('20-27964483-3') == '20-27964483-3'

    def test_no_formatea_largo_incorrecto(self):
        """CUIT con largo incorrecto se devuelve sin modificar."""
        assert formatear_cuit('1234567') == '1234567'

    def test_no_formatea_con_letras(self):
        """CUIT con letras se devuelve sin modificar."""
        assert formatear_cuit('20-abc12345-1') == '20-abc12345-1'

    def test_formatea_con_espacios(self):
        """Limpia espacios antes de formatear."""
        assert formatear_cuit('33 69345023 9') == '33-69345023-9'


# --------------------------------------------------------------------------
# Tests de validar_cuit: CUITs válidos
# --------------------------------------------------------------------------


class TestValidarCuitValidos:
    """Tests con CUITs válidos conocidos."""

    def test_cuit_afip(self):
        """CUIT de AFIP/ARCA es válido."""
        es_valido, mensaje = validar_cuit('33-69345023-9')
        assert es_valido is True
        assert mensaje == ''

    def test_cuit_persona_fisica_20(self):
        """CUIT prefijo 20 (persona física masculino)."""
        es_valido, _ = validar_cuit('20-27964483-3')
        assert es_valido is True

    def test_cuit_persona_fisica_23(self):
        """CUIT prefijo 23 (persona física masculino alternativo)."""
        es_valido, _ = validar_cuit('23-27964483-2')
        assert es_valido is True

    def test_cuit_persona_fisica_27(self):
        """CUIT prefijo 27 (persona física femenino)."""
        es_valido, _ = validar_cuit('27-27964483-8')
        assert es_valido is True

    def test_cuit_persona_juridica_30(self):
        """CUIT prefijo 30 (persona jurídica)."""
        es_valido, _ = validar_cuit('30-27964483-9')
        assert es_valido is True

    def test_cuit_persona_juridica_33(self):
        """CUIT prefijo 33 (persona jurídica)."""
        es_valido, _ = validar_cuit('33-12345678-0')
        assert es_valido is True

    def test_cuit_persona_juridica_34(self):
        """CUIT prefijo 34 (persona jurídica)."""
        es_valido, _ = validar_cuit('34-12345678-7')
        assert es_valido is True

    def test_cuit_prefijo_24(self):
        """CUIT prefijo 24 (persona física)."""
        es_valido, _ = validar_cuit('24-12345678-1')
        assert es_valido is True

    def test_cuit_sin_guiones(self):
        """CUIT válido sin guiones."""
        es_valido, _ = validar_cuit('33693450239')
        assert es_valido is True

    def test_cuit_con_espacios(self):
        """CUIT válido con espacios en lugar de guiones."""
        es_valido, _ = validar_cuit('33 69345023 9')
        assert es_valido is True

    def test_cuit_con_espacios_extremos(self):
        """CUIT válido con espacios al inicio y final."""
        es_valido, _ = validar_cuit('  20-27964483-3  ')
        assert es_valido is True


# --------------------------------------------------------------------------
# Tests de validar_cuit: CUITs inválidos
# --------------------------------------------------------------------------


class TestValidarCuitInvalidos:
    """Tests con CUITs inválidos."""

    def test_digito_verificador_incorrecto(self):
        """CUIT con dígito verificador incorrecto."""
        # 20-27964483-3 es válido, probamos con -4
        es_valido, mensaje = validar_cuit('20-27964483-4')
        assert es_valido is False
        assert 'verificador' in mensaje.lower()

    def test_prefijo_invalido_15(self):
        """CUIT con prefijo 15 es inválido."""
        es_valido, mensaje = validar_cuit('15-12345678-0')
        assert es_valido is False
        assert 'prefijo' in mensaje.lower()

    def test_prefijo_invalido_10(self):
        """CUIT con prefijo 10 es inválido."""
        es_valido, mensaje = validar_cuit('10-12345678-0')
        assert es_valido is False
        assert 'prefijo' in mensaje.lower()

    def test_prefijo_invalido_99(self):
        """CUIT con prefijo 99 es inválido."""
        es_valido, mensaje = validar_cuit('99-12345678-0')
        assert es_valido is False
        assert 'prefijo' in mensaje.lower()

    def test_largo_insuficiente(self):
        """CUIT con menos de 11 dígitos."""
        es_valido, mensaje = validar_cuit('20-123456-1')
        assert es_valido is False
        assert '11' in mensaje

    def test_largo_excesivo(self):
        """CUIT con más de 11 dígitos."""
        es_valido, mensaje = validar_cuit('20-123456789-1')
        assert es_valido is False
        assert '11' in mensaje

    def test_contiene_letras(self):
        """CUIT con letras es inválido."""
        es_valido, mensaje = validar_cuit('20-ABCDEFGH-1')
        assert es_valido is False
        assert 'números' in mensaje.lower()

    def test_cadena_vacia(self):
        """CUIT vacío es inválido."""
        es_valido, mensaje = validar_cuit('')
        assert es_valido is False

    def test_solo_espacios(self):
        """CUIT con solo espacios es inválido."""
        es_valido, mensaje = validar_cuit('   ')
        assert es_valido is False

    def test_none_como_string_vacia(self):
        """Cadena vacía retorna inválido."""
        es_valido, _ = validar_cuit('')
        assert es_valido is False

    def test_todos_ceros(self):
        """CUIT con todos ceros es inválido (prefijo 00 no existe)."""
        es_valido, mensaje = validar_cuit('00-00000000-0')
        assert es_valido is False
        assert 'prefijo' in mensaje.lower()


# --------------------------------------------------------------------------
# Tests de edge cases del módulo 11
# --------------------------------------------------------------------------


class TestModulo11EdgeCases:
    """Tests de casos borde del algoritmo módulo 11."""

    def test_resultado_modulo_11_digito_cero(self):
        """Cuando 11 - (suma % 11) == 11, el dígito verificador es 0."""
        # 20-00000006-0: suma % 11 == 0 => verificador = 0
        es_valido, _ = validar_cuit('20-00000006-0')
        assert es_valido is True

    def test_resultado_modulo_11_digito_cero_checkdigit_mal(self):
        """Cuando verificador debería ser 0 pero se pone otro."""
        es_valido, _ = validar_cuit('20-00000006-1')
        assert es_valido is False

    def test_resultado_modulo_10_digito_nueve(self):
        """Cuando 11 - (suma % 11) == 10, el dígito verificador es 9."""
        # 20-00000001-9: suma % 11 == 1 => 11-1=10 => verificador = 9
        es_valido, _ = validar_cuit('20-00000001-9')
        assert es_valido is True

    def test_resultado_modulo_10_digito_nueve_checkdigit_mal(self):
        """Cuando verificador debería ser 9 pero se pone otro."""
        es_valido, _ = validar_cuit('20-00000001-0')
        assert es_valido is False


# --------------------------------------------------------------------------
# Tests del validador WTForms
# --------------------------------------------------------------------------


class TestCuitValidoWTForms:
    """Tests del validador WTForms para CUIT."""

    def test_cuit_valido_no_lanza_error(self, app):
        """CUIT válido no lanza ValidationError."""
        from app.forms.facturador_forms import FacturadorForm

        with app.test_request_context():
            form = FacturadorForm(
                MultiDict(
                    {
                        'nombre': 'Test',
                        'razon_social': 'Test SA',
                        'cuit': '33-69345023-9',
                        'condicion_iva_id': '1',
                        'punto_venta': '1',
                        'ambiente': 'testing',
                    }
                ),
            )
            # Validar solo el campo cuit
            errores_cuit = []
            for validator in form.cuit.validators:
                try:
                    validator(form, form.cuit)
                except Exception as e:
                    errores_cuit.append(str(e))
            assert errores_cuit == []

    def test_cuit_invalido_lanza_validation_error(self, app):
        """CUIT inválido lanza ValidationError."""
        from wtforms.validators import ValidationError as WTFormsValidationError

        from app.forms.facturador_forms import FacturadorForm

        with app.test_request_context():
            form = FacturadorForm(
                MultiDict(
                    {
                        'nombre': 'Test',
                        'razon_social': 'Test SA',
                        'cuit': '20-12345678-0',
                        'condicion_iva_id': '1',
                        'punto_venta': '1',
                        'ambiente': 'testing',
                    }
                ),
            )
            with pytest.raises(WTFormsValidationError):
                cuit_valido(form, form.cuit)

    def test_campo_vacio_no_valida(self, app):
        """Campo vacío no dispara validación de CUIT (para uso con Optional)."""
        from app.forms.configuracion_forms import ConfiguracionArcaForm

        with app.test_request_context():
            form = ConfiguracionArcaForm(
                MultiDict(
                    {
                        'ambiente_arca': 'testing',
                    }
                ),
            )
            # cuit_valido no debería lanzar error si field.data es vacío
            errores_cuit = []
            for validator in form.cuit.validators:
                try:
                    validator(form, form.cuit)
                except Exception as e:
                    errores_cuit.append(str(e))
            # Optional() se encarga del vacío, cuit_valido lo ignora
            assert not any('verificador' in e for e in errores_cuit)


# --------------------------------------------------------------------------
# Tests de integración con formularios
# --------------------------------------------------------------------------


class TestIntegracionFormularios:
    """Tests de integración del validador con formularios reales."""

    def test_facturador_form_cuit_valido(self, app):
        """FacturadorForm acepta CUIT válido."""
        with app.test_request_context():
            form = FacturadorForm(
                MultiDict(
                    {
                        'nombre': 'Sucursal Centro',
                        'razon_social': 'Mi Empresa SA',
                        'cuit': '33-69345023-9',
                        'condicion_iva_id': '1',
                        'punto_venta': '1',
                        'ambiente': 'testing',
                    }
                ),
            )
            assert form.validate(), f'Errores inesperados: {form.errors}'

    def test_facturador_form_cuit_invalido(self, app):
        """FacturadorForm rechaza CUIT inválido."""
        with app.test_request_context():
            form = FacturadorForm(
                MultiDict(
                    {
                        'nombre': 'Sucursal Centro',
                        'razon_social': 'Mi Empresa SA',
                        'cuit': '20-12345678-0',
                        'condicion_iva_id': '1',
                        'punto_venta': '1',
                        'ambiente': 'testing',
                    }
                ),
            )
            assert not form.validate()
            assert 'cuit' in form.errors

    def test_configuracion_arca_form_cuit_valido(self, app):
        """ConfiguracionArcaForm acepta CUIT válido."""
        with app.test_request_context():
            form = ConfiguracionArcaForm(
                MultiDict(
                    {
                        'cuit': '30-27964483-9',
                        'ambiente_arca': 'testing',
                    }
                ),
            )
            assert form.validate(), f'Errores inesperados: {form.errors}'

    def test_configuracion_arca_form_cuit_invalido(self, app):
        """ConfiguracionArcaForm rechaza CUIT con dígito verificador mal."""
        with app.test_request_context():
            form = ConfiguracionArcaForm(
                MultiDict(
                    {
                        'cuit': '30-27964483-0',
                        'ambiente_arca': 'testing',
                    }
                ),
            )
            assert not form.validate()
            assert 'cuit' in form.errors

    def test_configuracion_arca_form_cuit_vacio_es_valido(self, app):
        """ConfiguracionArcaForm acepta CUIT vacío (campo opcional)."""
        with app.test_request_context():
            form = ConfiguracionArcaForm(
                MultiDict(
                    {
                        'ambiente_arca': 'testing',
                    }
                ),
            )
            assert form.validate(), f'Errores inesperados: {form.errors}'

    def test_configuracion_form_cuit_valido(self, app):
        """ConfiguracionForm acepta CUIT válido."""
        with app.test_request_context():
            form = ConfiguracionForm(
                MultiDict(
                    {
                        'nombre_negocio': 'Mi Ferretería',
                        'cuit': '20-27964483-3',
                    }
                ),
            )
            assert form.validate(), f'Errores inesperados: {form.errors}'

    def test_configuracion_form_cuit_invalido(self, app):
        """ConfiguracionForm rechaza CUIT inválido."""
        with app.test_request_context():
            form = ConfiguracionForm(
                MultiDict(
                    {
                        'nombre_negocio': 'Mi Ferretería',
                        'cuit': '20-12345678-0',
                    }
                ),
            )
            assert not form.validate()
            assert 'cuit' in form.errors
