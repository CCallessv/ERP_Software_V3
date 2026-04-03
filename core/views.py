from decimal import Decimal
from typing import Any, Dict
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum, F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.db import transaction
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.utils import timezone
from .models import Producto, Venta
from .decorators import rol_requerido

from .forms import (
    ProductoForm,
    ProveedorForm,
    CategoriaForm,
    ClienteForm,
    PresentacionForm,
    CompraForm,
    DetalleCompraForm,
    AjusteInventarioForm,
    
)
from .models import (
    Producto,
    Categoria,
    Proveedor,
    PresentacionProducto,
    Compra,
    DetalleCompra,
    Venta,
    Cliente,
    DetalleVenta,
    AjusteInventario,
)

@login_required
def home(request):
    # 1. Obtenemos el mes y año actual
    hoy = timezone.now()
    mes_actual = hoy.month
    anio_actual = hoy.year

    # 2. Valor del Inventario
    inventario = Producto.objects.aggregate(
        valor_total=Sum(F('stock') * F('precio_costo')) 
    )
    valor_inventario = inventario['valor_total'] or 0

    # 3. Ventas del Período
    ventas_mes = Venta.objects.filter(
        fecha_hora_emision__month=mes_actual,
        fecha_hora_emision__year=anio_actual,
        estado='sellada'
    )
    total_ventas = ventas_mes.aggregate(total=Sum('total_pagar'))['total'] or 0
    cantidad_ventas = ventas_mes.count()

    # --- NUEVO: 3.5 Compras del Período ---
    # Asumo que en tu modelo Compra la fecha se llama 'fecha_emision' 
    # y el total se llama 'total' (basado en el código que me pasaste antes).
    # --- NUEVO: 3.5 Compras del Período ---
    compras_mes = Compra.objects.filter(
        fecha_compra__month=mes_actual,  # <-- CAMBIO AQUÍ
        fecha_compra__year=anio_actual,  # <-- CAMBIO AQUÍ
        estado='completada'
    )
    total_compras = compras_mes.aggregate(total_suma=Sum('total'))['total_suma'] or 0
    cantidad_compras = compras_mes.count()
    # --------------------------------------
    # --------------------------------------

    # 4. Alertas de Stock Bajo
    stock_bajo = Producto.objects.filter(stock__lte=5).count()

    # 5. Últimas Transacciones (Ventas)
    ultimas_ventas = Venta.objects.filter(estado='sellada').order_by('-fecha_hora_emision')[:5]

    context: Dict[str, Any] = {
        'valor_inventario': valor_inventario,
        'total_ventas': total_ventas,
        'cantidad_ventas': cantidad_ventas,
        'total_compras': total_compras,       # Inyectamos el total de compras
        'cantidad_compras': cantidad_compras, # Inyectamos la cantidad de ordenes
        'stock_bajo': stock_bajo,
        'ultimas_ventas': ultimas_ventas,
    }
    
    return render(request, 'core/home.html', context)


def exit(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect('login')


def crear_cliente(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
    else:
        form = ClienteForm()
    return render(request, 'core/partials/modal_cliente.html', {'form': form})


def editar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'actualizarTablaClientes'
            return response
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'core/partials/modal_cliente.html', {'form': form, 'cliente': cliente})


def eliminar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        cliente.delete()
        return render(request, 'core/partials/cliente_creado.html')
    return render(request, 'core/partials/modal_eliminarCliente.html', {'cliente': cliente})


def clientes_list(request: HttpRequest) -> HttpResponse:
    queryset = Cliente.objects.all().order_by('-id')
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(nombres__icontains=search_query) |
            Q(documento__icontains=search_query)
        )
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/clientes_rows.html', {'page_obj': page_obj})
    total = Cliente.objects.count()
    activos = Cliente.objects.filter(estado=True).count()
    inactivos = Cliente.objects.filter(estado=False).count()
    context = {
        'page_obj': page_obj,
        'total_clientes': total,
        'activos': activos,
        'inactivos': inactivos,
        'search_query': search_query
    }
    return render(request, 'core/clientes_list.html', context)


