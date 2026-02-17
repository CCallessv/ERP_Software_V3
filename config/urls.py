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
from core.views import proveedor_list, proveedor_crear, proveedor_editar, eliminar_proveedor
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
   
    
    

]

