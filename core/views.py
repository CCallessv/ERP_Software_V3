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
from django.db.models import Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db.models import Value
from django.db.models.functions import Lower
from django.db.models import Sum, Value, DecimalField
from django.db.models.functions import Lower, Coalesce

from .forms import (
    ProductoForm,
    ProveedorForm,
    CategoriaForm,
    ClienteForm,
    CompraForm,
    DetalleCompraForm,
    AjusteInventarioForm,
    SolicitudAccesoForm,
    DetalleVentaForm,
    RegistrarPagoForm,
    
    
    
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
    PagoCompra,
    PagoVenta,
    NotaCredito
)

def es_administrador(user):
    if user.is_staff:
        return True
    raise PermissionDenied # Esto lanza el famoso Error 403 (Prohibido)

class CustomLoginView(LoginView):
    template_name = 'core/login.html' 

    def get_success_url(self):
        # 1. Respetar si el usuario intentaba acceder a una URL protegida específica (?next=...)
        url_destino = self.get_redirect_url()
        if url_destino:
            return url_destino
        
        # 2. Si entró por la puerta principal, aplicar el enrutamiento por roles
        if self.request.user.is_staff:
            return reverse_lazy('home')
        
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
@login_required
@user_passes_test(es_administrador)
def clientes_list(request: HttpRequest) -> HttpResponse:
    search_query = request.GET.get('q', '').strip() # .strip() quita espacios accidentales
    
   
    queryset = Cliente.objects.all().order_by('-estado', 'nombres')
    
    if search_query:
        
        queryset = queryset.filter(
            Q(codigo__icontains=search_query) | 
            Q(nombres__icontains=search_query) | 
            Q(documento__icontains=search_query)
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

@login_required
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

@login_required
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

@login_required
@user_passes_test(es_administrador)
def eliminar_cliente(request: HttpRequest, pk: int) -> HttpResponse:
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        # 1. BLOQUEO FINANCIERO: Evitar fuga de deudores (Solo ventas selladas)
        deudas_pendientes = cliente.venta_set.filter(
            estado__iexact='sellada', 
            condicion_pago='credito',
            estado_pago='pendiente',
        ).exists()
        
        if deudas_pendientes:
            # Retornamos el modal nuevamente inyectando un mensaje de error rojo
            return render(request, 'core/partials/modal_eliminarCliente.html', {
                'cliente': cliente,
                'error': "Bloqueo Financiero: Este cliente tiene facturas de crédito pendientes de pago. No puede ser inactivado."
            })

        # 2. SOFT DELETE
        cliente.estado = False
        cliente.save()
        
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true'
        return response
        
    return render(request, 'core/partials/modal_eliminarCliente.html', {'cliente': cliente})
@login_required
@require_POST
@user_passes_test(es_administrador)
def reactivar_cliente(request, pk: int):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    # Reversión del Soft Delete
    cliente.estado = True
    cliente.save()
    
    messages.success(request, f"El cliente {cliente.nombres} ha sido reactivado.")
    
    # Ordenamos a HTMX recargar la tabla para que el cliente vuelva a salir arriba
    response = HttpResponse(status=204)
    response['HX-Refresh'] = 'true'
    return response


@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
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

@login_required
def eliminar_proveedor(request: HttpRequest, pk: int) -> HttpResponse:
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        proveedor.activo = False # El Soft Delete
        proveedor.save()
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true'
        return response
        
    
    return render(request, 'core/partials/proveedor_confirm_delete.html', {'proveedor': proveedor})
@login_required
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

@login_required
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

@login_required
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

@login_required
def eliminar_categoria(request: HttpRequest, pk: int) -> HttpResponse:
    categoria = get_object_or_404(Categoria, pk=pk)
    if request.method == 'POST':
        categoria.estado = False
        categoria.save()
        response = HttpResponse(status=204)
        response['HX-Refresh'] = 'true'
        return response
    return render(request, 'core/partials/categoria_confirm_delete.html', {'categoria': categoria})


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
@require_POST
@login_required
@user_passes_test(es_administrador)
def venta_sellar(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    # 1. VALIDA EL ESTADO INICIAL
    if venta.estado != 'borrador':
        messages.error(request, 'Esta cotización/factura ya fue procesada o anulada.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)
        
    detalles = venta.detalles.all()
    if not detalles.exists():
        messages.warning(request, 'No puedes aprobar una cotización vacía. Agrega productos.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

        # # 2. BLOQUEO FISCAL Y COMERCIAL B2B
    # Validamos CCF (Legalidad)
    if venta.tipo_documento == 'CCF':
        if not venta.cliente.nrc:
            messages.error(request, f"Bloqueo Legal: No puedes emitir un CCF. El cliente {venta.cliente.nombres} no tiene registrado su NRC.")
            return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

    # Validamos FCF (Comercial - La nueva regla que discutimos)
    if venta.tipo_documento == 'FCF' and venta.condicion_pago == 'credito':
        messages.error(request, 'Las facturas FCF deben ser al contado. No se permite crédito para este documento.')
        return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)

    try:
        with transaction.atomic():
            suma_gravadas = Decimal('0.00')

            # 3. RECALCULAR PRECIOS
            for detalle in detalles:
                producto = Producto.objects.select_for_update().get(id=detalle.producto.id)
                
                precio_actual = producto.precio_venta
                if venta.tipo_documento == 'CCF':
                    precio_actual = (precio_actual / Decimal('1.13')).quantize(Decimal('0.01'))
                
                detalle.precio_unitario = precio_actual
                
                subtotal_sin_descuento = detalle.cantidad * precio_actual
                if detalle.descuento > subtotal_sin_descuento:
                    raise ValueError(f"Fallo contable: El precio de {producto.nombre} bajó y el descuento ahora es mayor al total.")
                
                detalle.save()
                
                subtotal_linea = subtotal_sin_descuento - detalle.descuento
                suma_gravadas += subtotal_linea

            # 4. DETERMINAR EL TOTAL REAL
            if venta.tipo_documento == 'CCF':
                iva_real = (suma_gravadas * Decimal('0.13')).quantize(Decimal('0.01'))
                total_real = suma_gravadas + iva_real
            else:
                iva_real = Decimal('0.00')
                total_real = suma_gravadas

            # 4.5 BLOQUEO HÍBRIDO: Prohibido dar crédito en FCF
            if venta.tipo_documento == 'FCF' and venta.condicion_pago == 'credito':
                raise ValueError("Falla de lógica de negocio: Las Facturas de Consumidor Final (FCF) no pueden emitirse al crédito. Deben ser pagadas al contado.")

            # 5. BLOQUEO DE CRÉDITO ESTRICTO
            if venta.condicion_pago == 'credito':
                if venta.cliente.limite_credito <= 0:
                    raise ValueError(f"Venta Denegada: El cliente {venta.cliente.nombres} no tiene crédito autorizado (Límite $0.00).")

                # Sumar toda la deuda existente que está en estado pendiente
                deuda_historica = Venta.objects.filter(
                    cliente=venta.cliente, 
                    condicion_pago='credito', 
                    estado='sellada', 
                    estado_pago='pendiente'
                ).aggregate(total_deuda=Sum('total_pagar'))['total_deuda'] or Decimal('0.00')

                deuda_proyectada = deuda_historica + total_real

                if deuda_proyectada > venta.cliente.limite_credito:
                    # El rollback de transaction.atomic revertirá cualquier cambio hecho arriba
                    raise ValueError(
                        f"Venta Denegada por Riesgo Financiero. "
                        f"Límite del cliente: ${venta.cliente.limite_credito}. "
                        f"Deuda actual pendiente: ${deuda_historica}. "
                        f"Cotización actual: ${total_real.quantize(Decimal('0.01'))}. "
                        f"Proyectado: ${deuda_proyectada.quantize(Decimal('0.01'))} (Supera el límite)."
                    )

            # 6. ACTUALIZAR KÁRDEX
            for detalle in detalles:
                MovimientoInventario.objects.create(
                    producto=detalle.producto,
                    tipo='salida_venta',
                    cantidad=detalle.cantidad, 
                    costo_unitario=detalle.producto.precio_costo,
                    referencia=f"{venta.tipo_documento} - {str(venta.codigo_generacion)[:8]}",
                    usuario=request.user,
                    notas="Venta registrada y descontada automáticamente."
                )

            # 7. CONSOLIDAR EL DOCUMENTO FINAL
            venta.sumatoria_gravadas = suma_gravadas
            venta.iva = iva_real
            venta.total_pagar = total_real
            venta.estado = 'sellada'
            
            # Solo si es al contado marcamos la venta como pagada y CREAMOS EL RECIBO DE DINERO
            if venta.condicion_pago == 'contado':
                venta.estado_pago = 'pagado'
                
                # --- INYECCIÓN FINANCIERA (EL PARCHE) ---
                # Capturamos el metodo de pago que el usuario seleccionó en el frontend
                # Si por algun motivo el formulario no lo envia, asumimos 'Efectivo' por seguridad
                metodo_seleccionado = request.POST.get('metodo_pago')
                if not metodo_seleccionado:
                    metodo_seleccionado = 'efectivo' 
                
                PagoVenta.objects.create(
                    venta=venta,
                    monto=total_real,
                    metodo_pago=metodo_seleccionado,
                    registrado_por=request.user
                )
                # ----------------------------------------
                
            venta.save()
            
            messages.success(request, 'Cotización aprobada. Venta sellada, crédito evaluado y Kárdex descontado.')
            
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f"Error crítico en el sellado: {str(e)}")
        
    return redirect('venta_detalle', codigo_generacion=venta.codigo_generacion)


@login_required
@user_passes_test(es_administrador)
def crear_venta_borrador(request):
    if request.method == 'GET':
        clientes = Cliente.objects.filter(estado=True).exclude(nombres='CLIENTE MOSTRADOR').order_by('nombres')
        return render(request, 'core/partials/venta_borrador_form.html', {'clientes': clientes})

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        tipo_documento = request.POST.get('tipo_documento')
        condicion_pago = request.POST.get('condicion_pago') 

        # QuerySet optimizado para re-renderizar el formulario en caso de error
        clientes_queryset = Cliente.objects.filter(estado=True).exclude(nombres='CLIENTE MOSTRADOR').order_by('nombres')

        # CANDADO 1: CCF requiere obligatoriamente un cliente seleccionado
        if tipo_documento == 'CCF' and not cliente_id:
            return render(request, 'core/partials/venta_borrador_form.html', {
                'error': "No puedes emitir un Crédito Fiscal (CCF) al Cliente Mostrador. Selecciona un cliente con NRC.",
                'clientes': clientes_queryset,
                'tipo_documento_seleccionado': tipo_documento,
                'condicion_pago_seleccionada': condicion_pago
            })

        # CANDADO 2: No se puede otorgar crédito a un cliente no registrado
        if condicion_pago == 'credito' and not cliente_id:
            return render(request, 'core/partials/venta_borrador_form.html', {
                'error': "Riesgo Financiero: No puedes otorgar crédito al Cliente Mostrador. Selecciona un cliente registrado.",
                'clientes': clientes_queryset,
                'tipo_documento_seleccionado': tipo_documento,
                'condicion_pago_seleccionada': condicion_pago
            })

        # CANDADO 3: FCF no permite condiciones de crédito
        if tipo_documento == 'FCF' and condicion_pago == 'credito':
            return render(request, 'core/partials/venta_borrador_form.html', {
                'error': "Las facturas FCF deben ser al contado.",
                'clientes': clientes_queryset,
                'tipo_documento_seleccionado': tipo_documento, 
                'condicion_pago_seleccionada': condicion_pago
            })

        # Una vez superados los filtros de negocio, asignamos el cliente de forma segura
        if not cliente_id:
            try:
                # Asegúrate de que este valor coincida exactamente con el de tu BD
                cliente_seleccionado = Cliente.objects.get(documento="0000-000000-000-0")
            except Cliente.DoesNotExist:
                return render(request, 'core/partials/venta_borrador_form.html', {
                    'error': "Error crítico: No existe el Cliente Mostrador en la base de datos."
                })
        else:
            cliente_seleccionado = get_object_or_404(Cliente, id=cliente_id)

        # CANDADO 4: Si es CCF, asegurar que el cliente seleccionado tenga NRC
        if tipo_documento == 'CCF' and not cliente_seleccionado.nrc:
            return render(request, 'core/partials/venta_borrador_form.html', {
                'error': f"El cliente {cliente_seleccionado.nombres} no tiene NRC registrado. No puede recibir un CCF.",
                'clientes': clientes_queryset,
                'tipo_documento_seleccionado': tipo_documento,
                'condicion_pago_seleccionada': condicion_pago
            })

        # Inserción limpia en la base de datos
        nueva_venta = Venta.objects.create(
            cliente=cliente_seleccionado,
            estado='borrador',
            tipo_documento=tipo_documento,
            condicion_pago=condicion_pago 
        )
        
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('venta_detalle', kwargs={'codigo_generacion': nueva_venta.codigo_generacion})
        return response


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

@login_required
@require_POST
@user_passes_test(es_administrador)
def venta_agregar_producto(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    
    if venta.estado != 'borrador':
        return HttpResponse("Error: Factura sellada.")
        
    producto_id = request.POST.get('producto')
    producto = get_object_or_404(Producto, id=producto_id)
    
    form = DetalleVentaForm(request.POST)
    if not form.is_valid():
        
        error_msg = list(form.errors.values())[0][0]
        return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta, 'error': error_msg})
        
    cantidad_entrante = form.cleaned_data['cantidad']
    descuento_entrante = form.cleaned_data['descuento']

    # 1. Logica de precio e IVA
    precio_base = producto.precio_venta
    precio_real = precio_base
    if venta.tipo_documento == 'CCF':
        precio_real = (precio_base / Decimal('1.13')).quantize(Decimal('0.01'))

    # 2. Bloqueo logico: El descuento no puede ser mayor al valor total de los productos
    subtotal_sin_descuento = cantidad_entrante * precio_real
    if descuento_entrante > subtotal_sin_descuento:
        error_msg = "Error contable: El descuento supera el valor total del producto."
        return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta, 'error': error_msg})

    # 3. Validar stock acumulado
    detalle_existente = DetalleVenta.objects.filter(venta=venta, producto=producto).first()
    cantidad_total_visual = cantidad_entrante
    if detalle_existente:
        cantidad_total_visual += detalle_existente.cantidad

    if cantidad_total_visual > producto.stock:
        error_msg = f"¡Bloqueo de Inventario! Intentas facturar {cantidad_total_visual} unidades, pero solo quedan {producto.stock} en bodega."
        return render(request, 'core/partials/venta_tabla_y_totales.html', {'venta': venta, 'error': error_msg})

    # 4. Ejecucion del guardado
    if detalle_existente:
        detalle_existente.cantidad += cantidad_entrante
        detalle_existente.descuento += descuento_entrante
        detalle_existente.save()
    else:
        DetalleVenta.objects.create(
            venta=venta,
            producto=producto,
            cantidad=cantidad_entrante,        
            precio_unitario=precio_real,
            descuento=descuento_entrante,
            tipo_afectacion='gravada'
        )
    
    venta.refresh_from_db()


    subtotal_neto = Decimal('0.00')
    iva_calculado = Decimal('0.00')
    
    
    total = venta.total_pagar or Decimal('0.00') 
    
    if total > 0:
        subtotal_neto = (total / Decimal('1.13')).quantize(Decimal('0.01'))
        iva_calculado = (total - subtotal_neto).quantize(Decimal('0.01'))
        
    context = {
        'venta': venta,
        'subtotal_neto': subtotal_neto,
        'iva_calculado': iva_calculado
    }
    
    return render(request, 'core/partials/venta_tabla_y_totales.html', context)
    

