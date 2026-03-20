from django.db import models
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
import uuid
from decimal import Decimal
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum

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
#############################################################################3

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

##########################################################
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

#######################################################################3
class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        # Entradas (Suman)
        ('entrada_compra', 'Entrada por Compra'),
        ('ajuste_entrada', 'Ajuste de Entrada (Positivo)'),
        # Salidas (Restan)
        ('salida_venta', 'Salida por Venta'),
        ('ajuste_salida', 'Ajuste de Salida (Merma/Daño)'),
    ]

    producto = models.ForeignKey('Producto', on_delete=models.PROTECT, related_name='movimientos')
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO, verbose_name="Tipo de Movimiento")
    
    # --- Matemáticas del Movimiento ---
    # Siempre se registra en la Unidad Base (ej. Libras, no Botellas)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Cantidad Movida")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Unitario (Histórico)")
    
    # --- El Seguro contra Colapsos (Snapshot) ---
    saldo_cantidad = models.DecimalField(
        max_digits=10, decimal_places=2, 
        blank=True, null=True,
        verbose_name="Stock Resultante",
        help_text="Fotografía del stock exacto DESPUÉS de este movimiento"
    )
    
    # --- Auditoría ---
    referencia = models.CharField(max_length=100, blank=True, null=True, verbose_name="Documento Respaldo", help_text="Ej: Factura #1234, Doc Ajuste #001")
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name="Registrado por")
    notas = models.TextField(blank=True, null=True, verbose_name="Justificación")

    class Meta:
        verbose_name = "Movimiento de Kardex"
        verbose_name_plural = "Kardex de Inventario"
        ordering = ['-fecha'] # Siempre muestra el más reciente primero

    def __str__(self):
        return f"{self.producto.codigo} | {self.get_tipo_display()} | {self.cantidad}"        

    def save(self, *args, **kwargs):
        # REGLA ERP: La matemática solo se ejecuta cuando el movimiento es NUEVO.
        # Los movimientos históricos son inmutables.
        if not self.pk:
            # TRANSACCIÓN ATÓMICA: Si algo falla aquí, la base de datos revierte todo
            with transaction.atomic():
                # select_for_update() bloquea la fila del producto. 
                # Si dos cajeros venden al mismo milisegundo, uno espera al otro.
                producto = Producto.objects.select_for_update().get(pk=self.producto.pk)

                if self.tipo in ['entrada_compra', 'ajuste_entrada']:
                    # 1. Calcular el Costo Promedio Ponderado
                    if self.cantidad > 0:
                        valor_inventario_actual = producto.stock * producto.precio_costo
                        valor_nuevo_ingreso = self.cantidad * self.costo_unitario
                        nuevo_stock = producto.stock + self.cantidad
                        
                        # Evitar la división por cero matemática
                        if nuevo_stock > 0:
                            producto.precio_costo = (valor_inventario_actual + valor_nuevo_ingreso) / nuevo_stock

                    # 2. Sumar el stock
                    producto.stock += self.cantidad

                elif self.tipo in ['salida_venta', 'ajuste_salida']:
                    # Validar fraude o error de digitación
                    if producto.stock < self.cantidad:
                        raise ValueError(f"Error Crítico: Intento de dejar el stock en negativo para {producto.nombre}.")
                    
                    # 2. Restar el stock
                    producto.stock -= self.cantidad

                # 3. Tomar la fotografía financiera (Saldo)
                self.saldo_cantidad = producto.stock

                # 4. Guardar el producto modificado
                producto.save()

        # 5. Finalmente, guardar este movimiento en el historial
        super().save(*args, **kwargs)
#########################################################################
class Compra(models.Model):
    ESTADO_COMPRA = [
        ('borrador', 'Borrador (No afecta stock)'),
        ('completada', 'Completada (Stock actualizado)'),
        ('anulada', 'Anulada (Stock revertido)'),
    ]
    
    TIPO_COMPROBANTE = [
        ('ccf', 'Comprobante de Crédito Fiscal (CCF)'),
        ('factura', 'Factura de Consumidor Final'),
        ('recibo', 'Recibo / Otro'),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='compras')
    fecha_compra = models.DateField(default=timezone.now, verbose_name="Fecha de Compra")
    tipo_comprobante = models.CharField(max_length=20, choices=TIPO_COMPROBANTE, default='ccf')
    numero_comprobante = models.CharField(max_length=50, verbose_name="Número de Documento")
    
    estado = models.CharField(max_length=20, choices=ESTADO_COMPRA, default='borrador')
    
    # Totales del documento
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    impuestos = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_compra', '-id']

    def __str__(self):
        return f"Compra {self.numero_comprobante} - {self.proveedor.nombre_empresa}"

##############################################################################
class DetalleCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('Producto', on_delete=models.PROTECT)
    
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Unitario")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        # REGLA: El subtotal lo calcula la máquina, no el humano, para evitar fraude.
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"

