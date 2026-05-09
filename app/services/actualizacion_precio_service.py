"""Servicio de actualización masiva de precios."""

from decimal import ROUND_HALF_UP, Decimal

from flask_login import current_user

from ..extensions import db
from ..models import ActualizacionPrecio, Producto


def obtener_productos_por_categorias(categorias_ids):
    """Retorna productos activos de la empresa filtrados por múltiples categorías.

    Args:
        categorias_ids: lista de IDs de categorías seleccionadas.

    Returns:
        Lista de Producto activos que pertenecen a cualquiera de las categorías.
    """
    if not categorias_ids:
        return []

    query = (
        Producto.query_empresa()
        .filter(
            Producto.activo.is_(True),
            Producto.categoria_id.in_(categorias_ids),
        )
        .order_by(Producto.nombre)
    )
    return query.all()


def previsualizar_actualizacion(productos, porcentaje, actualizar_costo=True):
    """Calcula precios nuevos sin aplicar cambios.

    Args:
        productos: lista de objetos Producto.
        porcentaje: porcentaje de ajuste (positivo=aumento, negativo=descuento).
        actualizar_costo: si True, también se ajusta precio_costo.

    Returns:
        Lista de dicts con datos de previsualización.

    Raises:
        ValueError: si algún precio resultante queda <= 0.
    """
    porcentaje_decimal = Decimal(str(porcentaje))
    factor = Decimal('1') + porcentaje_decimal / Decimal('100')
    dos_decimales = Decimal('0.01')

    resultado = []
    errores = []

    for producto in productos:
        precio_costo_anterior = producto.precio_costo or Decimal('0')
        precio_venta_anterior = producto.precio_venta or Decimal('0')

        if actualizar_costo:
            precio_costo_nuevo = (precio_costo_anterior * factor).quantize(
                dos_decimales, rounding=ROUND_HALF_UP
            )
        else:
            precio_costo_nuevo = precio_costo_anterior

        precio_venta_nuevo = (precio_venta_anterior * factor).quantize(
            dos_decimales, rounding=ROUND_HALF_UP
        )

        # Validar que los precios no queden negativos o cero
        if precio_venta_nuevo <= 0:
            errores.append(
                f'El producto "{producto.nombre}" ({producto.codigo}) '
                f'quedaría con precio de venta ${precio_venta_nuevo}.'
            )
        if actualizar_costo and precio_costo_nuevo < 0:
            errores.append(
                f'El producto "{producto.nombre}" ({producto.codigo}) '
                f'quedaría con precio de costo ${precio_costo_nuevo}.'
            )

        resultado.append(
            {
                'producto': producto,
                'precio_costo_anterior': precio_costo_anterior,
                'precio_costo_nuevo': precio_costo_nuevo,
                'precio_venta_anterior': precio_venta_anterior,
                'precio_venta_nuevo': precio_venta_nuevo,
                'diferencia_costo': precio_costo_nuevo - precio_costo_anterior,
                'diferencia_venta': precio_venta_nuevo - precio_venta_anterior,
            }
        )

    if errores:
        raise ValueError(
            'No se puede aplicar el porcentaje porque algunos productos '
            'quedarían con precios inválidos:\n' + '\n'.join(errores)
        )

    return resultado


def aplicar_actualizacion(
    categorias_ids, porcentaje, actualizar_costo=True, notas=None, auto_commit=True
):
    """Aplica actualización masiva de precios.

    Args:
        categorias_ids: lista de IDs de categorías seleccionadas.
        porcentaje: porcentaje de ajuste.
        actualizar_costo: si True, también se ajusta precio_costo.
        notas: texto opcional de notas.

    Returns:
        Cantidad de productos actualizados.

    Raises:
        ValueError: si no hay productos o si precios quedarían inválidos.
    """
    productos = obtener_productos_por_categorias(categorias_ids)

    if not productos:
        raise ValueError('No hay productos activos en las categorías seleccionadas.')

    # Validar precios antes de aplicar
    preview = previsualizar_actualizacion(productos, porcentaje, actualizar_costo)

    porcentaje_decimal = Decimal(str(porcentaje))

    # Aplicar en transacción
    for item in preview:
        producto = item['producto']

        # Registrar auditoría
        registro = ActualizacionPrecio(
            producto_id=producto.id,
            usuario_id=current_user.id,
            tipo='masiva',
            porcentaje=porcentaje_decimal,
            precio_costo_anterior=item['precio_costo_anterior'],
            precio_costo_nuevo=item['precio_costo_nuevo'],
            precio_venta_anterior=item['precio_venta_anterior'],
            precio_venta_nuevo=item['precio_venta_nuevo'],
            actualizo_costo=actualizar_costo,
            categoria_id=categorias_ids[0] if categorias_ids else None,
            notas=notas,
            empresa_id=current_user.empresa_id,
        )
        db.session.add(registro)

        # Actualizar precios del producto
        producto.precio_venta = item['precio_venta_nuevo']
        if actualizar_costo:
            producto.precio_costo = item['precio_costo_nuevo']

    if auto_commit:
        db.session.commit()
    return len(preview)
