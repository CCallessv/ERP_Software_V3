import json
import calendar
from datetime import date
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
from itertools import chain
from operator import attrgetter
from datetime import timedelta
from django.db.models.functions import TruncDate
from django.urls import reverse
from collections import defaultdict
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

from .forms import (
    ProductoForm,
    ProveedorForm,
    CategoriaForm,
    ClienteForm,
    CompraForm,
    DetalleCompraForm,
    AjusteInventarioForm,
    SolicitudAccesoForm,
    
    
)
from .models import (
    Producto,
    Categoria,
    Proveedor,
    Compra,
    DetalleCompra,
    Venta,
    Cliente,
    DetalleVenta,
    AjusteInventario,
    MovimientoInventario,
)

def es_administrador(user):
    if user.is_staff:
        return True
    raise PermissionDenied # Esto lanza el famoso Error 403 (Prohibido)

class CustomLoginView(LoginView):
    template_name = 'core/login.html' 

    def get_success_url(self):
        # Aqui interceptamos a donde va el usuario DESPUES de poner bien su clave
        if self.request.user.is_staff:
            return reverse_lazy('home') # El administrador/gerente va al Dashboard
        
        # Si no es staff (es bodeguero u operativo), va directo a productos
        return reverse_lazy('productos_list')

@login_required
@user_passes_test(es_administrador)
def home(request):
    hoy = timezone.now()

    # 1. Capturar filtros de la URL (GET). Si no hay, usa el actual.
    try:
        mes_seleccionado = int(request.GET.get('mes', hoy.month))
        anio_seleccionado = int(request.GET.get('anio', hoy.year))
    except ValueError:
        mes_seleccionado = hoy.month
        anio_seleccionado = hoy.year

    # Obtener el último día del mes seleccionado para el gráfico
    _, ultimo_dia = calendar.monthrange(anio_seleccionado, mes_seleccionado)

    # 2. Valor del Inventario (Global, no depende del mes)
    inventario = Producto.objects.aggregate(valor_total=Sum(F('stock') * F('precio_costo')))
    valor_inventario = inventario['valor_total'] or 0

    # 3. Ventas del Periodo (CORRECCIÓN: uso de __iexact)
    ventas_mes = Venta.objects.filter(
        fecha_hora_emision__year=anio_seleccionado,
        fecha_hora_emision__month=mes_seleccionado,
        estado__iexact='sellada' 
    )
    total_ventas = ventas_mes.aggregate(total=Sum('total_pagar'))['total'] or 0
    cantidad_ventas = ventas_mes.count()
    estados_validos_compra = ['recibida', 'parcial', 'ajustada']

    compras_mes = Compra.objects.filter(
    fecha_compra__year=anio_seleccionado,
    fecha_compra__month=mes_seleccionado,
    estado__in=estados_validos_compra # Cambiamos iexact por __in
)
    total_compras = compras_mes.aggregate(total_suma=Sum('total'))['total_suma'] or 0
    cantidad_compras = compras_mes.count()

    # 4. Alertas de Stock Bajo (Global)
    alertas_query = Producto.objects.filter(activo=True, stock__lte=F('stock_minimo'))
    stock_bajo = alertas_query.count()
    productos_alerta = alertas_query.order_by('stock')[:5]

    # 5. Últimas Transacciones
    ultimas_ventas = Venta.objects.filter(
        estado__iexact='sellada'
    ).select_related('cliente').order_by('-fecha_hora_emision')[:5]

    # =========================================================
    # 6. TENDENCIA (Acoplado al mes y año seleccionado)
    # =========================================================
    ventas_chart = ventas_mes.values('fecha_hora_emision', 'total_pagar')
    dict_ventas = defaultdict(float)
    for v in ventas_chart:
        if v['fecha_hora_emision']:
            dia_str = v['fecha_hora_emision'].strftime('%Y-%m-%d')
            dict_ventas[dia_str] += float(v['total_pagar'])

    compras_chart = compras_mes.values('fecha_compra', 'total')
    dict_compras = defaultdict(float)
    for c in compras_chart:
        if c['fecha_compra']:
            dia_str = c['fecha_compra'].strftime('%Y-%m-%d')
            dict_compras[dia_str] += float(c['total'])

    meses_es = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    chart_labels = []
    chart_ventas = []
    chart_compras = []

    # Iteramos exactamente sobre los días del mes seleccionado
    for dia in range(1, ultimo_dia + 1):
        fecha_actual = date(anio_seleccionado, mes_seleccionado, dia)
        dia_iso = fecha_actual.strftime('%Y-%m-%d')
        dia_display = f"{dia} {meses_es[mes_seleccionado]}" 

        chart_labels.append(dia_display)
        chart_ventas.append(dict_ventas.get(dia_iso, 0.0))
        chart_compras.append(dict_compras.get(dia_iso, 0.0))

    context = {
        'valor_inventario': valor_inventario,
        'total_ventas': total_ventas,
        'cantidad_ventas': cantidad_ventas,
        'total_compras': total_compras,
        'cantidad_compras': cantidad_compras,
        'stock_bajo': stock_bajo,
        'productos_alerta': productos_alerta,
        'ultimas_ventas': ultimas_ventas,
        'chart_labels': json.dumps(chart_labels),
        'chart_ventas': json.dumps(chart_ventas),
        'chart_compras': json.dumps(chart_compras),
        # Variables para mantener seleccionado el filtro en el HTML
        'mes_actual': mes_seleccionado,
        'anio_actual': anio_seleccionado,
    }
    
    return render(request, 'core/home.html', context)