@login_required
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

@login_required
@user_passes_test(es_administrador)
def venta_detalle(request, codigo_generacion):
    venta = get_object_or_404(Venta, codigo_generacion=codigo_generacion)
    productos_disponibles = Producto.objects.filter(
        activo=True,
        es_vendible=True,
        stock__gt=0
    ).order_by('nombre')
    
    # CALCULOS DINÁMICOS PARA EL COMPROBANTE
    if venta.estado == 'borrador':
        # Si es borrador, calculamos el IVA en tiempo real basado en el total acumulado
        total = venta.total_pagar or Decimal('0.00')
        subtotal_neto = (total / Decimal('1.13')).quantize(Decimal('0.01'))
        iva_calculado = (total - subtotal_neto).quantize(Decimal('0.01'))
    else:
        # Si ya está sellada, consumimos los datos fijos de la base de datos
        subtotal_neto = venta.sumatoria_gravadas
        iva_calculado = venta.iva
    
    context = {
        'venta': venta,
        'productos': productos_disponibles,
        'subtotal_neto': subtotal_neto,
        'iva_calculado': iva_calculado,
    }
    return render(request, 'core/venta_detalle.html', context)

@login_required
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

    # Evitar estados ambiguos. Solo se anula lo que está formalmente sellado.
    if venta.estado != 'sellada': 
        messages.error(request, "Solo puedes anular facturas que ya han sido selladas.")
        return redirect('venta_list')

    if request.method == 'POST':
        motivo = request.POST.get('motivo_anulacion')
        if not motivo:
            messages.error(request, "Bloqueo Contable: Es obligatorio especificar un motivo para emitir la Nota de Crédito.")
            return redirect('venta_list')

        try:
            with transaction.atomic(): 
                # 1. EMISIÓN DE NOTA DE CRÉDITO
                # Este documento respalda legalmente el egreso de dinero y la anulación fiscal.
                NotaCredito.objects.create(
                    venta_origen=venta,
                    monto_revertido=venta.total_pagar,  # Mantenemos el valor real de la transacción
                    motivo_anulacion=motivo,
                    emitida_por=request.user
                )

                # 2. REVERSIÓN DE KÁRDEX
                for detalle in venta.detalles.all():
                    MovimientoInventario.objects.create(
                        producto=detalle.producto,
                        tipo='entrada_ajuste',  # Incrementa el stock de nuevo en bodega
                        cantidad=detalle.cantidad,
                        costo_unitario=detalle.producto.precio_costo,
                        referencia=f"NC Anulación - {str(venta.codigo_generacion)[:8]}",
                        usuario=request.user,
                        notas=f"Devolución automática. Motivo: {motivo}"
                    )

                # 3. ACTUALIZACIÓN DE ESTADO SIN MUTILAR VALORES
                venta.estado = 'anulada'
                # Conservamos venta.total_pagar intacto para auditorías de volumen anulado
                venta.save()

            messages.success(request, f"Factura anulada exitosamente. Se emitió la Nota de Crédito por ${venta.total_pagar} y el stock regresó al inventario.")
        
        except Exception as e:
            messages.error(request, f"Error crítico en la transacción de anulación: {str(e)}")

    return redirect('venta_list')

