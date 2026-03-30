"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views 
from core.views import home, exit, clientes_list, crear_cliente, editar_cliente, eliminar_cliente, productos_list,crear_producto,editar_producto,eliminar_producto
from core.views import proveedor_list, proveedor_crear, proveedor_editar, eliminar_proveedor,categorias_list,crear_categoria,editar_categoria,eliminar_categoria, gestionar_presentaciones,crear_compra
from core.views import compra_detalle,detalle_compra_crear,detalle_compra_eliminar,compra_confirmar,compra_list,compra_eliminar,anular_venta,registrar_movimiento_caja
from core.views import crear_venta_borrador, venta_detalle, venta_agregar_producto, venta_eliminar_producto,venta_sellar,venta_list, generar_pdf_venta, ajuste_list, crear_ajuste,abrir_sesion_caja,cerrar_sesion_caja
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    # Ruta de Login (Usando la plantilla personalizada)
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('crear_cliente/', crear_cliente, name='crear_cliente'),
    # Ruta de Logout (Cerrar sesión)
    path('logout/', exit, name='logout'),
    #ruta clientes
    path('clientes/', clientes_list, name='clientes_list'),
    #editar cliente en donde le pasamos el id aqui /<int:pk>/
    path('editar_cliente/<int:pk>/', editar_cliente, name='editar_cliente'),
    #eliminar cliente siemore pasando el id en esta parte <int:pk>
    path('eliminar_cliente/<int:pk>/', eliminar_cliente, name='eliminar_cliente'),
    #aca lilstamos los proudcto de la lista 
    path('inventario/', productos_list, name='productos_list'),
    #crear un producto nuevo desde forms
    path('inventario/crear/', crear_producto, name='crear_producto'),
    #editar un producto
    path('inventario/editar/<int:pk>/', editar_producto, name='editar_producto'),
    #eliminar un producto         #esta ruta es la que usamos en el html para eliminar un producto  (inventario/eliminar/<int:pk>/)
    path('inventario/eliminar/<int:pk>/', eliminar_producto, name='eliminar_producto'),
    #ruta proveedores
    path('proveedores/',proveedor_list, name='proveedor_list'),
    path('proveedores/crear/', proveedor_crear, name='proveedor_crear'),
    path('proveedores/editar/<int:pk>/', proveedor_editar, name='proveedor_editar'),
    path('proveedores/eliminar/<int:pk>/', eliminar_proveedor, name='eliminar_proveedor'),
    path('categorias/', categorias_list, name='categorias_list'),
    path('categorias/crear/', crear_categoria, name='crear_categoria'),
    path('categorias/editar/<int:pk>/', editar_categoria, name='editar_categoria'),
    path('categorias/eliminar/<int:pk>/', eliminar_categoria, name='eliminar_categoria'),
    #Aca se gestionara lo q son las presentaciones de cada producto
    path('inventario/presentaciones/<int:pk>/', gestionar_presentaciones, name='gestionar_presentaciones'),

   # === MÓDULO DE COMPRAS ===
    path('compras/', compra_list, name='compra_list'),
    path('compras/nueva/', crear_compra, name='crear_compra'),
    path('compras/<uuid:id_publico>/detalle/', compra_detalle, name='compra_detalle'),
    path('compras/<uuid:id_publico>/detalle/crear/', detalle_compra_crear, name='detalle_compra_crear'),
    
    # Nota: Este es el UNICO que se queda con <int> porque borra una fila de producto, no la compra entera.
    path('compras/detalle/<int:detalle_id>/eliminar/', detalle_compra_eliminar, name='detalle_compra_eliminar'), 
    
    path('compras/<uuid:id_publico>/confirmar/', compra_confirmar, name='compra_confirmar'),
    path('compras/<uuid:id_publico>/eliminar/', compra_eliminar, name='compra_eliminar'),
    path('ventas/', venta_list, name='venta_list'),
    path('ventas/nueva/', crear_venta_borrador, name='crear_venta_borrador'),
    
    # Usamos codigo_generacion como llave de seguridad
    path('ventas/<uuid:codigo_generacion>/',venta_detalle, name='venta_detalle'),
    path('ventas/<uuid:codigo_generacion>/agregar-producto/', venta_agregar_producto, name='venta_agregar_producto'),
    path('ventas/detalle/<int:detalle_id>/eliminar/', venta_eliminar_producto, name='venta_eliminar_producto'),
    path('ventas/<uuid:codigo_generacion>/sellar/', venta_sellar, name='venta_sellar'),
    path('ventas/<uuid:codigo_generacion>/pdf/', generar_pdf_venta, name='venta_pdf'),

    # === MODULO DE INVENTARIO / AJUSTES ===
    path('ajustes/', ajuste_list, name='ajuste_list'),
    path('ajustes/nuevo/',  crear_ajuste, name='crear_ajuste'),
    # === MODULO DE CAJA ===
    path('caja/abrir/', abrir_sesion_caja, name='abrir_sesion'),
    path('caja/cerrar/', cerrar_sesion_caja, name='cerrar_sesion'),
    path('ventas/anular/<uuid:codigo_generacion>/', anular_venta, name='anular_venta'),
    path('caja/<int:sesion_id>/movimiento/', registrar_movimiento_caja, name='registrar_movimiento_caja'),
   
]