@login_required
def recepciones_list(request):
    
    compras_entrantes = Compra.objects.select_related('proveedor').filter(
        estado__in=['en_transito', 'parcial', 'recibida', 'ajustada']
    ).order_by('-fecha_compra', '-id')
    
    paginator = Paginator(compras_entrantes, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'compras': page_obj,  
        'page_obj': page_obj, 
    }
    return render(request, 'core/recepciones_list.html', context)

@login_required
def recepcion_detalle(request, id_publico):
    #  Agregamos 'recibida' a la lista para evitar el 404 al ver el historial
    # Código corregido:
    compra = get_object_or_404(Compra, id_publico=id_publico, estado__in=['en_transito', 'parcial', 'recibida', 'ajustada'])
    detalles = compra.detalles.all()
    
    # Calculamos lo que falta
    for d in detalles:
        d.ya_recibido = d.cantidad_recibida if d.cantidad_recibida else 0
        d.pendiente = d.cantidad - d.ya_recibido

    # 2. SEGURIDAD: Solo procesamos el formulario si la compra AUN admite mercaderia
    if request.method == 'POST' and compra.estado in ['en_transito', 'parcial']:
        try:
            with transaction.atomic():
                hay_faltante_todavia = False
                
                for detalle in detalles:
                    campo_name = f"cantidad_nueva_{detalle.id}"
                    nueva_entrega_str = request.POST.get(campo_name)
                    
                    if nueva_entrega_str:
                        nueva_entrega = Decimal(nueva_entrega_str)
                        
                        if nueva_entrega > 0:
                            
                            #  delegamos TODO al Kardex
                            MovimientoInventario.objects.create(
                                producto=detalle.producto,
                                tipo='entrada_compra',
                                cantidad=nueva_entrega,
                                costo_unitario=detalle.precio_unitario,
                                referencia=f"Doc. Prov: {compra.numero_comprobante}",
                                usuario=request.user,
                                notas="Ingreso a bodega desde recepción."
                            )
                            
                            
                            if detalle.cantidad_recibida is None:
                                detalle.cantidad_recibida = 0
                            detalle.cantidad_recibida += nueva_entrega
                            detalle.save()

                    
                    if (detalle.cantidad_recibida or 0) < detalle.cantidad:
                        hay_faltante_todavia = True

                # Sellar o mantener abierta
                compra.estado = 'parcial' if hay_faltante_todavia else 'recibida'
                compra.save()
                
                messages.success(request, "Ingreso procesado. El Kárdex actualizó el stock y los costos automáticamente.")
                return redirect('recepciones_list')
                
        except Exception as e:
            messages.error(request, f"Error crítico de inventario: {e}")
    context = {
        'compra': compra,
        'detalles': detalles,
    }
    return render(request, 'core/recepcion_detalle.html', context)

def exit(request: HttpRequest) -> HttpResponse:
    logout(request)
    return redirect('login')

