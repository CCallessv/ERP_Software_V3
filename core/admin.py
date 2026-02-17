from django.contrib import admin
from .models import Categoria, Producto,Cliente

# Configuración para que la tabla de productos se vea profesional
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'categoria', 'stock', 'precio_venta', 'tipo', 'activo')
    search_fields = ('nombre', 'codigo') 
    list_filter = ('categoria',)

# ¡Esta es la parte clave! Registrar las tablas para que aparezcan
admin.site.register(Cliente)
admin.site.register(Categoria)
admin.site.register(Producto, ProductoAdmin)