@login_required
@user_passes_test(es_administrador)
def cuentas_por_cobrar_list(request):
    # 1. Filtramos y calculamos el saldo real en la DB
    pendientes = Venta.objects.filter(
        estado='sellada', 
        estado_pago='pendiente',
        condicion_pago='credito'
    ).annotate(
        monto_abonado=Coalesce(Sum('pagos__monto'), Value(0), output_field=DecimalField()),
        saldo_real=F('total_pagar') - F('monto_abonado')
    ).order_by('fecha_vencimiento') # Ordenamos por fecha de vencimiento (lo más viejo primero)

    # 2. Calculamos el total usando la base de datos directamente
    # Esto es mucho más eficiente que usar sum() en Python
    stats = pendientes.aggregate(
        total_deuda=Sum(F('total_pagar') - F('monto_abonado'))
    )
    
    total_por_cobrar = stats['total_deuda'] or Decimal('0.00')
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
    try:
        # Iniciamos la transacción inmediatamente para poder bloquear la fila
        with transaction.atomic():
            # 1. BLOQUEO DE FILA: Nadie más toca esta venta hasta que terminemos de contar el dinero
            venta = get_object_or_404(Venta.objects.select_for_update(), codigo_generacion=codigo_generacion)

            # 2. VALIDACIÓN LÓGICA
            if venta.estado != 'sellada':
                raise ValueError("Solo puedes registrar cobros de facturas selladas y válidas.")
                
            if venta.estado_pago == 'pagado':
                raise ValueError("Error contable: Esta factura ya está liquidada al 100%.")

            # 3. CÁLCULO EN TIEMPO REAL DE LA DEUDA
            pagos_previos = venta.pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
            deuda_pendiente = venta.total_pagar - pagos_previos

            # 4. INSTANCIAMOS EL FORMULARIO
            # Pasamos la deuda_pendiente al formulario para que el clean_monto haga su trabajo
            form = RegistrarPagoForm(request.POST, deuda_pendiente=deuda_pendiente)
            
            if form.is_valid():
                nuevo_pago = form.save(commit=False)
                nuevo_pago.venta = venta
                nuevo_pago.registrado_por = request.user
                nuevo_pago.save()

                # 5. AUDITORÍA DEL SALDO FINAL
                # Restamos el pago actual a la deuda que calculamos arriba
                saldo_restante = deuda_pendiente - nuevo_pago.monto

                # Si la deuda es cero (o menor por algún error de micro-centavos flotantes), cerramos la cuenta
                if saldo_restante <= Decimal('0.00'):
                    venta.estado_pago = 'pagado'
                    venta.save()
                    messages.success(request, f"Pago de ${nuevo_pago.monto} registrado. La factura ha sido liquidada en su totalidad.")
                else:
                    messages.success(request, f"Abono de ${nuevo_pago.monto} registrado. Saldo pendiente: ${saldo_restante.quantize(Decimal('0.01'))}.")
                    
            else:
                # Si el form.is_valid() falla (ej. intentaron pagar más de lo que deben)
                # Extraemos los errores del formulario para mostrarlos en pantalla
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
                        
    except ValueError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f"Fallo crítico al procesar el pago: {str(e)}")

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

