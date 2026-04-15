"""Rutas de productos."""

import json
from collections import OrderedDict
from decimal import Decimal

from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from ..extensions import db
from ..forms.producto_forms import (
    ActualizacionMasivaPreciosForm,
    ImportacionProductosForm,
    ProductoForm,
)
from ..models import Categoria, Producto
from ..services import actualizacion_precio_service
from ..services.importacion_producto_service import (
    ImportacionResult,
    aplicar_importacion,
    generar_plantilla_excel,
    parsear_archivo,
    validar_importacion,
)
from ..utils.decorators import admin_required, empresa_aprobada_required
from ..utils.helpers import es_peticion_htmx, paginar_query

bp = Blueprint('productos', __name__, url_prefix='/productos')


def _resolver_categoria_id(categoria_padre_id, subcategoria_id):
    """Resuelve el ID final de categoría a partir de padre/subcategoría."""
    if subcategoria_id and subcategoria_id > 0:
        return subcategoria_id
    if categoria_padre_id and categoria_padre_id > 0:
        return categoria_padre_id
    return None


@bp.route('/')
@login_required
def index():
    """Listado de productos."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    categoria_id = request.args.get('categoria', 0, type=int)
    solo_activos = request.args.get('activos', '1') == '1'
    solo_bajo_stock = request.args.get('bajo_stock', '0') == '1'

    # Construir query filtrada por empresa
    query = Producto.query_empresa()

    # Filtros
    if busqueda:
        query = query.filter(
            db.or_(
                Producto.codigo.ilike(f'%{busqueda}%'),
                Producto.nombre.ilike(f'%{busqueda}%'),
                Producto.codigo_barras.ilike(f'%{busqueda}%'),
            )
        )

    if categoria_id:
        categoria = Categoria.get_o_404(categoria_id)
        if categoria.es_padre:
            categoria_ids = [categoria.id] + [
                subcategoria.id for subcategoria in categoria.subcategorias
            ]
            query = query.filter(Producto.categoria_id.in_(categoria_ids))
        else:
            query = query.filter(Producto.categoria_id == categoria_id)

    if solo_activos:
        query = query.filter(Producto.activo.is_(True))

    if solo_bajo_stock:
        query = query.filter(Producto.stock_actual < Producto.stock_minimo)

    # Ordenar y paginar
    query = query.order_by(Producto.nombre)
    productos = paginar_query(query, page)

    # Categorías para el filtro
    categorias_padre = (
        Categoria.query_empresa()
        .filter_by(activa=True, padre_id=None)
        .order_by(Categoria.nombre)
        .all()
    )

    # Si es petición HTMX, devolver solo la tabla
    if es_peticion_htmx():
        return render_template('productos/_tabla.html', productos=productos, busqueda=busqueda)

    return render_template(
        'productos/index.html',
        productos=productos,
        categorias_padre=categorias_padre,
        busqueda=busqueda,
        categoria_id=categoria_id,
        solo_activos=solo_activos,
        solo_bajo_stock=solo_bajo_stock,
    )


@bp.route('/actualizacion-masiva')
@login_required
@empresa_aprobada_required
@admin_required
def actualizacion_masiva():
    """Página de actualización masiva de precios por categoría."""
    form = ActualizacionMasivaPreciosForm()

    # Construir árbol de categorías para el template
    categorias_padre = (
        Categoria.query_empresa()
        .filter_by(activa=True, padre_id=None)
        .order_by(Categoria.nombre)
        .all()
    )

    arbol_categorias = []
    for padre in categorias_padre:
        hijos = sorted(padre.subcategorias, key=lambda c: c.nombre)
        hijos_activos = [h for h in hijos if h.activa]
        arbol_categorias.append(
            {
                'id': padre.id,
                'nombre': padre.nombre,
                'hijos': [{'id': h.id, 'nombre': h.nombre} for h in hijos_activos],
            }
        )

    return render_template(
        'productos/actualizacion_masiva.html',
        form=form,
        arbol_categorias=arbol_categorias,
    )


@bp.route('/actualizacion-masiva/preview', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def actualizacion_masiva_preview():
    """Preview HTMX de actualización masiva de precios."""
    try:
        categorias_ids_raw = request.form.get('categorias_ids', '[]')
        categorias_ids = json.loads(categorias_ids_raw)
        categorias_ids = [int(cid) for cid in categorias_ids if cid]
    except (json.JSONDecodeError, ValueError):
        return render_template(
            'productos/_preview_actualizacion.html',
            error='Seleccioná al menos una categoría.',
            preview=None,
        )

    if not categorias_ids:
        return render_template(
            'productos/_preview_actualizacion.html',
            error='Seleccioná al menos una categoría.',
            preview=None,
        )

    try:
        porcentaje = Decimal(str(request.form.get('porcentaje', '0')))
    except Exception:
        return render_template(
            'productos/_preview_actualizacion.html',
            error='El porcentaje ingresado no es válido.',
            preview=None,
        )

    actualizar_costo = request.form.get('actualizar_costo') == 'y'

    # Validar que las categorías pertenezcan a la empresa
    for cid in categorias_ids:
        cat = Categoria.query.filter_by(id=cid, empresa_id=current_user.empresa_id).first()
        if not cat:
            return render_template(
                'productos/_preview_actualizacion.html',
                error=f'La categoría con ID {cid} no existe o no pertenece a tu empresa.',
                preview=None,
            )

    productos = actualizacion_precio_service.obtener_productos_por_categorias(categorias_ids)

    if not productos:
        return render_template(
            'productos/_preview_actualizacion.html',
            error='No hay productos activos en las categorías seleccionadas.',
            preview=None,
        )

    try:
        preview = actualizacion_precio_service.previsualizar_actualizacion(
            productos, porcentaje, actualizar_costo
        )
    except ValueError as e:
        return render_template(
            'productos/_preview_actualizacion.html',
            error=str(e),
            preview=None,
        )

    porcentaje_cero = porcentaje == 0

    return render_template(
        'productos/_preview_actualizacion.html',
        preview=preview,
        porcentaje=porcentaje,
        actualizar_costo=actualizar_costo,
        categorias_ids=categorias_ids,
        porcentaje_cero=porcentaje_cero,
        error=None,
    )


@bp.route('/actualizacion-masiva/aplicar', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def actualizacion_masiva_aplicar():
    """Aplica la actualización masiva de precios."""
    try:
        categorias_ids_raw = request.form.get('categorias_ids', '[]')
        categorias_ids = json.loads(categorias_ids_raw)
        categorias_ids = [int(cid) for cid in categorias_ids if cid]
    except (json.JSONDecodeError, ValueError):
        flash('Error al procesar las categorías seleccionadas.', 'danger')
        return redirect(url_for('productos.actualizacion_masiva'))

    try:
        porcentaje = Decimal(str(request.form.get('porcentaje', '0')))
    except Exception:
        flash('El porcentaje ingresado no es válido.', 'danger')
        return redirect(url_for('productos.actualizacion_masiva'))

    actualizar_costo = request.form.get('actualizar_costo') == 'y'
    notas = request.form.get('notas', '').strip() or None

    try:
        cantidad = actualizacion_precio_service.aplicar_actualizacion(
            categorias_ids=categorias_ids,
            porcentaje=porcentaje,
            actualizar_costo=actualizar_costo,
            notas=notas,
        )
        signo = '+' if porcentaje > 0 else ''
        flash(
            f'Se actualizaron {cantidad} productos con un {signo}{porcentaje}%.',
            'success',
        )
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('productos.actualizacion_masiva'))


def _decimal_serializer(obj):
    """Convierte Decimal a str para serialización JSON."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f'Objeto de tipo {type(obj)} no es serializable a JSON')