@user_passes_test(es_administrador)
def clientes_list(request: HttpRequest) -> HttpResponse:
    search_query = request.GET.get('q', '')
    queryset = Cliente.objects.all().order_by('-id')
    
    if search_query:
        queryset = queryset.filter(
            Q(nombres__icontains=search_query) | Q(documento__icontains=search_query)
        )
        
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
   
    if request.headers.get('HX-Request') and request.headers.get('HX-Target') == 'tabla-clientes-body':
        return render(request, 'core/partials/clientes_rows.html', {'page_obj': page_obj})
        
    context = {
        'page_obj': page_obj,
        'total_clientes': Cliente.objects.count(),
        'activos': Cliente.objects.filter(estado=True).count(),
        'inactivos': Cliente.objects.filter(estado=False).count(),
        'search_query': search_query
    }
    return render(request, 'core/clientes_list.html', context)

@user_passes_test(es_administrador)
def crear_cliente(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
        return render(request, 'core/partials/modal_cliente.html', {'form': form, 'cliente': None})
        
    form = ClienteForm()
    return render(request, 'core/partials/modal_cliente.html', {'form': form, 'cliente': None})

@user_passes_test(es_administrador)
def editar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
        return render(request, 'core/partials/modal_cliente.html', {'form': form, 'cliente': cliente})
        
    form = ClienteForm(instance=cliente)
    return render(request, 'core/partials/modal_cliente.html', {'form': form, 'cliente': cliente})

@user_passes_test(es_administrador)
def eliminar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        # SOFT DELETE: En lugar de destruir, inactivamos el registro
        cliente.estado = False
        cliente.save()
        
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true'
        return response
        
    return render(request, 'core/partials/modal_eliminarCliente.html', {'cliente': cliente})


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
        form = ProductoForm()
    return render(request, 'core/partials/producto_form.html', {'form': form, 'titulo_modal': 'Nuevo Producto'})


@login_required
@user_passes_test(es_administrador)
def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == 'POST':
        
        form = ProductoForm(request.POST, request.FILES, instance=producto)
        if form.is_valid():
            form.save()
            
            
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('productos_list') 
           
            return response
        else:
           
           return render(request, 'core/partials/producto_form.html', {'form': form, 'producto': producto, 'titulo_modal': f'Editar Producto: {producto.nombre}'})
    else:
        
        form = ProductoForm(instance=producto)
        return render(request, 'core/partials/producto_form.html', {'form': form, 'producto': producto})


@login_required
@user_passes_test(es_administrador)
def eliminar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)

    if request.method == 'POST':
        # PROTECCION ERP: No podemos borrar algo que tiene existencias
        if producto.stock > 0:
            return render(request, 'core/partials/producto_confirm_delete.html', {
                'producto': producto,
                'error': 'No puedes eliminar un producto que aún tiene stock en bodega.'
            })
            
        producto.delete()
        
        # Le decimos a HTMX: Cierra el modal y recarga la lista de productos
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('productos_list')
        return response

    # Si es GET, solo devolvemos el diseño de la ventanita
    return render(request, 'core/partials/producto_confirm_delete.html', {'producto': producto})


def proveedor_list(request: HttpRequest) -> HttpResponse:
    busqueda = request.GET.get('q', '')
    
    # 1. Filtramos solo los activos por defecto, ordenados por ID descendente
    proveedores = Proveedor.objects.filter(activo=True).order_by('-id')
    
    # 2. Aplicamos la búsqueda si existe
    if busqueda:
        proveedores = proveedores.filter(
            Q(nombre_comercial__icontains=busqueda) |
            Q(nit__icontains=busqueda) |
            Q(contacto_nombre__icontains=busqueda)
        )
    
    
    paginator = Paginator(proveedores, 10) # 10 por página
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # 4. Construimos el contexto con tus contadores específicos
    context = {
        'page_obj': page_obj, # Usamos page_obj en lugar de la lista cruda
        'busqueda': busqueda,
        'total_proveedores': Proveedor.objects.filter(activo=True).count(),
        'grandes_contribuyentes': Proveedor.objects.filter(activo=True, clasificacion='grande').count(),
        'creditos_activos': Proveedor.objects.filter(activo=True, dias_credito__gt=0).count(),
        'activos': Proveedor.objects.filter(activo=True).count(),      
        'inactivos': Proveedor.objects.filter(activo=False).count(),
    }
    
    # 5. La magia de HTMX para la búsqueda/paginación
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/proveedor_table_rows.html', context)
        
    return render(request, 'core/proveedor_list.html', context)


