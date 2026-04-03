from django.contrib import admin
# IMPORTANTE: Asegúrate de importar el nuevo modelo en la parte superior
from .models import Cliente, Categoria, Producto, PresentacionProducto, MovimientoInventario, Venta, DetalleVenta,Compra

# Esto incrusta las conversiones dentro del formulario del Producto
class PresentacionProductoInline(admin.TabularInline):
    model = PresentacionProducto
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    # Actualizado estrictamente con los campos que sobrevivieron a la purga
    list_display = ('codigo', 'nombre', 'categoria', 'stock', 'unidad_medida_base', 'precio_costo', 'activo')
    list_filter = ('categoria', 'activo', 'es_vendible', 'es_comprable')
    search_fields = ('codigo', 'nombre')
    inlines = [PresentacionProductoInline]


admin.site.register(MovimientoInventario)    
admin.site.register(Venta)
admin.site.register(Compra)
admin.site.register(Cliente)
admin.site.register(Categoria)