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

from .forms import (
    ProductoForm,
    ProveedorForm,
    CategoriaForm,
    ClienteForm,
    PresentacionForm,
    CompraForm,
    DetalleCompraForm,
    AjusteInventarioForm,
    AbrirSesionCajaForm,
    CerrarSesionCajaForm,
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
    Caja,
    SesionCaja,
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
    # 1. El Candado de Caja (Nunca se quita)
    sesion_activa = SesionCaja.objects.filter(usuario=request.user, estado='abierta').first()
    if not sesion_activa:
        messages.error(request, "¡Alto ahí! No puedes crear facturas sin abrir un turno de caja primero.")
        return redirect('abrir_sesion') # Asegúrate que coincida con el nombre en tu urls.py

    # 2. Recibir datos del Modal (Por POST)
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        tipo_documento = request.POST.get('tipo_documento')

        # Regla de negocio: No permitimos valores nulos
        if not cliente_id or not tipo_documento:
            messages.error(request, "Faltan datos. Debes seleccionar un cliente y el tipo de documento.")
            return redirect('venta_list')

        # 3. Buscar el cliente en la base de datos
        cliente_seleccionado = get_object_or_404(Cliente, id=cliente_id)

        # 4. Crear el registro inyectando los datos reales
        nueva_venta = Venta.objects.create(
            cliente=cliente_seleccionado,
            estado='borrador',
            tipo_documento=tipo_documento,
            sesion_caja=sesion_activa 
        )
        
        return redirect('venta_detalle', codigo_generacion=nueva_venta.codigo_generacion)

    # Si alguien intenta entrar escribiendo la URL directamente (GET), lo rebotamos
    return redirect('venta_list')



@login_required
def venta_list(request):
    ventas = Venta.objects.all().order_by('-fecha_hora_emision')
    # Extraemos solo los clientes activos para el modal
    clientes = Cliente.objects.filter(estado=True).order_by('nombres')
    
    context = {
        'ventas': ventas,
        'clientes': clientes, # <-- Pieza clave
    }
    return render(request, 'core/venta_list.html', context)


@require_POST
def venta_agregar_producto(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    if venta.estado != 'borrador':
        return HttpResponse("<tr><td colspan='7' class='text-danger'>Error: Factura sellada.</td></tr>")
        
    producto_id = request.POST.get('producto')
    try:
        cantidad = Decimal(request.POST.get('cantidad', 0))
        descuento = Decimal(request.POST.get('descuento', 0))
    except Exception:
        return HttpResponse("<tr><td colspan='7' class='text-danger'>Error: Valores numéricos inválidos.</td></tr>")
        
    producto = get_object_or_404(Producto, id=producto_id)
    
    if cantidad > producto.stock:
        return HttpResponse(
            f"<tr><td colspan='7' class='text-danger text-center fw-bold bg-red-lt'>¡Alerta! Intentas vender {cantidad} pero solo quedan {producto.stock} en Kardex. Venta bloqueada.</td></tr>"
        )

    # --- PARCHE TRIBUTARIO: EXTRACCION DE IVA PARA CCF ---
    # Asumimos que producto.precio_venta ya tiene el IVA incluido (precio público)
    precio_real = producto.precio_venta

    if venta.tipo_documento == 'CCF':
        # Le quitamos el IVA dividiendo entre 1.13 y lo redondeamos a 2 decimales
        precio_real = (producto.precio_venta / Decimal('1.13')).quantize(Decimal('0.01'))
    # -----------------------------------------------------

    DetalleVenta.objects.create(
        venta=venta,
        producto=producto,
        cantidad=cantidad,
        precio_unitario=precio_real, # <-- Aquí inyectamos el precio correcto
        descuento=descuento,
        tipo_afectacion='gravada'
    )
    
    detalles = venta.detalles.all()
    venta.refresh_from_db() # Aquí tu Signal ya hizo la suma y el cálculo de impuestos
    
    html = ""
    for d in detalles:
        html += f"""
        <tr>
            <td>{d.producto.nombre}</td>
            <td>{d.cantidad}</td>
            <td>${d.precio_unitario}</td>
            <td>${d.descuento}</td>
            <td>{d.get_tipo_afectacion_display()}</td>
            <td class="fw-bold">${d.subtotal}</td>
            <td>
               <button hx-post="/ventas/detalle/{d.id}/eliminar/" 
        hx-include="[name='csrfmiddlewaretoken']"
        class="btn btn-sm btn-danger btn-icon">X</button>
            </td>
        </tr>
        """
        
    script_totales = f"""
    <script>
        var caja = document.getElementById('caja-totales');
        if (caja) {{
            caja.innerHTML = `
                <div class="text-muted mb-1">Sumatoria Gravadas: <span class="text-body fw-bold">${venta.sumatoria_gravadas}</span></div>
                <div class="text-muted mb-1">Sumatoria Exentas: <span class="text-body fw-bold">${venta.sumatoria_exentas}</span></div>
                <div class="text-muted mb-2 border-bottom pb-2">IVA (13%): <span class="text-body fw-bold">${venta.iva}</span></div>
                <h2 class="mb-0 text-success">Total: ${venta.total_pagar}</h2>
            `;
        }}
    </script>
    """
    return HttpResponse(html + script_totales)

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
def venta_eliminar_producto(request: HttpRequest, detalle_id: int) -> HttpResponse:
    detalle = get_object_or_404(DetalleVenta, id=detalle_id)
    venta = detalle.venta
    if venta.estado != 'borrador':
        return HttpResponse("<tr><td colspan='7' class='text-danger'>Error: Factura sellada.</td></tr>")
    detalle.delete()
    venta.refresh_from_db()
    detalles = venta.detalles.all()
    html = ""
    if not detalles:
        html = "<tr><td colspan='7' class='text-center text-muted py-5'>Factura en blanco. Selecciona un producto.</td></tr>"
    else:
        for d in detalles:
            html += f"""
            <tr>
                <td>{d.producto.nombre}</td>
                <td>{d.cantidad}</td>
                <td>${d.precio_unitario}</td>
                <td>${d.descuento}</td>
                <td>{d.get_tipo_afectacion_display()}</td>
                <td class="fw-bold">${d.subtotal}</td>
                <td>
                    <button hx-post="/ventas/detalle/{d.id}/eliminar/" 
                    hx-include="[name='csrfmiddlewaretoken']"
                    class="btn btn-sm btn-danger btn-icon">X</button>
                </td>
            </tr>
            """
    script_totales = f"""
    <script>
        var caja = document.getElementById('caja-totales');
        if (caja) {{
            caja.innerHTML = `
                <div class="text-muted mb-1">Sumatoria Gravadas: <span class="text-body fw-bold">${venta.sumatoria_gravadas}</span></div>
                <div class="text-muted mb-1">Sumatoria Exentas: <span class="text-body fw-bold">${venta.sumatoria_exentas}</span></div>
                <div class="text-muted mb-2 border-bottom pb-2">IVA (13%): <span class="text-body fw-bold">${venta.iva}</span></div>
                <h2 class="mb-0 text-success">Total: ${venta.total_pagar}</h2>
            `;
        }}
    </script>
    """
    return HttpResponse(html + script_totales)



@require_POST
def venta_sellar(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    # 1. Blindaje inicial
    if venta.estado != 'borrador':
        messages.error(request, 'Esta factura ya fue sellada o anulada.')
        return redirect('venta_detalle', pk=venta.pk) # Ajusta el nombre de tu vista de detalle
        
    detalles = venta.detalles.all()
    if not detalles.exists():
        messages.warning(request, 'No puedes sellar una factura vacía. Agrega productos.')
        return redirect('venta_detalle', pk=venta.pk)

    # 2. Bloque Transaccional ACID (Todo o Nada)
    try:
        with transaction.atomic():
            for detalle in detalles:
                producto = detalle.producto
                
                # Verificación de stock de último microsegundo
                if detalle.cantidad > producto.stock:
                    raise ValueError(f"Stock insuficiente para {producto.nombre}. Quedan {producto.stock}.")
                
                # Descuento del Kardex
                producto.stock -= detalle.cantidad
                producto.save()
            
            # 3. Cambio de estado de la factura
            venta.estado = 'sellada' 
            venta.save()
            
            # --- NUEVO: SUMAR EL DINERO A LA CAJA DEL CAJERO ---
            # Como ya obligamos a que toda venta tenga una sesion_caja, simplemente la llamamos
            sesion = venta.sesion_caja
            sesion.saldo_esperado += venta.total_pagar
            sesion.save()
            # ---------------------------------------------------
            
            messages.success(request, f'Documento sellado. Se ingresaron ${venta.total_pagar} a tu caja y se descontaron productos del Kardex.')        
    except ValueError as e:
        # Si algo falla, la transacción se revierte sola y mostramos el error
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
def abrir_sesion_caja(request):
    # Regla de negocio: ¿El usuario ya tiene un turno abierto?
    sesion_activa = SesionCaja.objects.filter(usuario=request.user, estado='abierta').first()
    
    if sesion_activa:
        messages.warning(request, f"Ya tienes un turno abierto en {sesion_activa.caja.nombre}. Cierra ese turno antes de abrir otro.")
        return redirect('venta_list') 

    if request.method == 'POST':
        form = AbrirSesionCajaForm(request.POST)
        if form.is_valid():
            sesion = form.save(commit=False)
            sesion.usuario = request.user
            # El saldo esperado inicia exactamente igual al saldo inicial (no hay ventas aún)
            sesion.saldo_esperado = sesion.saldo_inicial 
            sesion.save()
            
            messages.success(request, f"Turno abierto exitosamente en {sesion.caja.nombre}.")
            return redirect('home') # Luego lo cambiaremos para que vaya directo a vender
    else:
        form = AbrirSesionCajaForm()

    return render(request, 'core/caja/abrir_sesion.html', {'form': form})


@login_required
def cerrar_sesion_caja(request):
    # 1. Buscamos la sesión que el usuario tiene abierta actualmente
    sesion_activa = SesionCaja.objects.filter(usuario=request.user, estado='abierta').first()

    if not sesion_activa:
        messages.warning(request, "No tienes ningún turno abierto para cerrar.")
        return redirect('home')

    if request.method == 'POST':
        form = CerrarSesionCajaForm(request.POST, instance=sesion_activa)
        if form.is_valid():
            sesion = form.save(commit=False)
            
            # 2. Registramos la hora de cierre y calculamos el faltante/sobrante
            sesion.fecha_cierre = timezone.now()
            sesion.diferencia = sesion.saldo_real - sesion.saldo_esperado
            sesion.estado = 'cerrada'
            sesion.save()

            # 3. Retroalimentación crítica basada en la auditoría
            if sesion.diferencia == 0:
                messages.success(request, "Turno cerrado con éxito. Caja cuadrada perfectamente.")
            elif sesion.diferencia > 0:
                messages.warning(request, f"Turno cerrado. Tienes un SOBRANTE de ${sesion.diferencia}. Revisa si olvidaste dar un vuelto.")
            else:
                messages.error(request, f"Turno cerrado. Tienes un FALTANTE de ${abs(sesion.diferencia)}. Este monto deberá ser justificado.")

            return redirect('dashboard')
    else:
        form = CerrarSesionCajaForm(instance=sesion_activa)

    context = {
        'form': form,
        'sesion': sesion_activa
    }
    return render(request, 'core/caja/cerrar_sesion.html', context)