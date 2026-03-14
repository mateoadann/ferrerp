"""Cliente wrapper para integrar con arca_arg siguiendo flujo documental."""

import fcntl
import os
import re
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

try:
    from zeep.helpers import serialize_object as _zeep_serialize
except ImportError:
    _zeep_serialize = None

from .arca_constants import (
    AMBIENTE_PRODUCCION,
    CONDICION_IVA,
    WSDL_PADRON_PRODUCCION,
    WSDL_PADRON_TESTING,
    WSDL_WSAA_PRODUCCION,
    WSDL_WSAA_TESTING,
    WSDL_WSFE_PRODUCCION,
    WSDL_WSFE_TESTING,
)
from .arca_exceptions import ArcaAuthError, ArcaNetworkError


class ArcaClient:
    """Encapsula configuracion, autenticacion y llamadas WSFE en arca_arg."""

    def __init__(
        self,
        cuit,
        certificado,
        clave_privada,
        ambiente='testing',
        ta_cache_root=None,
        enable_logging=False,
    ):
        self.cuit = self._normalizar_cuit(cuit)
        self.ambiente = (ambiente or 'testing').strip().lower()
        self.enable_logging = bool(enable_logging)
        self._certificado_bytes = certificado
        self._clave_privada_bytes = clave_privada

        self._lock = threading.RLock()
        self._ws_lock_files = {}
        self._wsfe = None
        self._ws_constancia = None
        self._cerrado = False

        self._cert_path = None
        self._key_path = None
        self._tmp_dir = None

        self.ta_cache_root = ta_cache_root or os.path.join(
            tempfile.gettempdir(),
            'ferrerp_arca_ta',
        )
        self.ta_cache_dir = self._resolver_ta_cache_dir(
            self.ta_cache_root,
            self.ambiente,
            self.cuit,
        )

        self._importar_arca_arg()
        self._crear_archivos_temporales()
        self._aplicar_configuracion_global()

    def _importar_arca_arg(self):
        """Importa arca_arg y valida disponibilidad de modulos requeridos."""
        try:
            import arca_arg.auth as arca_auth  # type: ignore
            import arca_arg.settings as arca_settings  # type: ignore
            import arca_arg.webservice as arca_ws  # type: ignore
            from arca_arg.webservice import ArcaWebService  # type: ignore
        except Exception as exc:
            raise ArcaAuthError(
                'No se pudo importar arca_arg. Instale la dependencia para usar ARCA.',
                detalle=str(exc),
            ) from exc

        self._settings = arca_settings
        self._auth = arca_auth
        self._webservice = arca_ws
        self._arca_webservice_cls = ArcaWebService

    @staticmethod
    def _normalizar_cuit(cuit):
        """Elimina caracteres no numericos del CUIT."""
        return re.sub(r'\D+', '', str(cuit or ''))

    @staticmethod
    def _resolver_ta_cache_dir(ta_cache_root, ambiente, cuit):
        """Construye el directorio de cache TA por ambiente y CUIT."""
        base = Path(ta_cache_root).expanduser()
        cache_dir = base / ambiente / cuit
        cache_dir.mkdir(parents=True, exist_ok=True)
        return f'{cache_dir}{os.sep}'

    def _crear_archivos_temporales(self):
        """Genera archivos temporales para certificado y clave privada."""
        self._tmp_dir = tempfile.mkdtemp(prefix='ferrerp_arca_')
        cert_fd, cert_path = tempfile.mkstemp(suffix='.crt', dir=self._tmp_dir)
        key_fd, key_path = tempfile.mkstemp(suffix='.key', dir=self._tmp_dir)

        try:
            with os.fdopen(cert_fd, 'wb') as cert_file:
                cert_file.write(self._certificado_bytes or b'')
            with os.fdopen(key_fd, 'wb') as key_file:
                key_file.write(self._clave_privada_bytes or b'')
        except Exception:
            for path in (cert_path, key_path):
                if path and os.path.exists(path):
                    os.remove(path)
            raise

        self._cert_path = cert_path
        self._key_path = key_path

    @property
    def _es_produccion(self):
        return self.ambiente == AMBIENTE_PRODUCCION

    @property
    def _wsdl_wsaa(self):
        return WSDL_WSAA_PRODUCCION if self._es_produccion else WSDL_WSAA_TESTING

    @property
    def _wsdl_wsfe(self):
        return WSDL_WSFE_PRODUCCION if self._es_produccion else WSDL_WSFE_TESTING

    @property
    def _wsdl_padron(self):
        return WSDL_PADRON_PRODUCCION if self._es_produccion else WSDL_PADRON_TESTING

    @staticmethod
    def _set_attr(modulo, nombre, valor):
        setattr(modulo, nombre, valor)

    def _set_if_exists(self, modulo, nombre, valor):
        if hasattr(modulo, nombre):
            self._set_attr(modulo, nombre, valor)

    def _aplicar_configuracion_global(self):
        """Aplica config requerida por arca_arg en settings/auth/webservice."""
        prod = self._es_produccion

        # Settings (requeridos por docs de arca_arg)
        self._set_attr(self._settings, 'PRIVATE_KEY_PATH', self._key_path)
        self._set_attr(self._settings, 'CERT_PATH', self._cert_path)
        self._set_attr(self._settings, 'TA_FILES_PATH', self.ta_cache_dir)
        self._set_attr(self._settings, 'CUIT', self.cuit)
        self._set_attr(self._settings, 'PROD', prod)
        self._set_if_exists(self._settings, 'WSDL_WSAA', self._wsdl_wsaa)
        self._set_if_exists(self._settings, 'WSDL_WSFE', self._wsdl_wsfe)
        self._set_if_exists(self._settings, 'WSDL_PADRON', self._wsdl_padron)
        self._set_if_exists(
            self._settings,
            'WSDL_WS_SR_CONSTANCIA_INSCRIPCION',
            self._wsdl_padron,
        )

        # Compatibilidad adicional
        self._set_if_exists(self._settings, 'CERT', self._cert_path)
        self._set_if_exists(self._settings, 'PRIVATE_KEY', self._key_path)
        self._set_if_exists(self._settings, 'KEY_PATH', self._key_path)
        self._set_if_exists(self._settings, 'TA_CACHE_DIR', self.ta_cache_dir)

        # Mirror a auth.* según requerimiento
        self._set_attr(self._auth, 'PRIVATE_KEY_PATH', self._key_path)
        self._set_attr(self._auth, 'CERT_PATH', self._cert_path)
        self._set_attr(self._auth, 'TA_FILES_PATH', self.ta_cache_dir)
        self._set_attr(self._auth, 'CUIT', self.cuit)
        self._set_attr(self._auth, 'PROD', prod)
        if hasattr(self._settings, 'WSDL_WSAA'):
            self._set_attr(self._auth, 'WSDL_WSAA', getattr(self._settings, 'WSDL_WSAA'))
        else:
            self._set_attr(self._auth, 'WSDL_WSAA', self._wsdl_wsaa)

        # Mirror a webservice.* según requerimiento
        self._set_attr(self._webservice, 'CUIT', self.cuit)
        self._set_attr(self._webservice, 'PROD', prod)
        self._set_if_exists(self._webservice, 'WSDL_WSFE', self._wsdl_wsfe)
        self._set_if_exists(self._webservice, 'WSDL_PADRON', self._wsdl_padron)
        self._set_if_exists(
            self._webservice,
            'WSDL_WS_SR_CONSTANCIA_INSCRIPCION',
            self._wsdl_padron,
        )

        if hasattr(self._settings, 'set_environment'):
            self._settings.set_environment(self.ambiente)

    def _obtener_lock_archivo(self, servicio):
        """Retorna un file descriptor para lock de inicializacion de servicio."""
        lock_path = Path(self.ta_cache_dir) / f'{servicio}.init.lock'
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        self._ws_lock_files[servicio] = lock_fd
        return lock_fd

    def _inicializar_wsfe_si_hace_falta(self):
        """Inicializa WSFE de forma lazy y thread-safe.

        La autenticación WSAA ocurre dentro del constructor de ArcaWebService,
        por lo que no se necesita un paso adicional de autenticación.
        """
        with self._lock:
            if self._wsfe is not None:
                return self._wsfe

            self._aplicar_configuracion_global()
            lock_fd = self._obtener_lock_archivo('wsfe')

            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                if self._wsfe is not None:
                    return self._wsfe

                self._wsfe = self._crear_ws('wsfe')
                return self._wsfe
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def _inicializar_ws_constancia_si_hace_falta(self):
        """Inicializa WS de padrón de forma lazy y thread-safe.

        La autenticación WSAA ocurre dentro del constructor de ArcaWebService,
        por lo que no se necesita un paso adicional de autenticación.
        """
        with self._lock:
            if self._ws_constancia is not None:
                return self._ws_constancia

            self._aplicar_configuracion_global()
            lock_fd = self._obtener_lock_archivo('ws_sr_constancia_inscripcion')

            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
                if self._ws_constancia is not None:
                    return self._ws_constancia

                self._ws_constancia = self._crear_ws('ws_sr_constancia_inscripcion')
                return self._ws_constancia
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)

    def _crear_ws(self, servicio):
        """Crea instancia ArcaWebService siguiendo la firma documentada."""
        if servicio == 'wsfe':
            wsdl = self._wsdl_wsfe
        elif servicio == 'ws_sr_constancia_inscripcion':
            wsdl = self._wsdl_padron
        else:
            raise ArcaNetworkError(f'Servicio no soportado: {servicio}')

        intentos = (
            lambda: self._arca_webservice_cls(
                wsdl,
                servicio,
                enable_logging=self.enable_logging,
            ),
            lambda: self._arca_webservice_cls(
                wsdl,
                servicio,
            ),
        )
        errores = []

        for espera in (0, 1, 2):
            if espera:
                time.sleep(espera)

            self._aplicar_configuracion_global()
            reintentar_por_ta = False

            for crear in intentos:
                try:
                    return crear()
                except Exception as exc:
                    mensaje = str(exc)
                    errores.append(mensaje)
                    if self._es_error_ta_ya_valido(mensaje):
                        reintentar_por_ta = True
                        break

            if reintentar_por_ta:
                continue

            break

        raise ArcaNetworkError(
            f'No se pudo inicializar ArcaWebService para {servicio}.',
            detalle=' | '.join(errores),
        )

    @staticmethod
    def _normalizar_texto(texto):
        normalizado = unicodedata.normalize('NFKD', str(texto or ''))
        sin_acentos = ''.join(ch for ch in normalizado if not unicodedata.combining(ch))
        return sin_acentos.lower()

    @classmethod
    def _es_error_ta_ya_valido(cls, mensaje):
        return 'ya posee un ta valido' in cls._normalizar_texto(mensaje)

    def _build_auth_request(self, ws):
        """Construye FEAuthRequest con token/sign/cuit del WS inicializado."""
        try:
            auth_type_or_instance = ws.get_type('FEAuthRequest')
        except Exception as exc:
            raise ArcaNetworkError('No se pudo construir FEAuthRequest.', detalle=str(exc)) from exc

        auth = auth_type_or_instance
        if callable(auth_type_or_instance):
            try:
                auth = auth_type_or_instance()
            except TypeError:
                auth = auth_type_or_instance

        token = getattr(ws, 'token', None)
        sign = getattr(ws, 'sign', None)
        cuit = getattr(ws, 'cuit', None) or self.cuit
        cuit_str = str(cuit or '')

        cuit_int = int(cuit_str) if cuit_str else 0

        if isinstance(auth, dict):
            auth['Token'] = token
            auth['Sign'] = sign
            auth['Cuit'] = cuit_int
            return auth

        update_method = getattr(auth, 'update', None)
        if callable(update_method):
            try:
                update_method(
                    {
                        'Token': token,
                        'Sign': sign,
                        'Cuit': cuit_int,
                    },
                )
                return auth
            except Exception:
                pass

        setattr(auth, 'Token', token)
        setattr(auth, 'Sign', sign)
        setattr(auth, 'Cuit', cuit_int)
        return auth

    def _send_request(self, ws, operacion, payload):
        """Invoca send_request de ArcaWebService."""
        self._aplicar_configuracion_global()
        try:
            return ws.send_request(operacion, payload)
        except Exception as exc:
            raise ArcaNetworkError(
                f'No se pudo invocar {operacion} en ARCA.',
                detalle=str(exc),
            ) from exc

    @staticmethod
    def _normalizar_doc_tipo(valor):
        if valor is None:
            return None

        if isinstance(valor, int):
            return valor

        texto = str(valor).strip().upper()
        mapa = {
            'CUIT': 80,
            'CUIL': 86,
            'DNI': 96,
        }
        if texto in mapa:
            return mapa[texto]

        try:
            return int(texto)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extraer_digitos(valor):
        return re.sub(r'\D+', '', str(valor or ''))

    @classmethod
    def _normalizar_condicion_iva(cls, condicion_iva, condicion_iva_id):
        try:
            if condicion_iva_id is not None:
                condicion_iva_id = int(str(condicion_iva_id))
        except (TypeError, ValueError):
            condicion_iva_id = None

        if condicion_iva_id and not condicion_iva:
            condicion_iva = CONDICION_IVA.get(condicion_iva_id)

        if condicion_iva_id:
            return condicion_iva, condicion_iva_id

        texto = cls._normalizar_texto(condicion_iva)
        if not texto:
            return None, None

        reglas = (
            ('agente de percepcion', 11),
            ('responsable inscripto', 1),
            ('sujeto exento', 4),
            ('exento', 4),
            ('consumidor final', 5),
            ('monotributo', 6),
            ('proveedor del exterior', 8),
            ('cliente del exterior', 9),
            ('iva liberado', 10),
        )
        for patron, identificador in reglas:
            if patron in texto:
                return CONDICION_IVA.get(identificador), identificador

        return condicion_iva, None

    @classmethod
    def _inferir_condicion_iva_padron(cls, persona):
        """Infiere condición IVA de la respuesta getPersona_v2.

        La respuesta de getPersona_v2 no trae campos explícitos de condición IVA.
        Se infiere según la presencia de datosRegimenGeneral o datosMonotributo.
        """
        # Primero intentar con campos explícitos como fallback
        desc = cls._buscar(
            persona,
            ('descripcionCondicionIVA',),
            ('datosGenerales', 'descripcionCondicionIVA'),
            ('condicionIVA',),
        )
        cond_id = cls._buscar(
            persona,
            ('idCondicionIVA',),
            ('datosGenerales', 'idCondicionIVA'),
            ('condicionIVAId',),
        )
        if desc or cond_id:
            return cls._normalizar_condicion_iva(desc, cond_id)

        # Inferir desde estructura de getPersona_v2
        datos_rg = cls._buscar(persona, ('datosRegimenGeneral',))
        datos_mono = cls._buscar(persona, ('datosMonotributo',))

        if datos_rg:
            return CONDICION_IVA.get(1), 1  # Responsable Inscripto
        if datos_mono:
            return CONDICION_IVA.get(6), 6  # Monotributo

        # Si tiene actividades pero no es RI ni Mono, probablemente Exento
        actividades = cls._buscar(
            persona,
            ('datosRegimenGeneral', 'actividad'),
            ('datosMonotributo', 'actividad'),
            ('listActividades',),
        )
        if actividades:
            return CONDICION_IVA.get(4), 4  # Exento

        return CONDICION_IVA.get(5), 5  # Consumidor Final

    @classmethod
    def _mensaje_no_encontrado(cls, mensaje):
        texto = cls._normalizar_texto(mensaje)
        return any(
            patron in texto
            for patron in (
                'no se encontro',
                'no existe',
                'inexistente',
                'persona no encontrada',
            )
        )

    def consultar_padron(self, cuit_consulta):
        """Consulta padrón ARCA y retorna datos fiscales normalizados."""
        cuit_consulta_norm = self._extraer_digitos(cuit_consulta)
        if len(cuit_consulta_norm) != 11:
            return {
                'success': False,
                'error': 'El CUIT a consultar debe contener 11 dígitos.',
            }

        ws = self._inicializar_ws_constancia_si_hace_falta()
        payload = {
            'token': getattr(ws, 'token', None),
            'sign': getattr(ws, 'sign', None),
            'cuitRepresentada': int(self.cuit),
            'idPersona': int(cuit_consulta_norm),
        }

        respuesta = self._send_request(ws, 'getPersona_v2', payload)
        data = self._normalizar_estructura_respuesta(
            self._to_python(respuesta) or {},
            'getPersona_v2',
        )

        if not isinstance(data, dict):
            return {
                'success': False,
                'error': 'Respuesta inválida del padrón ARCA.',
                'raw': data,
            }

        error_ws = self._buscar(
            data,
            ('errorConstancia',),
            ('ErrorConstancia',),
            ('error',),
            default='',
        )
        if error_ws:
            error_texto = str(error_ws)
            if self._mensaje_no_encontrado(error_texto):
                return {
                    'success': False,
                    'error': 'No se encontró información para el CUIT consultado.',
                    'raw': data,
                }
            return {
                'success': False,
                'error': error_texto,
                'raw': data,
            }

        persona = self._buscar(
            data,
            ('persona',),
            ('Persona',),
            ('personaReturn',),
            ('return',),
            default=data,
        )
        if not isinstance(persona, dict):
            return {
                'success': False,
                'error': 'No se pudo interpretar la respuesta del padrón ARCA.',
                'raw': data,
            }

        datos_generales = self._buscar(
            persona,
            ('datosGenerales',),
            ('datos_generales',),
            default=persona,
        )
        if not isinstance(datos_generales, dict):
            datos_generales = persona

        cuit_resultado = self._extraer_digitos(
            self._buscar(
                persona,
                ('idPersona',),
                ('cuit',),
                ('nroCUIT',),
                ('datosGenerales', 'idPersona'),
                default=cuit_consulta_norm,
            )
        )
        if len(cuit_resultado) != 11:
            cuit_resultado = cuit_consulta_norm

        razon_social = self._buscar(
            datos_generales,
            ('razonSocial',),
            ('razon_social',),
            ('apellidoNombre',),
        )
        if not razon_social:
            nombre = self._buscar(datos_generales, ('nombre',), default='')
            apellido = self._buscar(datos_generales, ('apellido',), default='')
            razon_social = ' '.join([str(apellido).strip(), str(nombre).strip()]).strip()

        condicion_iva, condicion_iva_id = self._inferir_condicion_iva_padron(persona)

        doc_tipo = self._normalizar_doc_tipo(
            self._buscar(
                persona,
                ('tipoClave',),
                ('docTipo',),
                ('datosGenerales', 'tipoClave'),
                ('datosGenerales', 'docTipo'),
                default=80,
            )
        )
        doc_nro = self._extraer_digitos(
            self._buscar(
                persona,
                ('docNro',),
                ('nroDocumento',),
                ('idPersona',),
                ('datosGenerales', 'docNro'),
                ('datosGenerales', 'idPersona'),
                default=cuit_resultado,
            )
        )

        if not razon_social:
            return {
                'success': False,
                'error': 'No se encontró razón social para el CUIT consultado.',
                'raw': data,
            }

        resultado = {
            'cuit': cuit_resultado,
            'razon_social': str(razon_social).strip(),
            'condicion_iva': condicion_iva,
            'condicion_iva_id': condicion_iva_id,
            'doc_tipo': doc_tipo or 80,
            'doc_nro': doc_nro or cuit_resultado,
        }
        return {
            'success': True,
            'data': resultado,
            'raw': data,
        }

    @staticmethod
    def _es_secuencia(objeto):
        return isinstance(objeto, (list, tuple, set))

    def _to_python(self, valor):
        """Convierte objetos Zeep u objetos complejos a tipos nativos."""
        if valor is None or isinstance(valor, (str, int, float, bool)):
            return valor

        if self._es_secuencia(valor):
            return [self._to_python(item) for item in valor]

        if isinstance(valor, dict):
            return {k: self._to_python(v) for k, v in valor.items()}

        # Intentar serialización nativa de zeep primero (maneja CompoundValue, etc.)
        if _zeep_serialize is not None:
            try:
                serializado = _zeep_serialize(valor, dict)
                if isinstance(serializado, dict):
                    return {k: self._to_python(v) for k, v in serializado.items()}
                if self._es_secuencia(serializado):
                    return [self._to_python(item) for item in serializado]
                return serializado
            except Exception:
                pass

        # Fallback para cuando zeep no está disponible
        if hasattr(valor, '__values__'):
            return {k: self._to_python(v) for k, v in valor.__values__.items()}

        if hasattr(valor, '__dict__'):
            data = {k: self._to_python(v) for k, v in vars(valor).items() if not k.startswith('_')}
            if data:
                return data

        return valor

    @staticmethod
    def _asegurar_lista(valor):
        """Normaliza campos que pueden venir como objeto unico o lista."""
        if valor is None:
            return []
        if isinstance(valor, list):
            return valor
        return [valor]

    @staticmethod
    def _buscar(data, *rutas, default=None):
        """Busca el primer valor disponible en rutas de claves."""
        for ruta in rutas:
            actual = data
            ok = True
            for clave in ruta:
                if isinstance(actual, dict) and clave in actual:
                    actual = actual[clave]
                elif isinstance(actual, list) and isinstance(clave, int) and len(actual) > clave:
                    actual = actual[clave]
                else:
                    ok = False
                    break
            if ok:
                return actual
        return default

    @staticmethod
    def _normalizar_estructura_respuesta(data, operacion=None):
        """Colapsa wrappers de Zeep/soap para exponer el payload util."""
        if not isinstance(data, dict):
            return data

        if operacion:
            directas = (
                f'{operacion}Result',
                f'{operacion.lower()}Result',
                f'{operacion}Response',
            )
            for clave in directas:
                if clave in data and data[clave] is not None:
                    return data[clave]

        if len(data) == 1:
            _, unico = next(iter(data.items()))
            if isinstance(unico, dict):
                return unico

        return data

    def _parsear_errores_observaciones(self, data):
        """Extrae errores y observaciones de una respuesta WSFE."""
        errores_raw = self._buscar(
            data,
            ('Errors', 'Err'),
            ('Errors',),
            ('errors',),
            ('ResultadoGet', 'Errors', 'Err'),
            default=[],
        )
        obs_raw = self._buscar(
            data,
            ('FeDetResp', 'FECAEDetResponse', 0, 'Observaciones', 'Obs'),
            ('FeDetResp', 'FECAEDetResponse', 0, 'Observaciones'),
            ('Observaciones', 'Obs'),
            ('Observaciones',),
            ('ResultadoGet', 'Observaciones', 'Obs'),
            ('observaciones',),
            default=[],
        )

        if isinstance(errores_raw, dict) and 'Err' in errores_raw:
            errores_raw = errores_raw['Err']
        if isinstance(obs_raw, dict) and 'Obs' in obs_raw:
            obs_raw = obs_raw['Obs']

        errores = [self._to_python(e) for e in self._asegurar_lista(errores_raw)]
        observaciones = [self._to_python(o) for o in self._asegurar_lista(obs_raw)]
        return errores, observaciones

    def _parsear_respuesta(self, respuesta, operacion='FECAESolicitar'):
        """Normaliza respuesta de WSFE para consumo interno."""
        data = self._normalizar_estructura_respuesta(
            self._to_python(respuesta) or {},
            operacion,
        )

        dets = self._buscar(
            data,
            ('FeDetResp', 'FECAEDetResponse'),
            ('ResultGet',),
            ('ResultadoGet',),
            default=[],
        )
        detalle = self._asegurar_lista(dets)
        primer_detalle = detalle[0] if detalle else {}

        errores, observaciones = self._parsear_errores_observaciones(data)
        resultado = self._buscar(
            primer_detalle,
            ('Resultado',),
            ('resultado',),
            default=self._buscar(data, ('FeCabResp', 'Resultado'), ('resultado',)),
        )

        return {
            'resultado': resultado,
            'cae': self._buscar(primer_detalle, ('CAE',), ('cae',)),
            'cae_vencimiento': self._buscar(primer_detalle, ('CAEFchVto',), ('cae_vencimiento',)),
            'numero_comprobante': self._buscar(
                primer_detalle,
                ('CbteDesde',),
                ('CbteHasta',),
                ('numero_comprobante',),
                ('CbteNro',),
            ),
            'errores': errores,
            'observaciones': observaciones,
            'raw': data,
        }

    def fe_comp_ultimo_autorizado(self, punto_venta, tipo_cbte):
        """Consulta el ultimo numero autorizado para el punto/tipo indicado."""
        ws = self._inicializar_wsfe_si_hace_falta()
        auth = self._build_auth_request(ws)
        respuesta = self._send_request(
            ws,
            'FECompUltimoAutorizado',
            {
                'Auth': auth,
                'PtoVta': int(punto_venta),
                'CbteTipo': int(tipo_cbte),
            },
        )
        data = self._normalizar_estructura_respuesta(
            self._to_python(respuesta) or {},
            'FECompUltimoAutorizado',
        )
        numero = self._buscar(
            data,
            ('CbteNro',),
            ('cbte_nro',),
            ('numero_comprobante',),
            ('result', 'CbteNro'),
            default=0,
        )
        try:
            return int(str(numero or 0))
        except Exception as exc:
            raise ArcaNetworkError(
                'Respuesta invalida al consultar ultimo autorizado.',
                detalle=str(data),
            ) from exc

    def fe_cae_solicitar(self, request_data):
        """Solicita CAE y retorna una respuesta normalizada."""
        ws = self._inicializar_wsfe_si_hace_falta()
        auth = self._build_auth_request(ws)
        respuesta = self._send_request(
            ws,
            'FECAESolicitar',
            {'Auth': auth, 'FeCAEReq': request_data},
        )
        return self._parsear_respuesta(respuesta, 'FECAESolicitar')

    def fe_comp_consultar(self, tipo_cbte, punto_venta, numero):
        """Consulta un comprobante puntual y devuelve respuesta normalizada."""
        ws = self._inicializar_wsfe_si_hace_falta()
        auth = self._build_auth_request(ws)
        respuesta = self._send_request(
            ws,
            'FECompConsultar',
            {
                'Auth': auth,
                'FeCompConsReq': {
                    'CbteTipo': int(tipo_cbte),
                    'PtoVta': int(punto_venta),
                    'CbteNro': int(numero),
                },
            },
        )
        return self._parsear_respuesta(respuesta, 'FECompConsultar')

    def close(self):
        """Libera locks y elimina archivos temporales sensibles."""
        with self._lock:
            if self._cerrado:
                return

            self._cerrado = True
            self._wsfe = None
            self._ws_constancia = None

            for lock_fd in self._ws_lock_files.values():
                try:
                    os.close(lock_fd)
                except OSError:
                    pass
            self._ws_lock_files = {}

            for path in (self._cert_path, self._key_path):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

            if self._tmp_dir and os.path.isdir(self._tmp_dir):
                try:
                    os.rmdir(self._tmp_dir)
                except OSError:
                    pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