###################################################
class Venta(models.Model):
    ESTADOS = (
        ('borrador', 'Borrador'),
        ('completada', 'Completada'),
        ('anulada', 'Anulada'),
    )
    
    TIPO_DOC = (
        ('FCF', 'Factura de Consumidor Final'),
        ('CCF', 'Comprobante de Crédito Fiscal'),
    )
    
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT)
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOC, default='FCF')

    # CAMPOS ESTRICTOS PARA FACTURACIÓN ELECTRÓNICA (DTE)
    codigo_generacion = models.UUIDField(default=uuid.uuid4, editable=False, null=True)
    numero_control = models.CharField(max_length=40, unique=True, blank=True, null=True)
    sello_recepcion = models.CharField(max_length=45, blank=True, null=True)

    CONDICION_PAGO = (
        ('contado', 'Contado'),
        ('credito', 'Crédito'),
    )
    METODO_PAGO = (
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia Bancaria'),
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('cheque', 'Cheque'),
        ('otro', 'Otro'),
    )

    condicion_pago = models.CharField(max_length=10, choices=CONDICION_PAGO, default='contado')
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO, default='efectivo')
    dias_credito = models.PositiveIntegerField(default=0, help_text="Aplica solo si la condición es Crédito")
    
    # METADATOS Y OBSERVACIONES
    numero_factura = models.CharField(max_length=20, unique=True, blank=True, null=True)
    fecha_hora_emision = models.DateTimeField(auto_now_add=True) # Modificado para capturar hora exacta
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    observaciones = models.TextField(blank=True, null=True) # Agregado para cumplir con el esquema
    
    # TOTALES GRANULARES
    sumatoria_gravadas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sumatoria_exentas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sumatoria_no_sujetas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    descuento_global = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # IMPUESTOS
    iva = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    iva_percibido = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    iva_retenido = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    total_pagar = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Venta {self.codigo_generacion} - {self.cliente.nombres}"


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, related_name='detalles', on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    
    # CANTIDADES BASE
    # Nota: Uso DecimalField en cantidad porque en alimentos a veces vendes "1.5 libras"
    cantidad = models.DecimalField(max_digits=10, decimal_places=2) 
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2) # Sin IVA si es CCF, Con IVA si es FCF
    
    # MODIFICADORES DE LÍNEA
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    otros = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # CLASIFICACIÓN TRIBUTARIA (Reemplaza las 3 columnas del PDF)
    TIPO_AFECTACION = (
        ('gravada', 'Gravada'),
        ('exenta', 'Exenta'),
        ('no_sujeta', 'No Sujeta'),
    )
    tipo_afectacion = models.CharField(max_length=15, choices=TIPO_AFECTACION, default='gravada')
    
    # EL RESULTADO MATEMÁTICO FINAL DE LA LÍNEA
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, editable=False)

    def save(self, *args, **kwargs):
        # La fórmula estricta según Hacienda: (Cantidad * Precio Unitario) - Descuento + Otros
        base = (Decimal(str(self.cantidad)) * Decimal(str(self.precio_unitario)))
        self.subtotal = base - Decimal(str(self.descuento)) + Decimal(str(self.otros))
        super().save(*args, **kwargs)       

# INTERCEPTOR TRIBUTARIO PARA EL SALVADOR
@receiver(post_save, sender=DetalleVenta)
@receiver(post_delete, sender=DetalleVenta)
def actualizar_totales_venta(sender, instance, **kwargs):
    venta = instance.venta
    
    # 1. Agrupamos los subtotales de las líneas según su afectación tributaria
    totales = venta.detalles.aggregate(
        gravadas=Sum('subtotal', filter=models.Q(tipo_afectacion='gravada')),
        exentas=Sum('subtotal', filter=models.Q(tipo_afectacion='exenta')),
        no_sujetas=Sum('subtotal', filter=models.Q(tipo_afectacion='no_sujeta'))
    )

    # 2. Asignamos ceros si la tabla de detalles está vacía o el filtro no encontró nada
    venta.sumatoria_gravadas = totales['gravadas'] or Decimal('0.00')
    venta.sumatoria_exentas = totales['exentas'] or Decimal('0.00')
    venta.sumatoria_no_sujetas = totales['no_sujetas'] or Decimal('0.00')

    # 3. Matemática de Impuestos (El IVA del 13% en SV solo aplica a las gravadas)
    # Si la venta es de Consumidor Final (FCF), el IVA ya va incluido en el precio, no se suma aparte.
    # Si es Crédito Fiscal (CCF), el IVA se calcula extra sobre el subtotal gravado.
    if venta.tipo_documento == 'CCF':
        venta.iva = (venta.sumatoria_gravadas * Decimal('0.13')).quantize(Decimal('0.01'))
        venta.total_pagar = venta.sumatoria_gravadas + venta.sumatoria_exentas + venta.sumatoria_no_sujetas + venta.iva
    else: # FCF
        venta.iva = Decimal('0.00') # Para FCF en SV el IVA va oculto en el precio
        venta.total_pagar = venta.sumatoria_gravadas + venta.sumatoria_exentas + venta.sumatoria_no_sujetas

    # 4. Sellamos la cabecera en la base de datos
    venta.save()        