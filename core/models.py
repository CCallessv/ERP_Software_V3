from django.db import models

# 1. Tabla de Categorias (Ej: Electronica, Muebles, Servicios)
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True) 
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
# 2. Tabla de Clientes (Para ventas)

class Cliente(models.Model):
    # Identificación
    codigo = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Código Cliente") # Nuevo
    nombres = models.CharField(max_length=150, verbose_name="Nombre o Razón Social")
    documento = models.CharField(max_length=20, unique=True, verbose_name="DUI/NIT")
    nrc = models.CharField(max_length=20, blank=True, null=True, verbose_name="NRC")
    giro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Giro")
    # Contacto
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    estado = models.BooleanField(default=True, verbose_name="Estado (Activo)")
    # Datos Financieros 
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Límite de Crédito")
    plazo_credito = models.PositiveIntegerField(default=0, verbose_name="Plazo Crédito (Días)")
    
    # Auditoria
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombres} ({self.codigo})"

    def save(self, *args, **kwargs):
        # Si el código está vacio, generamos uno nuevo
        if not self.codigo:
            # Contamos cuantos clientes hay actualmente
            total_clientes = Cliente.objects.count()
            # El nuevo numero sera el total + 1
            nuevo_numero = total_clientes + 1
# Mientras YA EXISTA un cliente con ese codigo, seguimos sumando 1
            while Cliente.objects.filter(codigo=f"CLI-{nuevo_numero:04d}").exists():
                nuevo_numero += 1
            # Formateamos: "CLI-" seguido del numero con 4 digitos 
            self.codigo = f"CLI-{nuevo_numero:04d}"
        
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
#####################################################################################################
class Producto(models.Model):
    # Opciones
    TIPO_CHOICES = [
        ('materia_prima', ' Producto Padre (Materia Prima)'),
        ('subproducto', ' Subproducto (Derivado)'),
        ('producto', ' Producto Normal (Compra/Venta)'),
        ('servicio', ' Servicio (Sin Stock)'),
    ]
    
    UNIDAD_CHOICES = [
        ('unidad', 'Unidad (Und)'),
        ('libra', 'Libra (Lb)'),
        ('kg', 'Kilogramo (Kg)'),
        ('metro', 'Metro (Mts)'),
        ('litro', 'Litro (Lt)'),
    ]

    #  Identificacion
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código / SKU")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    
    #  AQUI CONECTAMOS CON TU MODELO DE ARRIBA
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoría")

    #  Clasificacion
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='producto', verbose_name="Tipo de Producto")
    
   
    padre = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subproductos', 
        verbose_name="Proviene de (Padre)"
    )

    # --- Inventario y Ubicación ---
    unidad_medida = models.CharField(max_length=20, choices=UNIDAD_CHOICES, default='unidad', verbose_name="Unidad")
    ubicacion = models.CharField(max_length=50, blank=True, null=True, verbose_name="Ubicación en Bodega")
    
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Stock Actual")
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, verbose_name="Stock Mínimo")
    stock_maximo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None, verbose_name="Stock Máximo")

    # --- Precios ---
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Promedio")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio de Venta")

    # --- Control ---
    es_vendible = models.BooleanField(default=True, verbose_name="¿Se vende en caja?")
    es_comprable = models.BooleanField(default=True, verbose_name="¿Se compra a proveedores?")
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True, verbose_name="Imagen")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Inventario"
        ordering = ['nombre']

class Proveedor(models.Model):
    TIPO_PERSONA_CHOICES = [
        ('natural', 'Persona Natural'),
        ('juridica', 'Persona Jurídica'),
    ]

    # Clasificación esencial para retenciones de IVA en El Salvador
    CLASIFICACION_CHOICES = [
        ('no_contribuyente', 'No Contribuyente'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('mediano', 'Mediano Contribuyente'),
        ('grande', 'Gran Contribuyente'),
    ]

    # --- Identificacion ---
    nombre_comercial = models.CharField(max_length=200, verbose_name="Nombre Comercial")
    razon_social = models.CharField(max_length=200, blank=True, null=True, verbose_name="Razón Social")
    nit = models.CharField(max_length=17, unique=True, verbose_name="NIT")
    nrc = models.CharField(max_length=10, blank=True, null=True, verbose_name="NRC (Registro de IVA)")
    tipo_persona = models.CharField(max_length=10, choices=TIPO_PERSONA_CHOICES, default='natural')
    
    # --- Clasificacion Fiscal ---
    clasificacion = models.CharField(max_length=20, choices=CLASIFICACION_CHOICES, default='pequeno')
    giro = models.CharField(max_length=200, blank=True, null=True, verbose_name="Giro o Actividad Económica")

    # --- Contacto ---
    contacto_nombre = models.CharField(max_length=150, blank=True, verbose_name="Persona de Contacto")
    telefono = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    direccion = models.TextField(blank=True)

    # --- Credito ---
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    dias_credito = models.PositiveIntegerField(default=0, help_text="Días de plazo para pagar facturas")

    # --- El "Comodin" para Generalizar ---
    # Requiere que uses Postgres o Django 3.0+ (JSONField)
    # Aquí puedes guardar cosas como: "Frecuencia de visita", "Día de pago", etc.
    extra_data = models.JSONField(default=dict, blank=True, verbose_name="Datos Adicionales")

    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre_comercial} ({self.nit})"

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"