def _resultado_a_session(resultado: ImportacionResult, nombre_archivo: str) -> None:
    """Serializa ImportacionResult a session como JSON."""
    data = {
        'filas_validas': resultado.filas_validas,
        'filas_actualizar': resultado.filas_actualizar,
        'errores': resultado.errores,
        'advertencias': resultado.advertencias,
        'categorias_nuevas': resultado.categorias_nuevas,
        'nombre_archivo': nombre_archivo,
    }
    session['importacion_resultado'] = json.dumps(data, default=_decimal_serializer)


def _resultado_desde_session() -> tuple[ImportacionResult, str] | None:
    """Deserializa ImportacionResult desde session."""
    raw = session.get('importacion_resultado')
    if not raw:
        return None
    data = json.loads(raw)

    # Reconvertir strings a Decimal en filas válidas y a actualizar
    campos_decimal = [
        'precio_costo',
        'precio_venta',
        'iva_porcentaje',
        'stock_inicial',
        'stock_minimo',
    ]
    for lista in (data['filas_validas'], data['filas_actualizar']):
        for fila in lista:
            for campo in campos_decimal:
                if campo in fila and fila[campo] is not None:
                    fila[campo] = Decimal(str(fila[campo]))

    resultado = ImportacionResult(
        filas_validas=data['filas_validas'],
        filas_actualizar=data['filas_actualizar'],
        errores=data['errores'],
        advertencias=data['advertencias'],
        categorias_nuevas=data['categorias_nuevas'],
    )
    return resultado, data.get('nombre_archivo', '')


