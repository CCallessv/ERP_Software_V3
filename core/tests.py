from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Producto, Categoria
from .forms import ProductoForm # NUEVO IMPORT: Probaremos el formulario directo

#PrimerasPrueba
class ProductoTestCase(TestCase):
    def setUp(self):
        # 1. Crear un usuario administrador de prueba
        self.user = User.objects.create_superuser(
            username='admin_test', 
            email='admin@test.com', 
            password='password123'
        )
        self.client = Client()
        self.client.login(username='admin_test', password='password123')

        # 2. Crear datos base
        self.categoria = Categoria.objects.create(
            nombre="Carnes",
            descripcion="Categoría de carnes de prueba",
            estado=True
        )
        
        self.producto_con_stock = Producto.objects.create(
            nombre="Costilla BBQ",
            codigo="PROD-001",
            categoria=self.categoria,
            unidad_medida_base="lb",
            stock=10.00,
            stock_minimo=5.00,
            precio_costo=3.50,
            precio_venta=5.00,
            es_vendible=True,
            es_comprable=True,
            activo=True
        )
        
        self.producto_sin_stock = Producto.objects.create(
            nombre="Posta Negra",
            codigo="PROD-002",
            categoria=self.categoria,
            unidad_medida_base="lb",
            stock=0.00,
            stock_minimo=5.00,
            precio_costo=2.50,
            precio_venta=4.00,
            es_vendible=True,
            es_comprable=True,
            activo=True
        )

    # ========================================================
    # PRUEBAS UNITARIAS PURAS (Al Formulario Directamente)
    # ========================================================
    
    def test_crear_producto_exito(self):
        """
        Prueba 1: Verifica que el formulario valida correctamente datos nuevos.
        """
        datos = {
            'nombre': 'Pechuga de Pollo',
            'codigo': 'PROD-003',
            'categoria': self.categoria.pk,
            'unidad_medida_base': 'lb',
            'stock': 0.00,
            'stock_minimo': 5.00,
            'precio_costo': 2.00,
            'precio_venta': 3.50,
            'es_vendible': True,
            'es_comprable': True,
            'activo': True
        }
        form = ProductoForm(data=datos)
        self.assertTrue(form.is_valid(), f"El formulario falló con estos errores: {form.errors}")

    def test_editar_producto_mismo_nombre_exito(self):
        """
        Prueba 2: Verifica que editar sin cambiar el nombre pasa la validación anti-duplicados.
        """
        datos_edicion = {
            'nombre': 'Costilla BBQ', # Mismo nombre
            'codigo': 'PROD-001-MOD', # Diferente código
            'categoria': self.categoria.pk,
            'unidad_medida_base': 'lb',
            'stock': 10.00,
            'stock_minimo': 5.00,
            'precio_costo': 4.00,
            'precio_venta': 6.00,
            'es_vendible': True,
            'es_comprable': True,
            'activo': True
        }
        # Le pasamos la instancia para decirle a Django que es una edicion
        form = ProductoForm(data=datos_edicion, instance=self.producto_con_stock)
        self.assertTrue(form.is_valid(), f"El formulario falló con estos errores: {form.errors}")

    # ========================================================
    # PRUEBAS DE INTEGRACION (A las Vistas y Modelos)
    # ========================================================

    def test_validacion_nombre_duplicado(self):
        """
        Prueba 3: Verifica validación anti-duplicados vía vista (Prueba al encontrar error).
        """
        datos_duplicados = {
            'nombre': 'Costilla BBQ', # Nombre existente
            'codigo': 'PROD-004',
            'categoria': self.categoria.pk,
            'unidad_medida_base': 'lb',
            'stock': 0.00,
            'stock_minimo': 5.00,
            'precio_costo': 1.00,
            'precio_venta': 2.00,
            'es_vendible': True,
            'es_comprable': True,
            'activo': True
        }
        response = self.client.post(reverse('crear_producto'), datos_duplicados)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Producto.objects.filter(codigo='PROD-004').exists())

    def test_eliminar_producto_con_stock_falla(self):
        """
        Prueba 4: Verifica regla de negocio de inventario (Stock > 0).
        """
        response = self.client.post(reverse('eliminar_producto', args=[self.producto_con_stock.pk]))
        self.assertTrue(Producto.objects.filter(pk=self.producto_con_stock.pk).exists())

    def test_eliminar_producto_sin_stock_exito(self):
        """
        Prueba 5: Verifica eliminación exitosa (Stock == 0).
        """
        response = self.client.post(reverse('eliminar_producto', args=[self.producto_sin_stock.pk]))
        self.assertFalse(Producto.objects.filter(pk=self.producto_sin_stock.pk).exists())
        self.assertEqual(response.status_code, 204)