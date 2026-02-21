from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Producto, Categoria, Cliente, Proveedor,PresentacionProducto
from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth import logout
from django.db.models import Q, Sum, F
from django.core.paginator import Paginator
from .forms import ProductoForm, ProveedorForm, CategoriaForm,ClienteForm, PresentacionForm
from django.http import HttpResponse
from django.urls import reverse
@login_required
def home(request):
    # Contamos cuántos productos y categorías hay en la BD real
    total_productos = Producto.objects.count()
    total_categorias = Categoria.objects.count()
    
    context = {
        'total_productos': total_productos,
        'total_categorias': total_categorias,
    }
    return render(request, 'base.html', context)

def exit(request):
    logout(request) # Borra la sesión
    return redirect('login') # Te manda al login

from django.http import HttpResponse # Asegúrate de importar esto

def crear_cliente(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            # En lugar de renderizar una página, enviamos la señal de éxito
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'proveedorActualizado' # Usamos el trigger que ya escucha tu JS
            return response
    else:
        form = ClienteForm()

    return render(request, 'core/partials/modal_cliente.html', {'form': form})

def editar_cliente(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            # ESTA ES LA CORRECCIÓN OBLIGATORIA
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'proveedorActualizado' # Dispara la limpieza y recarga
            return response
    else:
        form = ClienteForm(instance=cliente)

    return render(request, 'core/partials/modal_cliente.html', {
        'form': form,
        'cliente': cliente 
    })

def eliminar_cliente(request, pk):
    # Buscamos al cliente o damos error 404 si no existe
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == 'POST':
        # Si el usuario confirmó (dio clic en "Si, eliminar"), lo borramos
        cliente.delete()
        # Recargamos la pagina principal para que desaparezca de la tabla
        return render(request, 'core/partials/cliente_creado.html')

    # Si es GET, mostramos la ventanita de advertencia (modal_eliminar.html)
    return render(request, 'core/partials/modal_eliminarCliente.html', {'cliente': cliente})    

def clientes_list(request):
    # 1. OBTENER CLIENTES (¡Con paréntesis al final!)
    # Usamos .order_by('-id') para ver los nuevos primero
    queryset = Cliente.objects.all().order_by('-id') 

    # 2. BUSCADOR
    search_query = request.GET.get('q', '')
    if search_query:
        queryset = queryset.filter(
            Q(nombres__icontains=search_query) | 
            Q(documento__icontains=search_query)
        )

    # 3. PAGINACIÓN
    # Aquí es donde fallaba si 'queryset' era una función y no una lista
    paginator = Paginator(queryset, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 4. HTMX (Para búsquedas dinámicas)
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/clientes_rows.html', {'page_obj': page_obj})

    # 5. CONTEOS (Totales)
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
    



def productos_list(request):
    # BASE DE DATOS: IGNORAR LOS ELIMINADOS
    productos_activos = Producto.objects.filter(activo=True)

    # 1. LOGICA DE LA TABLA (Busqueda y Filtros)
    # ELIMINAMOS 'padre' de select_related porque ya no existe
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

    # 2. LOGICA DEL DASHBOARD 
    total_productos = productos_activos.count()
    
    # ELIMINADOS: total_padres y total_subproductos
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


def crear_producto(request):
    if request.method == 'POST':
        # IMPORTANTE: request.FILES es obligatorio porque tu modelo tiene imágenes
        form = ProductoForm(request.POST, request.FILES)
        
        if form.is_valid():
            # 1. Pausamos el guardado
            producto = form.save(commit=False)
            
            # 2. Generación automática del código (Estándar ERP)
            ultimo_producto = Producto.objects.order_by('-id').first()
            if ultimo_producto:
                nuevo_numero = ultimo_producto.id + 1
            else:
                nuevo_numero = 1
            producto.codigo = f"PROD-{nuevo_numero:04d}"
            
            # 3. Guardamos en la base de datos
            producto.save()
            
            # 4. Éxito: disparamos el evento para la tabla de productos
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'productoActualizado'
            return response
        else:
            print("❌ ERRORES DE PRODUCTO:", form.errors)
    else:
        form = ProductoForm()

    return render(request, 'core/partials/producto_form.html', {'form': form, 'titulo_modal': 'Nuevo Producto'})



def editar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    
    if request.method == 'POST':
        # IMPORTANTE: request.FILES para mantener la imagen
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


def eliminar_producto(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    
    if request.method == 'POST':
        # SOFT DELETE: Protegemos el historial financiero
        producto.activo = False
        producto.save()
        
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'productoActualizado'
        return response
        
    return render(request, 'core/partials/producto_confirm_delete.html', {'producto': producto})



def proveedor_list(request):
    # 1. Obtener la búsqueda del parámetro 'q' que enviará HTMX
    busqueda = request.GET.get('q', '')
    
    # 2. Filtrar solo proveedores activos (Soft Delete)
    proveedores = Proveedor.objects.filter(activo=True)
    
    if busqueda:
        proveedores = proveedores.filter(
            Q(nombre_comercial__icontains=busqueda) |
            Q(nit__icontains=busqueda) |
            Q(contacto_nombre__icontains=busqueda)
        )

    # 3. Cálculos para los indicadores (KPIs)
    context = {
        'proveedores': proveedores,
        'total_proveedores': Proveedor.objects.filter(activo=True).count(),
        'grandes_contribuyentes': Proveedor.objects.filter(activo=True, clasificacion='grande').count(),
        'creditos_activos': Proveedor.objects.filter(activo=True, dias_credito__gt=0).count(),
    }

    # Si es una petición de HTMX, solo devolvemos el fragmento de la tabla
    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/proveedor_table_rows.html', context) # <-- AQUÍ ESTÁ EL CAMBIO
        
    return render(request, 'core/proveedor_list.html', context)


def proveedor_crear(request):
    if request.method == 'POST':
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'proveedorActualizado'
            return response
        else:
            # Si hay errores, los imprimimos para depurar
            print("ERRORES DEL FORMULARIO:", form.errors)
            
    else:
        # Si es GET, creamos un formulario vacío
        form = ProveedorForm()

    # ESTE RETURN VA AQUÍ AFUERA. ALINEADO CON EL IF/ELSE.
    # Así garantiza que devolverá el HTML tanto si es GET como si falló el POST.
    return render(request, 'core/partials/proveedor_form.html', {'form': form})

def proveedor_editar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == 'POST':
        form = ProveedorForm(request.POST, instance=proveedor)
        if form.validate():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'proveedorActualizado'
            return response
    else:
        form = ProveedorForm(instance=proveedor)
    
    return render(request, 'core/partials/proveedor_form.html', {'form': form})    


def eliminar_proveedor(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    
    if request.method == 'POST':
        # Soft Delete: Cambiamos el estado en lugar de borrar el registro fisico
        proveedor.activo = False 
        proveedor.save()
        
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'proveedorActualizado'
        return response
        
    # Si es GET, devolvemos el modal de confirmación
    return render(request, 'core/partials/proveedor_confirm_delete.html', {'proveedor': proveedor})

# ==========================================
# MÓDULO DE CATEGORÍAS
# ==========================================

def categorias_list(request):
    busqueda = request.GET.get('q', '')
    
    # Filtramos categorias activas (estado=True)
    categorias = Categoria.objects.filter(estado=True).order_by('nombre')
    
    if busqueda:
        categorias = categorias.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda)
        )

    # Paginación
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

def crear_categoria(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            categoria = form.save(commit=False)
            categoria.estado = True 
            categoria.save()
            
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'categoriaActualizada'
            return response
        else:
            print("❌ ERRORES DE VALIDACIÓN:", form.errors)
    else:
        form = CategoriaForm()

    return render(request, 'core/partials/categoria_form.html', {'form': form, 'titulo': 'Nueva Categoría'})


def editar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    
    if request.method == 'POST':
        form = CategoriaForm(request.POST, instance=categoria)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response['HX-Trigger'] = 'categoriaActualizada'
            return response
    else:
        form = CategoriaForm(instance=categoria)

    return render(request, 'core/partials/categoria_form.html', {'form': form, 'titulo': 'Editar Categoría', 'categoria': categoria})


def eliminar_categoria(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    
    if request.method == 'POST':
        # Soft delete: la ocultamos en lugar de borrarla
        categoria.estado = False
        categoria.save()
        
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'categoriaActualizada'
        return response
        
    return render(request, 'core/partials/categoria_confirm_delete.html', {'categoria': categoria})    

def gestionar_presentaciones(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    # Solo traemos las presentaciones activas
    presentaciones = producto.presentaciones.filter(activo=True)
    
    if request.method == 'POST':
        form = PresentacionForm(request.POST)
        if form.is_valid():
            nueva_presentacion = form.save(commit=False)
            nueva_presentacion.producto = producto
            nueva_presentacion.save()
            # Limpiamos el formulario después de guardar para agregar otra
            form = PresentacionForm() 
    else:
        form = PresentacionForm()
        
    return render(request, 'core/partials/presentaciones_modal.html', {
        'producto': producto,
        'presentaciones': presentaciones,
        'form': form
    })