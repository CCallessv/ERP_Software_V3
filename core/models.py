from django.db import models

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
class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Categoría")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    estado = models.BooleanField(default=True, verbose_name="Activo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre
###########################################################3

class Producto(models.Model):
    # La unidad maestra. Todo el stock se cuenta matemáticamente en esta unidad.
    UNIDADES_BASE = [
        ('und', 'Unidad (Und)'),
        ('lb', 'Libra (Lb)'),
        ('oz', 'Onza (Oz)'),
        ('kg', 'Kilogramo (Kg)'),
        ('lt', 'Litro (Lt)'),
        ('gal', 'Galón (Gal)'),
        ('mts', 'Metro (Mts)'),
    ]

    # Identificación
    codigo = models.CharField(max_length=50, unique=True, verbose_name="Código / SKU")
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    categoria = models.ForeignKey('Categoria', on_delete=models.PROTECT, related_name='productos', verbose_name="Categoría")
    
    # --- Inventario Base (Núcleo Matemático) ---
    unidad_medida_base = models.CharField(max_length=10, choices=UNIDADES_BASE, default='und', verbose_name="Unidad Base")
    ubicacion = models.CharField(max_length=50, blank=True, null=True, verbose_name="Ubicación en Bodega")
    
    stock = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Stock Actual")
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, verbose_name="Stock Mínimo")
    stock_maximo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=None, verbose_name="Stock Máximo")

    # --- Precios Base ---
    precio_costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Promedio (Unidad Base)")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio Venta (Unidad Base)")

    # --- Control ---
    es_vendible = models.BooleanField(default=True, verbose_name="¿Se vende al cliente?")
    es_comprable = models.BooleanField(default=True, verbose_name="¿Se compra a proveedores?")
    imagen = models.ImageField(upload_to='productos/', blank=True, null=True, verbose_name="Imagen")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Inventario"
        ordering = ['nombre']


class PresentacionProducto(models.Model):
    """
    Motor Multi-Unidad (UoM). 
    Ejemplo: Producto = Crema (Base: Libra). 
    Presentación 1 = "Botella", Factor = 1.5, Precio = $3.00
    Presentación 2 = "Media Libra", Factor = 0.5, Precio = $1.00
    """
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='presentaciones')
    nombre = models.CharField(max_length=100, verbose_name="Nombre de Presentación", help_text="Ej: Botella, Caja x50, Media Libra")
    codigo_barras = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name="Código de Barras")
    
    # El eslabón matemático: Cuánto descuenta del stock maestro
    factor_conversion = models.DecimalField(
        max_digits=10, decimal_places=4, 
        verbose_name="Equivalencia en Unidad Base",
        help_text="¿Cuántas unidades base contiene o consume esta presentación?"
    )
    
    # Te permite vender la botella más cara que si vendieras la libra suelta
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Específico")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} de {self.producto.nombre}"

    class Meta:
        verbose_name = "Presentación"
        verbose_name_plural = "Presentaciones"

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