@login_required
@user_passes_test(es_administrador)
def cuentas_por_pagar_list(request):
    # Traemos compras que ya recibimos, que son al credito y que aun debemos
    pendientes = Compra.objects.filter(
        estado__in=['recibida', 'parcial', 'ajustada'], 
        estado_pago='pendiente',
        condicion_pago='credito'
    ).annotate(
        monto_abonado=Coalesce(Sum('pagos__monto'), Value(0), output_field=DecimalField()),
        saldo_real=F('total') - F('monto_abonado')
    ).order_by('fecha_compra')

    total_por_pagar = sum(c.saldo_real for c in pendientes)
    conteo_facturas = pendientes.count()

    context = {
        'pendientes': pendientes,
        'total_por_pagar': total_por_pagar,
        'conteo_facturas': conteo_facturas,
    }
    return render(request, 'core/cxp_list.html', context)

@login_required
@user_passes_test(es_administrador)
def registrar_pago_compra(request, id_publico):
    compra = get_object_or_404(Compra, id_publico=id_publico)
    
    if request.method == 'POST':
        try:
            monto = Decimal(request.POST.get('monto'))
            metodo_pago = request.POST.get('metodo_pago')
            comprobante = request.POST.get('comprobante_pago', '')
            
            # Recalculamos deuda real
            abonado = compra.pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')
            saldo_real = compra.total - abonado
            
            if monto > saldo_real:
                messages.error(request, f"Fallo contable: Solo debes ${saldo_real}. No puedes registrar un pago mayor.")
                return redirect('cxp_list')
                
            PagoCompra.objects.create(
                compra=compra,
                monto=monto,
                metodo_pago=metodo_pago,
                comprobante_pago=comprobante,
                usuario=request.user
            )
            
            # Si el pago liquida la deuda, cerramos la cuenta
            if monto == saldo_real:
                compra.estado_pago = 'pagado'
                compra.save()
                messages.success(request, f"Pago de ${monto} registrado. Deuda con {compra.proveedor.nombre_comercial} liquidada.")
            else:
                messages.success(request, f"Abono de ${monto} registrado exitosamente.")
                
        except Exception as e:
            messages.error(request, f"Error al procesar el pago: {str(e)}")
            
    return redirect('cxp_list')