def productos_list(request: HttpRequest) -> HttpResponse:
    productos_activos = Producto.objects.filter(activo=True)
    queryset = productos_activos.select_related('categoria').order_by('-id')
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(nombre__icontains=search_query) |
            Q(codigo__icontains=search_query)
        )
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    total_productos = productos_activos.count()
    stock_bajo = productos_activos.filter(stock__lte=F('stock_minimo')).count()
    data_valor = productos_activos.aggregate(total=Sum(F('stock') * F('precio_costo')))
    valor_total = data_valor['total'] or 0
    context = {
        'productos': page_obj,
        'page_obj': page_obj,
        'search_query': search_query,
        'total_productos': total_productos,
        'stock_bajo': stock_bajo,
        'valor_total': valor_total,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/producto_table_rows.html', context)
    return render(request, 'core/productos_list.html', context)


def crear_producto(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES)
        if form.is_valid():
            producto = form.save(commit=False)
            ultimo_producto = Producto.objects.order_by('-id').first()
            if ultimo_producto:
                nuevo_numero = ultimo_producto.id + 1
            else:
                nuevo_numero = 1
            producto.codigo = f"PROD-{nuevo_numero:04d}"
            producto.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'productoActualizado'
            return response
        else:
            print(" ERRORES DE PRODUCTO:", form.errors)
    else:
        form = ProductoForm()
    return render(request, 'core/partials/producto_form.html', {'form': form, 'titulo_modal': 'Nuevo Producto'})


def editar_producto(request: HttpRequest, pk: int) -> HttpResponse:
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'productoActualizado'
            return response
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'core/partials/producto_form.html', {
        'form': form,
        'titulo_modal': f'Editar: {producto.codigo}'
    })


def eliminar_producto(request: HttpRequest, pk: int) -> HttpResponse:
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        producto.activo = False
        producto.save()
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'productoActualizado'
        return response
    return render(request, 'core/partials/producto_confirm_delete.html', {'producto': producto})