def _preparar_preview_context(resultado: ImportacionResult) -> dict:
    """Prepara el contexto para el template de preview."""
    # Agrupar errores por fila
    errores_por_fila: OrderedDict[int, list[str]] = OrderedDict()
    for err in resultado.errores:
        fila_num = err['fila']
        if fila_num not in errores_por_fila:
            errores_por_fila[fila_num] = []
        msg = err.get('mensaje', '')
        if err.get('campo'):
            msg = f"{err['campo']}: {msg}"
        errores_por_fila[fila_num].append(msg)

    # Agrupar advertencias por fila
    advertencias_por_fila: OrderedDict[int, list[str]] = OrderedDict()
    for adv in resultado.advertencias:
        fila_num = adv['fila']
        if fila_num not in advertencias_por_fila:
            advertencias_por_fila[fila_num] = []
        advertencias_por_fila[fila_num].append(adv.get('mensaje', ''))

    total_filas = (
        len(resultado.filas_validas)
        + len(resultado.filas_actualizar)
        + len(errores_por_fila)
        + len(advertencias_por_fila)
    )

    return {
        'resultado': resultado,
        'errores_por_fila': errores_por_fila,
        'advertencias_por_fila': advertencias_por_fila,
        'filas_con_error': len(errores_por_fila),
        'filas_con_advertencia': len(advertencias_por_fila),
        'total_filas': total_filas,
    }


@bp.route('/importar')
@login_required
@empresa_aprobada_required
@admin_required
def importar():
    """Página de importación masiva de productos."""
    form = ImportacionProductosForm()
    return render_template('productos/importar.html', form=form)


@bp.route('/importar/plantilla')
@login_required
@empresa_aprobada_required
@admin_required
def importar_plantilla():
    """Descarga la plantilla Excel para importación de productos."""
    output = generar_plantilla_excel(current_user.empresa_id)
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={
            'Content-Disposition': 'attachment; filename=plantilla_importacion_productos.xlsx',
        },
    )