def reporte_ingresos(request):
    # 1. Captura de fechas del GET (asumo que ya lo tienes así)
    fecha_inicio = request.GET.get('fecha_inicio', timezone.now().date())
    fecha_fin = request.GET.get('fecha_fin', timezone.now().date())

    # 2. Filtrar pagos
    pagos = PagoVenta.objects.filter(fecha_registro__date__gte=fecha_inicio, fecha_registro__date__lte=fecha_fin)
    
    # 3. Suma bruta
    gran_total = pagos.aggregate(total=Sum('monto'))['total'] or Decimal('0.00')

    # ---> AQUÍ VA EL CÓDIGO DE LAS NOTAS DE CRÉDITO <---
    # Filtramos las notas de crédito exactamente en el mismo rango de fechas
    notas_credito = NotaCredito.objects.filter(
        fecha_emision__date__gte=fecha_inicio, 
        fecha_emision__date__lte=fecha_fin
    ).aggregate(total=Sum('monto_revertido'))['total'] or Decimal('0.00')

    # Calculamos el dinero real que quedó en caja
    total_neto = gran_total - notas_credito
    # ---------------------------------------------------

    # 4. Agrupación por método (lo que arreglamos antes)
    totales_por_metodo = pagos.annotate(
        metodo_normalizado=Lower('metodo_pago')
    ).values('metodo_normalizado').annotate(
        total=Coalesce(Sum('monto'), Value(0, output_field=DecimalField()))
    ).order_by('-total')

    # 5. Pasarlo al contexto para que el HTML lo pueda leer
    context = {
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'pagos': pagos,
        'totales_por_metodo': totales_por_metodo,
        'gran_total': gran_total,
        'notas_credito': notas_credito,  # ENVIAR AL HTML
        'total_neto': total_neto         # ENVIAR AL HTML
    }

    return render(request, 'reporte_ingresos.html', context)