def proveedor_crear(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            # Cierra el modal y refresca la tabla entera
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
        
        # Si hay errores, devolvemos el HTML del modal para que HTMX actualice el cuadro blanco
        return render(request, 'core/partials/proveedor_form.html', {'form': form, 'proveedor': None})
        
    form = ProveedorForm()
    return render(request, 'core/partials/proveedor_form.html', {'form': form, 'proveedor': None})


def proveedor_editar(request: HttpRequest, pk: int) -> HttpResponse:
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Refresh'] = 'true'
            return response
            
        return render(request, 'core/partials/proveedor_form.html', {'form': form, 'proveedor': proveedor})
        
    form = ProveedorForm(instance=proveedor)
    return render(request, 'core/partials/proveedor_form.html', {'form': form, 'proveedor': proveedor})


def eliminar_proveedor(request: HttpRequest, pk: int) -> HttpResponse:
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.activo = False # El Soft Delete
        proveedor.save()
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true'
        return response
        
    return render(request, 'core/partials/Proveedor_confirm_delete.html', {'proveedor': proveedor})

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


@require_POST
@user_passes_test(es_administrador)
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
                # BLOQUEO DE FILA: Evita que otro cajero toque este stock en el mismo milisegundo
                producto = Producto.objects.select_for_update().get(id=detalle.producto.id)
                
                # CÁLCULO ESTRICTO: Determinar cuánto descontar realmente del Kárdex
                factor = detalle.presentacion.factor_conversion if detalle.presentacion else Decimal('1.00')
                descuento_real_kardex = detalle.cantidad * factor
                
                # Validar otra vez. El stock pudo cambiar desde que el cajero armó el borrador.
                if descuento_real_kardex > producto.stock:
                    raise ValueError(f"Stock insuficiente para {producto.nombre}. Alguien más lo facturó primero. Quedan {producto.stock} {producto.get_unidad_medida_base_display()} en bodega.")
                
                producto.stock -= descuento_real_kardex
                producto.save()
            
            venta.estado = 'sellada' 
            venta.save()
            messages.success(request, 'Documento sellado de forma segura. Inventario actualizado.')        
    except ValueError as e:
        messages.error(request, str(e))
        
    return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

#Modulo de COMPRAS
@login_required
@user_passes_test(es_administrador)
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
        form = CompraForm()
    return render(request, 'core/partials/compra_form.html', {'form': form})


@login_required
@user_passes_test(es_administrador)
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
@user_passes_test(es_administrador)
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
@user_passes_test(es_administrador)
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
@user_passes_test(es_administrador)
def compra_confirmar(request: HttpRequest, id_publico) -> HttpResponse:
    compra = get_object_or_404(Compra, id_publico=id_publico)
    
    if request.method == 'POST':
        # Validación 1: Que no se procese doble
        if compra.estado != 'borrador':
            messages.error(request, "Esta factura ya fue procesada y no está en borrador.")
            return redirect('compra_detalle', id_publico=compra.id_publico)
            
        detalles = DetalleCompra.objects.filter(compra=compra)
        
        # Validación 2: Que no vaya vacía
        if not detalles.exists():
            messages.error(request, "No puedes procesar una factura sin productos.")
            return redirect('compra_detalle', id_publico=compra.id_publico)
            
        try:
            # EL CAMBIO CLAVE: Despachamos el camión hacia la bodega.
            compra.estado = 'en_transito'
            compra.save()
            
            messages.success(request, "Factura confirmada. Mercadería en camino a Recepción de Bodega.")
            
        except Exception as e:
            messages.error(request, f"Error crítico de base de datos: {e}")
            
    return redirect('compra_detalle', id_publico=compra.id_publico)


@login_required
@user_passes_test(es_administrador)
def compra_list(request: HttpRequest) -> HttpResponse:


    compras = Compra.objects.select_related('proveedor').all().order_by('-fecha_compra', '-id')
    paginator = Paginator(compras, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'compras': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'core/compra_list.html', context)


@login_required
@user_passes_test(es_administrador)
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

@login_required
@user_passes_test(es_administrador)
def compra_resolver_discrepancia(request, id_publico):
    compra = get_object_or_404(Compra, id_publico=id_publico)
    
    if request.method == 'POST':
        observaciones = request.POST.get('observaciones')
        accion = request.POST.get('accion') # 'esperar' o 'ajustar'
        
        with transaction.atomic():
            compra.observaciones = observaciones
            
            if accion == 'ajustar':
                # RECALCULO FINANCIERO: Ajustar el total de la factura a lo recibido
                nuevo_subtotal = sum(d.cantidad_recibida * d.precio_unitario for d in compra.detalles.all())
                compra.subtotal = nuevo_subtotal
                compra.impuestos = nuevo_subtotal * Decimal('0.13')
                compra.total = compra.subtotal + compra.impuestos
                compra.estado = 'ajustada' # Sella la factura
                messages.success(request, f"Factura ajustada financieramente. Nuevo total: ${compra.total}")
            
            else:
                # Se queda como parcial, permitiendo que bodega vuelva a recibir después
                messages.warning(request, "Compra marcada como pendiente. Se espera el remanente de mercadería.")
            
            compra.save()
            
    return redirect('compra_detalle', id_publico=compra.id_publico)


#MODULO DE VENTAS 

@login_required
@user_passes_test(es_administrador)
def crear_venta_borrador(request):
    # 1. Si HTMX pide el formulario (GET) para abrir el modal
    if request.method == 'GET':
        clientes = Cliente.objects.filter(estado=True).order_by('nombres')
        return render(request, 'core/partials/venta_borrador_form.html', {'clientes': clientes})

    # 2. Si HTMX envía los datos para guardar (POST)
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        tipo_documento = request.POST.get('tipo_documento')

        # Validación estricta
        if not cliente_id or not tipo_documento:
            clientes = Cliente.objects.filter(estado=True).order_by('nombres')
            # Devolvemos el mismo modal pero con un mensaje de error inyectado
            return render(request, 'core/partials/venta_borrador_form.html', {
                'clientes': clientes,
                'error': "Faltan datos. Debes seleccionar un cliente y el tipo de documento."
            })

        cliente_seleccionado = get_object_or_404(Cliente, id=cliente_id)

        # Crear la venta
        nueva_venta = Venta.objects.create(
            cliente=cliente_seleccionado,
            estado='borrador',
            tipo_documento=tipo_documento
        )
        
        # LA CLAVE: No usamos un redirect normal de Django.
        # Le ordenamos a HTMX que cambie la URL del navegador al detalle de la venta.
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('venta_detalle', kwargs={'codigo_generacion': nueva_venta.codigo_generacion})
        return response


#VENTAS
@login_required
@user_passes_test(es_administrador)
def venta_list(request):
    # 1. Traemos todas las ventas ordenadas
    ventas_lista = Venta.objects.all().order_by('-fecha_hora_emision')
    
    # 2. Las rebanamos en bloques de 10
    paginator = Paginator(ventas_lista, 10) 
    page_number = request.GET.get('page')
    ventas_paginadas = paginator.get_page(page_number)
    
    clientes = Cliente.objects.filter(estado=True).order_by('nombres')
    
    context = {
        'ventas': ventas_paginadas, # Mandamos la rebanada, no el pastel entero
        'clientes': clientes, 
    }
    return render(request, 'core/venta_list.html', context)


@require_POST
@user_passes_test(es_administrador)
def venta_agregar_producto(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    if venta.estado != 'borrador':
        return HttpResponse("Error: Factura sellada.")
        
    producto_id = request.POST.get('producto')
    
    try:
        cantidad_entrante = Decimal(request.POST.get('cantidad', 0))
        descuento_entrante = Decimal(request.POST.get('descuento', 0))
    except Exception:
        return HttpResponse("Error: Valores numéricos inválidos.")
        
    producto = get_object_or_404(Producto, id=producto_id)
    precio_base = producto.precio_venta

    # 1. Buscamos si ya existe ANTES de validar el stock 
    detalle_existente = DetalleVenta.objects.filter(
        venta=venta,
        producto=producto
    ).first()

    # 2. Calculamos la cantidad total real que terminaria en la factura
    cantidad_total_visual = cantidad_entrante
    if detalle_existente:
        cantidad_total_visual += detalle_existente.cantidad

    # 3. Matematica de stock: Como ya no hay presentaciones, la cantidad visual es la real
    cantidad_total_a_descontar = cantidad_total_visual

    # 4. Validamos el total acumulado contra lo que realmente hay en bodega
    if cantidad_total_a_descontar > producto.stock:
        error_msg = f"¡Bloqueo de Inventario! Intentas facturar un total de {cantidad_total_a_descontar} {producto.get_unidad_medida_base_display()}, pero solo quedan {producto.stock} en bodega."
        # Devolvemos la tabla intacta, pero le inyectamos la variable de error
        return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta, 'error': error_msg})

    # 5. Lógica de precio e IVA
    precio_real = precio_base
    if venta.tipo_documento == 'CCF':
        precio_real = (precio_base / Decimal('1.13')).quantize(Decimal('0.01'))

    # 6. Ejecución del guardado (Agrupar vs Crear)
    if detalle_existente:
        detalle_existente.cantidad += cantidad_entrante
        detalle_existente.descuento += descuento_entrante
        detalle_existente.save()
    else:
        # Creación limpia, sin el campo presentacion
        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            cantidad=cantidad_entrante,        
            precio_unitario=precio_real,
            descuento=descuento_entrante,
            tipo_afectacion='gravada'
        )
    
    venta.refresh_from_db()
    return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta})
    