@bp.route('/importar/preview', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def importar_preview():
    """Preview HTMX de importación masiva de productos."""
    form = ImportacionProductosForm()

    if not form.validate_on_submit():
        errores = []
        for campo, msgs in form.errors.items():
            for msg in msgs:
                errores.append(msg)
        return render_template(
            'productos/_preview_importacion.html',
            error='; '.join(errores),
            resultado=None,
        )

    archivo = form.archivo.data
    nombre_archivo = archivo.filename
    modo_duplicados = form.modo_duplicados.data
    crear_categorias = form.crear_categorias.data

    try:
        filas = parsear_archivo(archivo, nombre_archivo)
    except ValueError as e:
        return render_template(
            'productos/_preview_importacion.html',
            error=str(e),
            resultado=None,
        )

    if not filas:
        return render_template(
            'productos/_preview_importacion.html',
            error='El archivo no contiene filas de datos.',
            resultado=None,
        )

    resultado = validar_importacion(
        filas,
        current_user.empresa_id,
        crear_categorias=crear_categorias,
        modo_duplicados=modo_duplicados,
    )

    # Guardar en session para el paso de aplicar
    _resultado_a_session(resultado, nombre_archivo)

    context = _preparar_preview_context(resultado)
    context['modo_duplicados'] = modo_duplicados
    context['crear_categorias'] = crear_categorias
    context['error'] = None

    return render_template('productos/_preview_importacion.html', **context)


@bp.route('/importar/aplicar', methods=['POST'])
@login_required
@empresa_aprobada_required
@admin_required
def importar_aplicar():
    """Aplica la importación masiva de productos."""
    datos = _resultado_desde_session()
    if not datos:
        flash('No hay datos de importación para aplicar. Volvé a subir el archivo.', 'danger')
        return redirect(url_for('productos.importar'))

    resultado, nombre_archivo = datos
    crear_categorias = request.form.get('crear_categorias') == 'y'

    try:
        auditoria = aplicar_importacion(
            resultado=resultado,
            empresa_id=current_user.empresa_id,
            usuario_id=current_user.id,
            crear_categorias=crear_categorias,
            nombre_archivo=nombre_archivo,
        )
        db.session.commit()

        partes_mensaje = []
        if auditoria.filas_importadas > 0:
            partes_mensaje.append(f'{auditoria.filas_importadas} importado(s)')
        if auditoria.filas_actualizadas > 0:
            partes_mensaje.append(f'{auditoria.filas_actualizadas} actualizado(s)')
        if auditoria.categorias_creadas > 0:
            partes_mensaje.append(f'{auditoria.categorias_creadas} categoría(s) creada(s)')

        flash(
            f'Importación exitosa: {", ".join(partes_mensaje)}.',
            'success',
        )
    except Exception as e:
        db.session.rollback()
        flash(f'Error al aplicar la importación: {e}', 'danger')
        return redirect(url_for('productos.importar'))
    finally:
        session.pop('importacion_resultado', None)

    return redirect(url_for('productos.index'))


@bp.route('/nuevo', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def nuevo():
    """Crear nuevo producto."""
    form = ProductoForm()

    if form.validate_on_submit():
        # Verificar código único dentro de la empresa
        existente = Producto.query_empresa().filter_by(codigo=form.codigo.data).first()
        if existente:
            flash('Ya existe un producto con ese código.', 'danger')
            categorias_padre = (
                Categoria.query_empresa()
                .filter_by(activa=True, padre_id=None)
                .order_by(Categoria.nombre)
                .all()
            )
            return render_template(
                'productos/form.html',
                form=form,
                titulo='Nuevo Producto',
                categorias_padre=categorias_padre,
            )

        categoria_id = _resolver_categoria_id(
            form.categoria_padre_id.data,
            form.subcategoria_id.data,
        )

        producto = Producto(
            codigo=form.codigo.data,
            codigo_barras=form.codigo_barras.data or None,
            nombre=form.nombre.data,
            descripcion=form.descripcion.data,
            categoria_id=categoria_id,
            unidad_medida=form.unidad_medida.data,
            precio_costo=form.precio_costo.data,
            precio_venta=form.precio_venta.data,
            iva_porcentaje=Decimal(str(form.iva_porcentaje.data)),
            stock_actual=form.stock_actual.data or 0,
            stock_minimo=form.stock_minimo.data or 0,
            proveedor_id=form.proveedor_id.data if form.proveedor_id.data else None,
            ubicacion=form.ubicacion.data,
            activo=form.activo.data,
            empresa_id=current_user.empresa_id,
        )

        db.session.add(producto)
        db.session.commit()

        flash(f'Producto "{producto.nombre}" creado correctamente.', 'success')
        return redirect(url_for('productos.index'))

    categorias_padre = (
        Categoria.query_empresa()
        .filter_by(activa=True, padre_id=None)
        .order_by(Categoria.nombre)
        .all()
    )

    return render_template(
        'productos/form.html',
        form=form,
        titulo='Nuevo Producto',
        categorias_padre=categorias_padre,
    )


@bp.route('/<int:id>')
@login_required
def detalle(id):
    """Ver detalle de producto."""
    producto = Producto.get_o_404(id)
    actualizaciones_precio = producto.actualizaciones_precio.limit(20).all()
    return render_template(
        'productos/detalle.html',
        producto=producto,
        actualizaciones_precio=actualizaciones_precio,
    )


@bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@empresa_aprobada_required
def editar(id):
    """Editar producto."""
    producto = Producto.get_o_404(id)
    form = ProductoForm(obj=producto)
    categorias_padre = (
        Categoria.query_empresa()
        .filter_by(activa=True, padre_id=None)
        .order_by(Categoria.nombre)
        .all()
    )

    categoria_padre_id_actual = 0
    subcategoria_id_actual = 0

    if producto.categoria:
        if producto.categoria.padre_id:
            categoria_padre_id_actual = producto.categoria.padre_id
            subcategoria_id_actual = producto.categoria.id
        else:
            categoria_padre_id_actual = producto.categoria.id

    if request.method == 'GET':
        form.categoria_padre_id.data = categoria_padre_id_actual
        form.subcategoria_id.data = subcategoria_id_actual
        # Normalizar IVA: Decimal('10.50') → '10.5' para que coincida con choices
        if producto.iva_porcentaje is not None:
            iva_norm = str(producto.iva_porcentaje.normalize())
            form.iva_porcentaje.data = iva_norm

    if form.validate_on_submit():
        # Verificar código único (excluyendo el actual) dentro de la empresa
        existente = (
            Producto.query_empresa()
            .filter(Producto.codigo == form.codigo.data, Producto.id != id)
            .first()
        )
        if existente:
            flash('Ya existe otro producto con ese código.', 'danger')
            return render_template(
                'productos/form.html',
                form=form,
                titulo='Editar Producto',
                producto=producto,
                categorias_padre=categorias_padre,
            )

        categoria_id = _resolver_categoria_id(
            form.categoria_padre_id.data,
            form.subcategoria_id.data,
        )

        producto.codigo = form.codigo.data
        producto.codigo_barras = form.codigo_barras.data or None
        producto.nombre = form.nombre.data
        producto.descripcion = form.descripcion.data
        producto.categoria_id = categoria_id
        producto.unidad_medida = form.unidad_medida.data
        producto.precio_costo = form.precio_costo.data
        producto.precio_venta = form.precio_venta.data
        producto.iva_porcentaje = Decimal(str(form.iva_porcentaje.data))
        producto.stock_minimo = form.stock_minimo.data or 0
        producto.proveedor_id = form.proveedor_id.data if form.proveedor_id.data else None
        producto.ubicacion = form.ubicacion.data
        producto.activo = form.activo.data

        db.session.commit()

        flash(f'Producto "{producto.nombre}" actualizado correctamente.', 'success')
        return redirect(url_for('productos.detalle', id=producto.id))

    return render_template(
        'productos/form.html',
        form=form,
        titulo='Editar Producto',
        producto=producto,
        categorias_padre=categorias_padre,
        categoria_padre_id_actual=categoria_padre_id_actual,
        subcategoria_id_actual=subcategoria_id_actual,
    )


@bp.route('/<int:id>/toggle-activo', methods=['POST'])
@login_required
@empresa_aprobada_required
def toggle_activo(id):
    """Activar/desactivar producto."""
    producto = Producto.get_o_404(id)
    producto.activo = not producto.activo
    db.session.commit()

    estado = 'activado' if producto.activo else 'desactivado'
    flash(f'Producto "{producto.nombre}" {estado}.', 'success')

    if es_peticion_htmx():
        return '', 204

    return redirect(url_for('productos.index'))


@bp.route('/buscar')
@login_required
def buscar():
    """Búsqueda de productos para autocompletado (HTMX/AJAX)."""
    q = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)

    if len(q) < 2:
        return jsonify([])

    productos = (
        Producto.query_empresa()
        .filter(
            Producto.activo.is_(True),
            db.or_(
                Producto.codigo.ilike(f'%{q}%'),
                Producto.nombre.ilike(f'%{q}%'),
                Producto.codigo_barras.ilike(f'%{q}%'),
            ),
        )
        .limit(limit)
        .all()
    )

    return jsonify([p.to_dict() for p in productos])


@bp.route('/tabla')
@login_required
def tabla():
    """Partial de tabla de productos (HTMX)."""
    page = request.args.get('page', 1, type=int)
    busqueda = request.args.get('q', '')
    categoria_id = request.args.get('categoria', 0, type=int)
    solo_activos = request.args.get('activos', '1') == '1'
    solo_bajo_stock = request.args.get('bajo_stock', '0') == '1'

    query = Producto.query_empresa()

    if busqueda:
        query = query.filter(
            db.or_(
                Producto.codigo.ilike(f'%{busqueda}%'),
                Producto.nombre.ilike(f'%{busqueda}%'),
                Producto.codigo_barras.ilike(f'%{busqueda}%'),
            )
        )

    if categoria_id:
        categoria = Categoria.get_o_404(categoria_id)
        if categoria.es_padre:
            categoria_ids = [categoria.id] + [
                subcategoria.id for subcategoria in categoria.subcategorias
            ]
            query = query.filter(Producto.categoria_id.in_(categoria_ids))
        else:
            query = query.filter(Producto.categoria_id == categoria_id)

    if solo_activos:
        query = query.filter(Producto.activo.is_(True))

    if solo_bajo_stock:
        query = query.filter(Producto.stock_actual < Producto.stock_minimo)

    query = query.order_by(Producto.nombre)
    productos = paginar_query(query, page)

    return render_template('productos/_tabla.html', productos=productos, busqueda=busqueda)