def proveedor_list(request: HttpRequest) -> HttpResponse:
    busqueda = request.GET.get('q', '')
    proveedores = Proveedor.objects.filter(activo=True)
    if busqueda:
        proveedores = proveedores.filter(
            Q(nombre_comercial__icontains=busqueda) |
            Q(nit__icontains=busqueda) |
            Q(contacto_nombre__icontains=busqueda)
        )
    context = {
        'proveedores': proveedores,
        'total_proveedores': Proveedor.objects.filter(activo=True).count(),
        'grandes_contribuyentes': Proveedor.objects.filter(activo=True, clasificacion='grande').count(),
        'creditos_activos': Proveedor.objects.filter(activo=True, dias_credito__gt=0).count(),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/proveedor_table_rows.html', context)
    return render(request, 'core/proveedor_list.html', context)


def proveedor_crear(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'proveedorActualizado'
            return response
        else:
            print("ERRORES DEL FORMULARIO:", form.errors)
    else:
        form = ProveedorForm()
    return render(request, 'core/partials/proveedor_form.html', {'form': form})


def proveedor_editar(request: HttpRequest, pk: int) -> HttpResponse:
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'proveedorActualizado'
            return response
    else:
        form = ProveedorForm(instance=proveedor)
    return render(request, 'core/partials/proveedor_form.html', {'form': form})


def eliminar_proveedor(request: HttpRequest, pk: int) -> HttpResponse:
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.activo = False
        proveedor.save()
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'proveedorActualizado'
        return response
    return render(request, 'core/partials/proveedor_confirm_delete.html', {'proveedor': proveedor})


def categorias_list(request: HttpRequest) -> HttpResponse:
    busqueda = request.GET.get('q', '')
    categorias = Categoria.objects.filter(estado=True).order_by('nombre')
    if busqueda:
        categorias = categorias.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )
    paginator = Paginator(categorias, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'categorias': page_obj,
        'page_obj': page_obj,
        'search_query': busqueda,
        'total_categorias': Categoria.objects.filter(estado=True).count(),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/categoria_table_rows.html', context)
    return render(request, 'core/categorias_list.html', context)


def crear_categoria(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.estado = True
            categoria.save()
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
        else:
            print(" ERRORES DE VALIDACIÓN:", form.errors)
    else:
        form = CategoriaForm()
    return render(request, 'core/partials/categoria_form.html', {'form': form, 'titulo': 'Nueva Categoría'})


def editar_categoria(request: HttpRequest, pk: int) -> HttpResponse:
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
    else:
        form = CategoriaForm(instance=categoria)
    return render(request, 'core/partials/categoria_form.html', {
        'form': form,
        'titulo': 'Editar Categoría',
        'categoria': categoria
    })


def eliminar_categoria(request: HttpRequest, pk: int) -> HttpResponse:
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.estado = False
        categoria.save()
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true'
        return response
    return render(request, 'core/partials/categoria_confirm_delete.html', {'categoria': categoria})


def gestionar_presentaciones(request: HttpRequest, pk: int) -> HttpResponse:
    producto = get_object_or_404(Producto, pk=pk)
    presentaciones = producto.presentaciones.filter(activo=True)
    if request.method == 'POST':
        form = PresentacionForm(request.POST)
        if form.is_valid():
            nueva_presentacion = form.save(commit=False)
            nueva_presentacion.producto = producto
            nueva_presentacion.save()
            form = PresentacionForm()
    else:
        form = PresentacionForm()
    return render(request, 'core/partials/presentaciones_modal.html', {
        'producto': producto,
        'presentaciones': presentaciones,
        'form': form
    })

#Modulo de COMPRAS
@login_required
def crear_compra(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = CompraForm(request.POST)
        if form.is_valid():
            nueva_compra = form.save(commit=False)
            nueva_compra.usuario = request.user
            nueva_compra.estado = 'borrador'
            nueva_compra.save()
            return redirect('compra_detalle', id_publico=nueva_compra.id_publico) 

        else:
            
            print("ERRORES DEL FORMULARIO:", form.errors)
    else:
        form = CompraForm()
    return render(request, 'core/partials/compra_form.html', {'form': form})


@login_required
def compra_detalle(request: HttpRequest, id_publico) -> HttpResponse: 
    compra = get_object_or_404(Compra, id_publico=id_publico) 
    detalles = DetalleCompra.objects.filter(compra=compra)
    form = DetalleCompraForm()
    context = {
        'compra': compra,
        'detalles': detalles,
        'form': form,
    }
    return render(request, 'core/partials/compra_detalle.html', context)


@login_required
def detalle_compra_crear(request: HttpRequest, id_publico) -> HttpResponse: 
    compra = get_object_or_404(Compra, id_publico=id_publico)
    if request.method == 'POST':
        form = DetalleCompraForm(request.POST)
        if form.is_valid():
            detalle = form.save(commit=False)
            detalle.compra = compra
            detalle.subtotal = detalle.cantidad * detalle.precio_unitario
            detalle.save()
            suma_subtotales = DetalleCompra.objects.filter(compra=compra).aggregate(Sum('subtotal'))['subtotal__sum'] or 0
            subtotal_decimal = Decimal(str(suma_subtotales)).quantize(Decimal('0.01'))
            if compra.tipo_comprobante == 'ccf':
                iva = (subtotal_decimal * Decimal('0.13')).quantize(Decimal('0.01'))
            else:
                iva = Decimal('0.00')
            compra.subtotal = subtotal_decimal
            compra.impuestos = iva
            compra.total = subtotal_decimal + iva
            compra.save()
    detalles = DetalleCompra.objects.filter(compra=compra)
    form_limpio = DetalleCompraForm()
    context = {
        'compra': compra,
        'detalles': detalles,
        'form': form_limpio,
    }
    return render(request, 'core/partials/compra_detalle.html', context)


@login_required
def detalle_compra_eliminar(request: HttpRequest, detalle_id: int) -> HttpResponse:
    # Esta función borra el DETALLE, por eso mantiene el detalle_id (int)
    detalle = get_object_or_404(DetalleCompra, pk=detalle_id)
    compra = detalle.compra
    if request.method == 'POST':
        detalle.delete()
        suma_subtotales = DetalleCompra.objects.filter(compra=compra).aggregate(Sum('subtotal'))['subtotal__sum'] or 0
        subtotal_decimal = Decimal(str(suma_subtotales)).quantize(Decimal('0.01'))
        if compra.tipo_comprobante == 'ccf':
            iva = (subtotal_decimal * Decimal('0.13')).quantize(Decimal('0.01'))
        else:
            iva = Decimal('0.00')
        compra.subtotal = subtotal_decimal
        compra.impuestos = iva
        compra.total = subtotal_decimal + iva
        compra.save()
    detalles = DetalleCompra.objects.filter(compra=compra)
    form_limpio = DetalleCompraForm()
    context = {
        'compra': compra,
        'detalles': detalles,
        'form': form_limpio,
    }
    return render(request, 'core/partials/compra_detalle.html', context)


@login_required
def compra_confirmar(request: HttpRequest, id_publico) -> HttpResponse:
    compra = get_object_or_404(Compra, id_publico=id_publico)
    if request.method == 'POST':
        if compra.estado != 'borrador':
            messages.error(request, "Esta factura ya fue ingresada al Kardex y está bloqueada.")
            return redirect('compra_detalle', id_publico=compra.id_publico)
        detalles = DetalleCompra.objects.filter(compra=compra)
        if not detalles.exists():
            messages.error(request, "No puedes procesar una factura sin productos.")
            return redirect('compra_detalle', id_publico=compra.id_publico)
        try:
            with transaction.atomic():
                for detalle in detalles:
                    producto = detalle.producto
                    stock_actual = producto.stock
                    costo_actual = producto.precio_costo
                    cantidad_nueva = detalle.cantidad
                    precio_nuevo = detalle.precio_unitario
                    stock_total_futuro = stock_actual + cantidad_nueva
                    if stock_total_futuro > 0:
                        nuevo_costo = ((stock_actual * costo_actual) + (cantidad_nueva * precio_nuevo)) / stock_total_futuro
                        producto.precio_costo = Decimal(str(nuevo_costo)).quantize(Decimal('0.01'))
                    else:
                        producto.precio_costo = precio_nuevo
                    producto.stock += cantidad_nueva
                    producto.save()
                compra.estado = 'completada'
                compra.save()
            messages.success(request, "Factura procesada. Inventario y costos actualizados correctamente.")
        except Exception as e:
            messages.error(request, f"Error crítico de base de datos: {e}")
    return redirect('compra_detalle', id_publico=compra.id_publico)


@login_required
def compra_list(request: HttpRequest) -> HttpResponse:
    compras = Compra.objects.select_related('proveedor').all()
    context = {
        'compras': compras
    }
    return render(request, 'core/compra_list.html', context)


@login_required
def compra_eliminar(request: HttpRequest, id_publico) -> HttpResponse:
    compra = get_object_or_404(Compra, id_publico=id_publico)
    if request.method == 'POST':
        if compra.estado != 'borrador':
            messages.error(request, "Violación de seguridad: No puedes eliminar una factura que ya afectó el stock del Kardex.")
            return redirect('compra_list')
        numero = compra.numero_comprobante
        compra.delete()
        messages.success(request, f"Borrador {numero} destruido permanentemente.")
    return redirect('compra_list')




#MODULO DE VENTAS 

@login_required
def crear_venta_borrador(request):
    # 1. Recibir datos del Modal (Por POST)
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        tipo_documento = request.POST.get('tipo_documento')

        if not cliente_id or not tipo_documento:
            messages.error(request, "Faltan datos. Debes seleccionar un cliente y el tipo de documento.")
            return redirect('venta_list')

        cliente_seleccionado = get_object_or_404(Cliente, id=cliente_id)

        # 2. Crear el registro SIN caja
        nueva_venta = Venta.objects.create(
            cliente=cliente_seleccionado,
            estado='borrador',
            tipo_documento=tipo_documento
            # ¡Adiós sesion_caja!
        )
        
        return redirect('venta_detalle', codigo_generacion=nueva_venta.codigo_generacion)

    return redirect('venta_list')

@login_required
def venta_list(request):
    ventas = Venta.objects.all().order_by('-fecha_hora_emision')
    clientes = Cliente.objects.filter(estado=True).order_by('nombres')
    
    # Adiós búsqueda de caja activa
    
    context = {
        'ventas': ventas,
        'clientes': clientes, 
        # Adiós sesion_activa
    }
    return render(request, 'core/venta_list.html', context)


@require_POST
def venta_agregar_producto(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    if venta.estado != 'borrador':
        return HttpResponse("Error: Factura sellada.")
        
    producto_id = request.POST.get('producto')
    try:
        cantidad = Decimal(request.POST.get('cantidad', 0))
        descuento = Decimal(request.POST.get('descuento', 0))
    except Exception:
        return HttpResponse("Error: Valores numéricos inválidos.")
        
    producto = get_object_or_404(Producto, id=producto_id)
    
    if cantidad > producto.stock:
        return HttpResponse(f"¡Alerta! Intentas vender {cantidad} pero solo quedan {producto.stock}.")

    # Lógica de precio e IVA
    precio_real = producto.precio_venta
    if venta.tipo_documento == 'CCF':
        precio_real = (producto.precio_venta / Decimal('1.13')).quantize(Decimal('0.01'))

    # Guardado
    DetalleVenta.objects.create(
        venta=venta,
        producto=producto,
        cantidad=cantidad,
        precio_unitario=precio_real,
        descuento=descuento,
        tipo_afectacion='gravada'
    )
    
    venta.refresh_from_db()
    
    # ESTA ES LA ÚNICA RESPUESTA. Cero strings de HTML manuales.
    return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta})


@require_POST
def venta_eliminar_producto(request, detalle_id: int):
    detalle = get_object_or_404(DetalleVenta, id=detalle_id)
    venta = detalle.venta
    
    if venta.estado != 'borrador':
        return HttpResponse("Error: Factura sellada.")
        
    detalle.delete()
    venta.refresh_from_db() 
    
    
    return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta})

def venta_detalle(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    productos_disponibles = Producto.objects.filter(
        activo=True,
        es_vendible=True,
        stock__gt=0
    ).order_by('nombre')
    
    context = {
        'venta': venta,
        'productos': productos_disponibles,
    }
    return render(request, 'core/venta_detalle.html', context)

@require_POST
def venta_sellar(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    if venta.estado != 'borrador':
        messages.error(request, 'Esta factura ya fue sellada o anulada.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)
        
    detalles = venta.detalles.all()
    if not detalles.exists():
        messages.warning(request, 'No puedes sellar una factura vacía. Agrega productos.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

    try:
        with transaction.atomic():
            for detalle in detalles:
                producto = detalle.producto
                if detalle.cantidad > producto.stock:
                    raise ValueError(f"Stock insuficiente para {producto.nombre}. Quedan {producto.stock}.")
                
                producto.stock -= detalle.cantidad
                producto.save()
            
            venta.estado = 'sellada' 
            venta.save()
            
            # ¡Adiós al bloque de sumar dinero a la caja!
            
            messages.success(request, f'Documento sellado. Se descontaron los productos del Kardex. (CxC pendiente)')        
    except ValueError as e:
        messages.error(request, str(e))
        
    return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

def generar_pdf_venta(request, codigo_generacion):
    # Traemos la venta y sus detalles
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    # Le decimos a Django que usaremos una plantilla HTML específica para el PDF
    template_path = 'core/venta_pdf.html'
    context = {'venta': venta}
    
    # Preparamos la respuesta como un archivo PDF
    response = HttpResponse(content_type='application/pdf')
    # "inline" abre el PDF en el navegador. Si quieres que se descargue directo, usa "attachment"
    response['Content-Disposition'] = f'inline; filename="Documento_{venta.codigo_generacion}.pdf"'
    
    # Renderizamos el HTML con los datos de la venta
    template = get_template(template_path)
    html = template.render(context)
    
    # Creamos el PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Hubo un error al generar el PDF: <pre>' + html + '</pre>')
    return response    


@login_required
def ajuste_list(request):
    ajustes = AjusteInventario.objects.select_related('producto', 'usuario').all()
    return render(request, 'core/ajuste_list.html', {'ajustes': ajustes})

@login_required
def crear_ajuste(request):
    if request.method == 'POST':
        form = AjusteInventarioForm(request.POST)
        if form.is_valid():
            try:
                ajuste = form.save(commit=False)
                ajuste.usuario = request.user
                ajuste.save() # El modelo actualizará el stock automáticamente
                messages.success(request, f"Ajuste registrado: {ajuste.get_tipo_display()} aplicado al Kardex.")
                # Asegúrate de importar HttpResponseClientRefresh de django_htmx si usas HTMX, o simplemente recarga
                return redirect('ajuste_list')
            except ValueError as e:
                # Captura el error si el stock queda en negativo
                messages.error(request, str(e))
        else:
            messages.error(request, "Revisa los datos del formulario.")
    else:
        form = AjusteInventarioForm()
    
    return render(request, 'core/partials/ajuste_form.html', {'form': form})



@login_required
@rol_requerido('Administrador') 
def anular_venta(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)

    if venta.estado != 'completada' and venta.estado != 'sellada': 
        messages.error(request, "Solo puedes anular facturas que ya fueron procesadas.")
        return redirect('venta_list')

    if request.method == 'POST':
        try:
            with transaction.atomic(): 
                # 1. Reversion de Inventario (Devolver al Kardex)
                for detalle in venta.detalles.all():
                    producto = detalle.producto
                    producto.stock += detalle.cantidad
                    producto.save()

                # ¡Adiós a la reversión de caja!

                # 2. Ajuste Fiscal
                venta.estado = 'anulada'
                venta.sumatoria_gravadas = 0
                venta.sumatoria_exentas = 0
                venta.sumatoria_no_sujetas = 0
                venta.iva = 0
                venta.total_pagar = 0
                venta.save()

            messages.success(request, f"Factura anulada con éxito. Inventario devuelto al Kardex.")
        
        except Exception as e:
            messages.error(request, f"Operación denegada: {str(e)}")

    return redirect('venta_list')


@login_required
def cuentas_por_cobrar_list(request):
    # Filtramos ventas que:
    # 1. Estén Selladas (ya son deuda real)
    # 2. El estado de pago sea 'pendiente'
    pendientes = Venta.objects.filter(
        estado='sellada', 
        estado_pago='pendiente'
    ).order_by('fecha_hora_emision')

    # Cálculo rápido para el resumen superior
    total_por_cobrar = sum(v.total_pagar for v in pendientes)
    conteo_facturas = pendientes.count()

    context = {
        'pendientes': pendientes,
        'total_por_cobrar': total_por_cobrar,
        'conteo_facturas': conteo_facturas,
    }
    return render(request, 'core/cxc_list.html', context)


@login_required
@require_POST
def registrar_pago_factura(request, codigo_generacion):
    # BUSQUEDA SEGURA: Solo facturas selladas que aún deban dinero
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion, estado='sellada', estado_pago='pendiente')
    
    metodo = request.POST.get('metodo_pago')
    referencia = request.POST.get('comprobante_pago', '').strip()
    
    # 1. Validación de seguridad: No permitimos campos vacíos en el método
    if not metodo:
        messages.error(request, "Error: Debes seleccionar un método de pago.")
        return redirect('cxc_list')

    # 2. Proceso de Cobro (Transaccional)
    try:
        with transaction.atomic():
            venta.metodo_pago = metodo
            # Guardamos una huella de auditoría en las observaciones para que no se pierda el dato
            info_pago = f"\n[PAGO REGISTRADO EL {timezone.now().strftime('%d/%m/%Y %H:%M')}] - Ref: {referencia}"
            venta.observaciones = (venta.observaciones or "") + info_pago
            
            venta.estado_pago = 'pagado'
            venta.save()
            
            messages.success(request, f"Factura {venta.codigo_generacion|stringformat:'s'|slice:':8'} saldada con éxito.")
    except Exception as e:
        messages.error(request, f"Error crítico al registrar el pago: {str(e)}")
        
    return redirect('cxc_list')