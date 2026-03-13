"""Builder para construir payloads FECAESolicitar."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .arca_constants import CLASE_POR_TIPO, porcentaje_a_alicuota_id
from .arca_exceptions import ArcaValidationError

DOS_DECIMALES = Decimal('0.01')


def _to_decimal(valor):
    if valor is None:
        return Decimal('0')
    return Decimal(str(valor))


def _round2(valor):
    return _to_decimal(valor).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)


class FacturaBuilder:
    """API fluida para armar comprobantes electronicos de ARCA."""

    def __init__(self):
        self._data = {
            'CantReg': 1,
            'PtoVta': None,
            'CbteTipo': None,
            'Concepto': 1,
            'DocTipo': 99,
            'DocNro': 0,
            'CbteDesde': None,
            'CbteHasta': None,
            'CbteFch': date.today(),
            'FchServDesde': None,
            'FchServHasta': None,
            'FchVtoPago': None,
            'ImpTotal': Decimal('0'),
            'ImpTotConc': Decimal('0'),
            'ImpNeto': Decimal('0'),
            'ImpOpEx': Decimal('0'),
            'ImpTrib': Decimal('0'),
            'ImpIVA': Decimal('0'),
            'MonId': 'PES',
            'MonCotiz': Decimal('1'),
            'CondicionIVAReceptorId': None,
            'Iva': [],
            'CbtesAsoc': [],
            'clase': None,
        }

    def set_comprobante(self, tipo_comprobante, punto_venta, numero_comprobante, concepto=1):
        """Configura tipo, punto de venta, numero y concepto del comprobante."""
        self._data['CbteTipo'] = int(tipo_comprobante)
        self._data['PtoVta'] = int(punto_venta)
        self._data['CbteDesde'] = int(numero_comprobante)
        self._data['CbteHasta'] = int(numero_comprobante)
        self._data['Concepto'] = int(concepto)
        self._data['clase'] = CLASE_POR_TIPO.get(int(tipo_comprobante))
        return self

    def set_fechas(
        self, fecha_emision, fch_serv_desde=None, fch_serv_hasta=None, fch_vto_pago=None
    ):
        """Configura fechas de emision y, opcionalmente, de servicios."""
        self._data['CbteFch'] = fecha_emision or date.today()
        self._data['FchServDesde'] = fch_serv_desde
        self._data['FchServHasta'] = fch_serv_hasta
        self._data['FchVtoPago'] = fch_vto_pago
        return self

    def set_receptor(self, doc_tipo, doc_nro):
        """Configura documento del receptor."""
        self._data['DocTipo'] = int(doc_tipo)
        self._data['DocNro'] = int(doc_nro)
        return self

    def set_importes(
        self,
        imp_total,
        imp_neto,
        imp_iva,
        imp_tot_conc=Decimal('0'),
        imp_op_ex=Decimal('0'),
        imp_trib=Decimal('0'),
    ):
        """Configura importes del comprobante."""
        self._data['ImpTotal'] = _round2(imp_total)
        self._data['ImpNeto'] = _round2(imp_neto)
        self._data['ImpIVA'] = _round2(imp_iva)
        self._data['ImpTotConc'] = _round2(imp_tot_conc)
        self._data['ImpOpEx'] = _round2(imp_op_ex)
        self._data['ImpTrib'] = _round2(imp_trib)
        return self

    def set_moneda(self, mon_id='PES', mon_cotiz=Decimal('1')):
        """Configura moneda y cotizacion."""
        self._data['MonId'] = mon_id
        self._data['MonCotiz'] = _to_decimal(mon_cotiz)
        return self

    def add_iva(self, iva_id, base_imp, importe):
        """Agrega una alicuota de IVA al detalle de impuestos."""
        self._data['Iva'].append(
            {
                'Id': int(iva_id),
                'BaseImp': _round2(base_imp),
                'Importe': _round2(importe),
            }
        )
        return self

    def set_comprobante_asociado(
        self,
        tipo_comprobante,
        punto_venta,
        numero_comprobante,
        cuit_emisor=None,
        fecha_comprobante=None,
    ):
        """Asocia un comprobante de referencia (obligatorio en NC/ND)."""
        item = {
            'Tipo': int(tipo_comprobante),
            'PtoVta': int(punto_venta),
            'Nro': int(numero_comprobante),
        }
        if cuit_emisor:
            item['Cuit'] = int(str(cuit_emisor))
        if fecha_comprobante:
            item['CbteFch'] = self._formatear_fecha(fecha_comprobante)
        self._data['CbtesAsoc'].append(item)
        return self

    def set_condicion_iva_receptor(self, condicion_iva_receptor_id):
        """Configura CondicionIVAReceptorId (RG 5616)."""
        self._data['CondicionIVAReceptorId'] = int(condicion_iva_receptor_id)
        return self

    def _ajustar_ecuacion_importes(self):
        """Ajusta deriva de redondeo de hasta un centavo para cuadrar ecuacion."""
        suma = (
            self._data['ImpNeto']
            + self._data['ImpIVA']
            + self._data['ImpTotConc']
            + self._data['ImpOpEx']
            + self._data['ImpTrib']
        )
        diferencia = self._data['ImpTotal'] - suma
        if diferencia == 0:
            return

        if abs(diferencia) <= DOS_DECIMALES:
            self._data['ImpTrib'] = _round2(self._data['ImpTrib'] + diferencia)
            return

        raise ArcaValidationError(
            'La ecuacion de importes no cierra.',
            detalle={
                'imp_total': str(self._data['ImpTotal']),
                'suma_componentes': str(suma),
                'diferencia': str(diferencia),
            },
        )

    def validate(self):
        """Valida reglas de negocio antes de construir el payload final."""
        requeridos = ('PtoVta', 'CbteTipo', 'CbteDesde', 'CbteHasta', 'CondicionIVAReceptorId')
        faltantes = [campo for campo in requeridos if self._data.get(campo) is None]
        if faltantes:
            raise ArcaValidationError(f'Faltan campos obligatorios: {", ".join(faltantes)}')

        if self._data['Concepto'] in (2, 3):
            if not all(
                (
                    self._data['FchServDesde'],
                    self._data['FchServHasta'],
                    self._data['FchVtoPago'],
                )
            ):
                raise ArcaValidationError(
                    'Para concepto servicios se requieren FchServDesde, FchServHasta y FchVtoPago.',
                )

        if self._data['CbteTipo'] in (2, 3, 7, 8, 12, 13, 52, 53) and not self._data['CbtesAsoc']:
            raise ArcaValidationError('NC/ND requiere comprobante asociado.')

        if self._data['clase'] == 'C':
            self._data['ImpIVA'] = Decimal('0.00')
            self._data['Iva'] = []

        self._ajustar_ecuacion_importes()
        return self

    @staticmethod
    def _formatear_fecha(valor):
        """Formatea una fecha al formato YYYYMMDD."""
        if valor is None:
            return None
        if isinstance(valor, str):
            return valor
        return valor.strftime('%Y%m%d')

    def build(self):
        """Construye el payload final listo para FECAESolicitar."""
        self.validate()

        detalle = {
            'Concepto': self._data['Concepto'],
            'DocTipo': self._data['DocTipo'],
            'DocNro': self._data['DocNro'],
            'CbteDesde': self._data['CbteDesde'],
            'CbteHasta': self._data['CbteHasta'],
            'CbteFch': self._formatear_fecha(self._data['CbteFch']),
            'ImpTotal': float(_round2(self._data['ImpTotal'])),
            'ImpTotConc': float(_round2(self._data['ImpTotConc'])),
            'ImpNeto': float(_round2(self._data['ImpNeto'])),
            'ImpOpEx': float(_round2(self._data['ImpOpEx'])),
            'ImpTrib': float(_round2(self._data['ImpTrib'])),
            'ImpIVA': float(_round2(self._data['ImpIVA'])),
            'MonId': self._data['MonId'],
            'MonCotiz': float(self._data['MonCotiz']),
            'CondicionIVAReceptorId': self._data['CondicionIVAReceptorId'],
        }

        if self._data['Concepto'] in (2, 3):
            detalle['FchServDesde'] = self._formatear_fecha(self._data['FchServDesde'])
            detalle['FchServHasta'] = self._formatear_fecha(self._data['FchServHasta'])
            detalle['FchVtoPago'] = self._formatear_fecha(self._data['FchVtoPago'])

        if self._data['CbtesAsoc']:
            detalle['CbtesAsoc'] = {'CbteAsoc': self._data['CbtesAsoc']}

        if self._data['clase'] != 'C' and self._data['Iva']:
            iva_items = [
                {
                    'Id': item['Id'],
                    'BaseImp': float(_round2(item['BaseImp'])),
                    'Importe': float(_round2(item['Importe'])),
                }
                for item in self._data['Iva']
            ]
            detalle['Iva'] = {'AlicIva': iva_items}

        return {
            'FeCabReq': {
                'CantReg': self._data['CantReg'],
                'PtoVta': self._data['PtoVta'],
                'CbteTipo': self._data['CbteTipo'],
            },
            'FeDetReq': {'FECAEDetRequest': [detalle]},
        }

    @classmethod
    def desde_venta(
        cls,
        venta,
        tipo_comprobante,
        punto_venta,
        numero_comprobante,
        concepto,
        receptor,
        comprobante_asociado=None,
        precios_con_iva=True,
        fch_serv_desde=None,
        fch_serv_hasta=None,
        fch_vto_pago=None,
    ):
        """Construye payload FECAESolicitar a partir de una venta y sus detalles."""
        builder = cls()
        clase = CLASE_POR_TIPO.get(int(tipo_comprobante))
        if not clase:
            raise ArcaValidationError(f'Tipo de comprobante no soportado: {tipo_comprobante}')

        detalles = list(venta.detalles)
        if not detalles:
            raise ArcaValidationError('La venta no tiene detalles para facturar.')

        subtotal_venta = _round2(venta.subtotal or sum(_to_decimal(d.subtotal) for d in detalles))
        descuento_total = _round2(venta.descuento_monto or 0)
        total_venta = _round2(venta.total)

        neto_total = Decimal('0.00')
        iva_total = Decimal('0.00')
        iva_por_id = {}

        descuento_asignado = Decimal('0.00')

        for indice, detalle in enumerate(detalles, start=1):
            subtotal_linea = _round2(detalle.subtotal)
            es_ultimo = indice == len(detalles)

            if subtotal_venta > 0 and descuento_total > 0:
                if es_ultimo:
                    descuento_linea = descuento_total - descuento_asignado
                else:
                    descuento_linea = _round2(descuento_total * subtotal_linea / subtotal_venta)
                    descuento_asignado += descuento_linea
            else:
                descuento_linea = Decimal('0.00')

            subtotal_descuento = _round2(subtotal_linea - descuento_linea)
            iva_porcentaje = _to_decimal(detalle.iva_porcentaje or 0)

            if clase == 'C':
                neto_linea = subtotal_descuento
                iva_linea = Decimal('0.00')
            else:
                if precios_con_iva and iva_porcentaje > 0:
                    divisor = Decimal('1') + (iva_porcentaje / Decimal('100'))
                    neto_linea = _round2(subtotal_descuento / divisor)
                    iva_linea = _round2(subtotal_descuento - neto_linea)
                else:
                    neto_linea = subtotal_descuento
                    iva_linea = _round2(neto_linea * iva_porcentaje / Decimal('100'))

                iva_id = porcentaje_a_alicuota_id(iva_porcentaje)
                agrupado = iva_por_id.setdefault(
                    iva_id,
                    {'base': Decimal('0.00'), 'importe': Decimal('0.00')},
                )
                agrupado['base'] = _round2(agrupado['base'] + neto_linea)
                agrupado['importe'] = _round2(agrupado['importe'] + iva_linea)

            neto_total = _round2(neto_total + neto_linea)
            iva_total = _round2(iva_total + iva_linea)

        if clase == 'C':
            neto_total = total_venta
            iva_total = Decimal('0.00')

        builder.set_comprobante(tipo_comprobante, punto_venta, numero_comprobante, concepto)
        builder.set_fechas(
            fecha_emision=(venta.fecha.date() if hasattr(venta.fecha, 'date') else venta.fecha),
            fch_serv_desde=fch_serv_desde,
            fch_serv_hasta=fch_serv_hasta,
            fch_vto_pago=fch_vto_pago,
        )
        builder.set_receptor(
            receptor.get('doc_tipo', 99),
            receptor.get('doc_nro', 0),
        )
        builder.set_condicion_iva_receptor(receptor.get('condicion_iva_id', 5))
        builder.set_importes(
            imp_total=total_venta,
            imp_neto=neto_total,
            imp_iva=iva_total,
            imp_tot_conc=Decimal('0'),
            imp_op_ex=Decimal('0'),
            imp_trib=Decimal('0'),
        )
        builder.set_moneda('PES', Decimal('1'))

        if clase != 'C':
            for iva_id, valores in iva_por_id.items():
                builder.add_iva(iva_id, valores['base'], valores['importe'])

        if comprobante_asociado:
            builder.set_comprobante_asociado(
                comprobante_asociado['tipo_comprobante'],
                comprobante_asociado['punto_venta'],
                comprobante_asociado['numero_comprobante'],
                comprobante_asociado.get('cuit_emisor'),
                comprobante_asociado.get('fecha_comprobante'),
            )

        return builder.build()