@require_POST
@user_passes_test(es_administrador)
def venta_eliminar_producto(request, detalle_id: int):
    detalle = get_object_or_404(DetalleVenta, id=detalle_id)
    venta = detalle.venta
    
    if venta.estado != 'borrador':
        return HttpResponse("Error: Factura sellada.")
        
    detalle.delete()
    venta.refresh_from_db() 
    
    
    return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta})

@user_passes_test(es_administrador)
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
@login_required
@user_passes_test(es_administrador)
def venta_sellar(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    if venta.estado != 'borrador':
        messages.error(request, 'Esta factura ya fue sellada o anulada.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)
        
    detalles = venta.detalles.all()
    if not detalles.exists():
        messages.warning(request, 'No puedes sellar una factura vacía.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

    try:
        with transaction.atomic():
            for detalle in detalles:
                # 1. Ya no hay presentaciones, la cantidad ingresada es exactamente la cantidad a descontar
                descuento_real_inventario = detalle.cantidad
                
                # 2. CREAMOS EL MOVIMIENTO. El modelo Kárdex validará negativos y restará el stock.
                MovimientoInventario.objects.create(
                    producto=detalle.producto,
                    tipo='salida_venta',
                    cantidad=descuento_real_inventario, 
                    costo_unitario=detalle.producto.precio_costo,
                    referencia=f"{venta.tipo_documento} - {str(venta.codigo_generacion)[:8]}",
                    usuario=request.user,
                    notas="Venta registrada y descontada automáticamente."
                )
            
            # 3. Marcamos la venta como finalizada
            venta.estado = 'sellada' 
            venta.save()
            
            messages.success(request, 'Factura sellada. Kárdex actualizado con rastro de auditoría exacto.')
            
    except ValueError as e:
        # Atrapa el error de "Stock en negativo" si se intenta vender más de lo que hay
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f"Error crítico en el sellado: {str(e)}")
        
    return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

@user_passes_test(es_administrador)
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
    paginator = Paginator(ajustes, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'ajustes': page_obj,
        'page_obj': page_obj,
    }

    return render(request, 'core/ajuste_list.html', context)

@login_required
def crear_ajuste(request):
    if request.method == 'POST':
        form = AjusteInventarioForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Guardamos el documento del ajuste (SIN MATEMÁTICAS AQUÍ)
                    ajuste = form.save(commit=False)
                    ajuste.usuario = request.user
                    ajuste.save() 
                    
                    # 2. Traducimos el tipo de ajuste al idioma del Kárdex
                
                    tipo_kardex = 'ajuste_entrada' if ajuste.tipo == 'entrada' else 'ajuste_salida'

                    # 3. Disparamos el motor del Kárdex. ÉL hará la suma/resta por nosotros
                    MovimientoInventario.objects.create(
                        producto=ajuste.producto,
                        tipo=tipo_kardex,
                        cantidad=ajuste.cantidad,
                        costo_unitario=ajuste.producto.precio_costo,
                        referencia=f"Ajuste - Motivo: {ajuste.motivo}",
                        usuario=request.user,
                        notas="Generado automáticamente desde el módulo de Ajustes"
                    )

                messages.success(request, f"Ajuste registrado. El Kárdex ha actualizado el stock.")
                return redirect('ajuste_list')
                
            except ValueError as e:
                # Si el Kárdex detecta que el stock queda en negativo, lanzará el error aquí
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error al procesar el ajuste: {str(e)}")
        else:
            messages.error(request, "Revisa los datos del formulario.")
    else:
        form = AjusteInventarioForm()
    
    return render(request, 'core/partials/ajuste_form.html', {'form': form})



@login_required
@user_passes_test(es_administrador)
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
@user_passes_test(es_administrador)
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
@user_passes_test(es_administrador)
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




@login_required
def kardex_detalle(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    
    # Simplemente traemos el historial puro y duro de la base de datos
    movimientos = MovimientoInventario.objects.filter(producto=producto).order_by('-fecha')

    context = {
        'producto': producto,
        'movimientos': movimientos,
    }
    return render(request, 'core/kardex_detalle.html', context)

@login_required
def kardex_list(request):
    # Traemos todos los productos activos
    productos = Producto.objects.filter(activo=True).order_by('nombre')
    
    # Inteligencia básica: Contamos cuántos productos están por debajo o igual a su stock mínimo
    # Usamos F() para comparar dos campos del mismo modelo directamente en la base de datos
    productos_criticos = productos.filter(stock__lte=F('stock_minimo')).count()
    
    # Valorización del inventario (¿Cuánto dinero tenemos en la bodega a precio de costo?)
    valor_total_bodega = sum(p.stock * p.precio_costo for p in productos)

    # Lógica de paginación
    paginator = Paginator(productos, 10) 
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'productos': productos,
        'productos_criticos': productos_criticos,
        'valor_total_bodega': valor_total_bodega,
    }
    return render(request, 'core/kardex_list.html', context)    

def solicitar_acceso(request):
    if request.method == 'POST':
        formulario = SolicitudAccesoForm(request.POST)
        if formulario.is_valid():
            formulario.save()
            # Mostramos un mensaje de éxito y lo devolvemos al login
            messages.success(request, 'Tu solicitud ha sido enviada al administrador.')
            return redirect('login') # Asegúrate de que 'login' sea el nombre correcto de tu URL
    else:
        formulario = SolicitudAccesoForm()
    
    return render(request, 'core/solicitar_acceso.html', {'formulario': formulario})    

@login_required
def kardex_imprimir_pdf(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    
    movimientos_db = MovimientoInventario.objects.filter(producto=producto).order_by('fecha', 'id')
    
    # 2. SIMULACIÓN DEL KÁRDEX EN MEMORIA
    saldo_fisico_acumulado = Decimal('0.00')
    saldo_financiero_acumulado = Decimal('0.00')
    movimientos_procesados = []

    for mov in movimientos_db:
        # Extraemos el costo y calculamos el valor total del movimiento
        
        costo_u = mov.costo_unitario if mov.costo_unitario else Decimal('0.00')
        valor_movimiento = mov.cantidad * costo_u

        if 'entrada' in mov.tipo:
            saldo_fisico_acumulado += mov.cantidad
            saldo_financiero_acumulado += valor_movimiento
        elif 'salida' in mov.tipo:
            saldo_fisico_acumulado -= mov.cantidad
            saldo_financiero_acumulado -= valor_movimiento
            
        # Protegemos contra divisiones por cero (aunque en salidas el costo promedio no cambia)
        if saldo_fisico_acumulado > 0:
             costo_promedio_momento = saldo_financiero_acumulado / saldo_fisico_acumulado
        else:
             costo_promedio_momento = Decimal('0.00')

        # Inyectamos los saldos calculados al objeto antes de mandarlo a la plantilla
        movimientos_procesados.append({
            'fecha': mov.fecha,
            'tipo_display': mov.get_tipo_display(),
            'referencia': mov.referencia,
            'es_entrada': 'entrada' in mov.tipo,
            'es_salida': 'salida' in mov.tipo,
            'cantidad': mov.cantidad,
            'costo_unitario': costo_u,
            'valor_movimiento': valor_movimiento,
            'saldo_fisico': saldo_fisico_acumulado,
            'costo_promedio': costo_promedio_momento,
            'saldo_financiero': saldo_financiero_acumulado,
        })
    
    context = {
        'producto': producto,
        'movimientos': movimientos_procesados, 
        'fecha_impresion': timezone.now(),
        'usuario_solicitante': request.user
    }
    
    template = get_template('core/kardex_pdf.html')
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Kardex_{producto.codigo}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse(f'Error generando PDF: <pre>{html}</pre>')
        
    return response    

