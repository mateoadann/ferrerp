"""Servicio de orquestacion para emitir factura electronica desde una venta."""

from datetime import datetime
from decimal import Decimal

from ..extensions import db
from ..models import Empresa, Factura, FacturaDetalle, Venta
from .arca_client import ArcaClient
from .arca_constants import CLASE_POR_TIPO, FACTURA_POR_CLASE, determinar_clase_comprobante
from .arca_exceptions import ArcaAuthError, ArcaNetworkError, ArcaRechazoError, ArcaValidationError
from .factura_builder import FacturaBuilder
from .wsfe_service import WSFEService


class FacturacionService:
    """Coordina la emision de comprobantes ARCA a partir de ventas."""

    def __init__(self, arca_client_cls=ArcaClient, wsfe_service_cls=WSFEService):
        self.arca_client_cls = arca_client_cls
        self.wsfe_service_cls = wsfe_service_cls

    def emitir_factura_desde_venta(
        self,
        venta_id,
        empresa_id,
        tipo_comprobante=None,
        punto_venta=None,
        concepto=1,
    ):
        """Emite comprobante electronico para una venta completada."""
        venta = self._obtener_venta_completada(venta_id, empresa_id)
        empresa = self._validar_configuracion_empresa(empresa_id)
        receptor = self._resolver_receptor_fiscal(venta.cliente)

        clase = self._determinar_clase(empresa.condicion_iva_id, receptor['condicion_iva_id'])
        tipo_cbte = int(tipo_comprobante or FACTURA_POR_CLASE.get(clase, 0))
        if not tipo_cbte:
            raise ArcaValidationError(
                f'No se pudo determinar tipo de comprobante para clase {clase}.'
            )

        self._validar_no_duplicada(venta.id, empresa_id, tipo_cbte)

        pv = int(punto_venta or empresa.punto_venta_arca)
        arca_client = self.arca_client_cls(
            cuit=empresa.cuit,
            certificado=empresa.certificado_arca,
            clave_privada=empresa.clave_privada_arca,
            ambiente=empresa.ambiente_arca or 'testing',
        )
        wsfe = self.wsfe_service_cls(arca_client)

        factura = None

        try:
            ultimo = wsfe.ultimo_autorizado(pv, tipo_cbte)
            numero_cbte = int(ultimo) + 1
            request_data = self._construir_request(
                venta=venta,
                tipo_comprobante=tipo_cbte,
                punto_venta=pv,
                numero_comprobante=numero_cbte,
                concepto=concepto,
                receptor=receptor,
            )

            factura = self._crear_factura_local(
                venta=venta,
                empresa=empresa,
                tipo_comprobante=tipo_cbte,
                punto_venta=pv,
                numero_comprobante=numero_cbte,
                concepto=concepto,
                receptor=receptor,
                request_data=request_data,
            )
            db.session.commit()

            try:
                respuesta = wsfe.autorizar(request_data)
            except ArcaRechazoError as exc:
                if wsfe.es_error_secuencia(exc):
                    respuesta = self._reintentar_secuencia(
                        wsfe=wsfe,
                        factura=factura,
                        venta=venta,
                        tipo_comprobante=tipo_cbte,
                        punto_venta=pv,
                        concepto=concepto,
                        receptor=receptor,
                    )
                    if not respuesta:
                        return factura
                else:
                    self._marcar_rechazada(factura, exc)
                    db.session.commit()
                    return factura

            self._marcar_autorizada(factura, respuesta)
            db.session.commit()
            return factura

        except (ArcaNetworkError, ArcaAuthError) as exc:
            db.session.rollback()
            if factura:
                self._guardar_estado_error(
                    factura.id, str(exc), detalle=getattr(exc, 'detalle', None)
                )
            raise
        except Exception:
            db.session.rollback()
            if factura:
                self._guardar_estado_error(factura.id, 'Error inesperado al emitir factura.')
            raise
        finally:
            arca_client.close()

    @staticmethod
    def _obtener_venta_completada(venta_id, empresa_id):
        """Busca una venta completada perteneciente a la empresa."""
        venta = Venta.query.filter_by(id=venta_id, empresa_id=empresa_id).first()
        if not venta:
            raise ArcaValidationError('Venta no encontrada para la empresa indicada.')
        if venta.estado != 'completada':
            raise ArcaValidationError('Solo se pueden facturar ventas completadas.')
        return venta

    @staticmethod
    def _validar_configuracion_empresa(empresa_id):
        """Valida configuracion minima ARCA de la empresa."""
        empresa = Empresa.query.filter_by(id=empresa_id).first()
        if not empresa:
            raise ArcaValidationError('Empresa no encontrada.')

        faltantes = []
        if not empresa.arca_habilitado:
            faltantes.append('arca_habilitado')
        if not empresa.certificado_arca:
            faltantes.append('certificado_arca')
        if not empresa.clave_privada_arca:
            faltantes.append('clave_privada_arca')
        if not empresa.cuit:
            faltantes.append('cuit')
        if not empresa.condicion_iva_id:
            faltantes.append('condicion_iva_id')
        if not empresa.punto_venta_arca:
            faltantes.append('punto_venta_arca')

        if faltantes:
            raise ArcaValidationError(
                f'Configuracion ARCA incompleta: {", ".join(faltantes)}',
            )
        return empresa

    @staticmethod
    def _resolver_receptor_fiscal(cliente):
        """Resuelve datos fiscales del receptor o consumidor final por defecto."""
        if not cliente:
            return {
                'doc_tipo': 99,
                'doc_nro': 0,
                'condicion_iva_id': 5,
                'nombre': 'Consumidor Final',
            }

        doc_nro = ''.join(ch for ch in str(cliente.dni_cuit or '') if ch.isdigit())
        return {
            'doc_tipo': int(cliente.doc_tipo or 99),
            'doc_nro': int(doc_nro or 0),
            'condicion_iva_id': int(cliente.condicion_iva_id or 5),
            'nombre': cliente.nombre_fiscal,
        }

    @staticmethod
    def _determinar_clase(condicion_iva_emisor_id, condicion_iva_receptor_id):
        """Determina clase A/B/C validando combinaciones fiscales."""
        try:
            return determinar_clase_comprobante(condicion_iva_emisor_id, condicion_iva_receptor_id)
        except ValueError as exc:
            raise ArcaValidationError(str(exc)) from exc

    @staticmethod
    def _validar_no_duplicada(venta_id, empresa_id, tipo_comprobante):
        """Impide facturar dos veces la misma venta con mismo tipo autorizado."""
        factura = Factura.query.filter_by(
            venta_id=venta_id,
            empresa_id=empresa_id,
            tipo_comprobante=tipo_comprobante,
            estado='autorizada',
        ).first()
        if factura:
            raise ArcaValidationError(
                f'Ya existe factura autorizada para esta venta y tipo ({tipo_comprobante}).',
            )

    @staticmethod
    def _construir_request(
        venta,
        tipo_comprobante,
        punto_venta,
        numero_comprobante,
        concepto,
        receptor,
    ):
        """Construye payload FECAESolicitar con FacturaBuilder."""
        return FacturaBuilder.desde_venta(
            venta=venta,
            tipo_comprobante=tipo_comprobante,
            punto_venta=punto_venta,
            numero_comprobante=numero_comprobante,
            concepto=concepto,
            receptor=receptor,
            precios_con_iva=True,
        )

    def _crear_factura_local(
        self,
        venta,
        empresa,
        tipo_comprobante,
        punto_venta,
        numero_comprobante,
        concepto,
        receptor,
        request_data,
    ):
        """Crea factura local en estado pendiente y copia sus detalles."""
        det_req = request_data['FeDetReq']['FECAEDetRequest'][0]
        factura = Factura(
            venta_id=venta.id,
            empresa_id=empresa.id,
            tipo_comprobante=tipo_comprobante,
            punto_venta=punto_venta,
            numero_comprobante=numero_comprobante,
            concepto=concepto,
            fecha_emision=(venta.fecha.date() if hasattr(venta.fecha, 'date') else venta.fecha),
            doc_tipo_receptor=receptor['doc_tipo'],
            doc_nro_receptor=str(receptor['doc_nro']),
            condicion_iva_receptor_id=receptor['condicion_iva_id'],
            imp_total=Decimal(str(det_req['ImpTotal'])),
            imp_neto=Decimal(str(det_req['ImpNeto'])),
            imp_iva=Decimal(str(det_req['ImpIVA'])),
            imp_tot_conc=Decimal(str(det_req['ImpTotConc'])),
            imp_op_ex=Decimal(str(det_req['ImpOpEx'])),
            imp_trib=Decimal(str(det_req['ImpTrib'])),
            mon_id=det_req['MonId'],
            mon_cotiz=Decimal(str(det_req['MonCotiz'])),
            estado='pendiente',
            arca_request=request_data,
        )

        db.session.add(factura)
        db.session.flush()

        clase = CLASE_POR_TIPO.get(tipo_comprobante)
        precios_con_iva = clase in ('B', 'M', 'C')

        for detalle in venta.detalles:
            iva_porcentaje = Decimal(str(detalle.iva_porcentaje or 0))
            subtotal_linea = Decimal(str(detalle.subtotal or 0))

            if clase == 'C' or iva_porcentaje == 0:
                iva_monto = Decimal('0.00')
            elif precios_con_iva:
                divisor = Decimal('1') + (iva_porcentaje / Decimal('100'))
                neto = subtotal_linea / divisor
                iva_monto = (subtotal_linea - neto).quantize(
                    Decimal('0.01'),
                )
            else:
                iva_monto = (subtotal_linea * iva_porcentaje / Decimal('100')).quantize(
                    Decimal('0.01'),
                )

            factura_det = FacturaDetalle(
                factura_id=factura.id,
                producto_id=detalle.producto_id,
                descripcion=detalle.producto.nombre
                if detalle.producto
                else f'Producto #{detalle.producto_id}',
                cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario,
                subtotal=detalle.subtotal,
                iva_porcentaje=detalle.iva_porcentaje,
                iva_monto=iva_monto,
            )
            db.session.add(factura_det)

        return factura

    def _reintentar_secuencia(
        self,
        wsfe,
        factura,
        venta,
        tipo_comprobante,
        punto_venta,
        concepto,
        receptor,
    ):
        """Reintenta una unica vez cuando ARCA devuelve error de secuencia 10016."""
        ultimo = wsfe.ultimo_autorizado(punto_venta, tipo_comprobante)
        nuevo_numero = int(ultimo) + 1

        nuevo_request = self._construir_request(
            venta=venta,
            tipo_comprobante=tipo_comprobante,
            punto_venta=punto_venta,
            numero_comprobante=nuevo_numero,
            concepto=concepto,
            receptor=receptor,
        )

        factura.numero_comprobante = nuevo_numero
        factura.arca_request = nuevo_request
        db.session.commit()

        try:
            return wsfe.autorizar(nuevo_request)
        except ArcaRechazoError as exc:
            self._marcar_rechazada(factura, exc)
            db.session.commit()
            return None

    @staticmethod
    def _marcar_autorizada(factura, respuesta):
        """Actualiza factura local como autorizada por ARCA."""
        factura.estado = 'autorizada'
        factura.cae = respuesta.get('cae')
        factura.cae_vencimiento = FacturacionService._parsear_fecha(
            respuesta.get('cae_vencimiento')
        )
        factura.error_codigo = None
        factura.error_mensaje = None
        factura.arca_response = respuesta.get('raw') or respuesta

    @staticmethod
    def _marcar_rechazada(factura, exc):
        """Actualiza factura local como rechazada por ARCA."""
        factura.estado = 'rechazada'
        factura.error_codigo = str(exc.codigo or '') or None
        factura.error_mensaje = exc.mensaje
        factura.arca_response = (
            exc.detalle if isinstance(exc.detalle, dict) else {'detalle': exc.detalle}
        )

    @staticmethod
    def _guardar_estado_error(factura_id, mensaje, detalle=None):
        """Persistencia best-effort del estado error ante fallas de red/autenticacion."""
        factura = Factura.query.filter_by(id=factura_id).first()
        if not factura:
            return

        factura.estado = 'error'
        factura.error_mensaje = mensaje
        if detalle is not None:
            factura.arca_response = {'detalle': detalle}
        db.session.commit()

    @staticmethod
    def _parsear_fecha(valor):
        """Parsea fechas devueltas por ARCA en varios formatos."""
        if not valor:
            return None
        if hasattr(valor, 'year'):
            return valor

        texto = str(valor)
        for formato in ('%Y%m%d', '%Y-%m-%d'):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
        return None
