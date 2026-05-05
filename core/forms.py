from django import forms
import re
from .models import (
    Cliente, Producto, Proveedor, Categoria, Compra, DetalleCompra, AjusteInventario, SolicitudAcceso,
)
from decimal import Decimal
from django.core.exceptions import ValidationError

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombres', 'documento', 'nrc', 'giro', 'email', 'telefono', 'direccion', 'limite_credito', 'plazo_credito', 'estado']
        
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan Pérez S.A. de C.V.'}),
            'documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DUI (00000000-0) o NIT'}),
            'nrc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123456-7'}),
            'giro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Venta de repuestos'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 2222-3333'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'limite_credito': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'plazo_credito': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_documento(self):
        doc = self.cleaned_data.get('documento')
        if doc:
            # 1. SANITIZAR: Quitamos TODO lo que no sea número
            doc_limpio = re.sub(r'\D', '', doc)
            
            # 2. EVALUAR Y FORMATEAR
            # Si tiene 9 números, es un DUI
            if len(doc_limpio) == 9:
                doc_formateado = f"{doc_limpio[:8]}-{doc_limpio[8]}"
            # Si tiene 14 números, es un NIT
            elif len(doc_limpio) == 14:
                doc_formateado = f"{doc_limpio[:4]}-{doc_limpio[4:10]}-{doc_limpio[10:13]}-{doc_limpio[13]}"
            else:
                raise forms.ValidationError("El documento debe tener 9 números (DUI) o 14 números (NIT).")
            
            # 3. VERIFICAR DUPLICADOS
            if Cliente.objects.filter(documento=doc_formateado).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Crítico: Este documento ya está registrado en otro cliente.")
            
            # Retornamos el dato ya formateado para la base de datos
            return doc_formateado
        return doc

    def clean_nrc(self):
        nrc = self.cleaned_data.get('nrc')
        if nrc:
            # 1. SANITIZAR: Quitamos todo lo que no sea número
            nrc_limpio = re.sub(r'\D', '', nrc)
            
            # 2. EVALUAR: El NRC suele tener entre 3 y 8 números en total
            if len(nrc_limpio) < 3 or len(nrc_limpio) > 8:
                raise forms.ValidationError("El NRC debe tener entre 3 y 8 números en total.")
            
            # 3. FORMATEAR: Asumimos que el último dígito es el verificador
            nrc_formateado = f"{nrc_limpio[:-1]}-{nrc_limpio[-1]}"
            
            # 4. VERIFICAR DUPLICADOS
            if Cliente.objects.filter(nrc=nrc_formateado).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Crítico: Este NRC ya está registrado.")
                
            return nrc_formateado
        return nrc

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if telefono:
            # 1. SANITIZAR Y EVALUAR (Tu lógica original aquí era buena)
            numeros = re.sub(r'\D', '', telefono) # Limpia cualquier carácter que no sea dígito
            
            if len(numeros) != 8:
                raise forms.ValidationError("El teléfono debe tener exactamente 8 dígitos.")
            
            # 2. FORMATEAR
            return f"{numeros[:4]}-{numeros[4:]}"
        return telefono

    def clean_limite_credito(self):
        limite = self.cleaned_data.get('limite_credito')
        if limite is not None:
            if limite < 0:
                raise forms.ValidationError("El límite de crédito no puede ser negativo.")
            # Redondeamos a dos decimales para curarnos en salud
            return round(limite, 2) 
        return limite

    def clean_plazo_credito(self):
        plazo = self.cleaned_data.get('plazo_credito')
        if plazo is not None and plazo < 0:
            raise forms.ValidationError("Los días de crédito no pueden ser negativos.")
        return plazo
# === FORMULARIO DE PRODUCTOS ===

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            'nombre', 'categoria', 'unidad_medida_base', 
            'ubicacion', 'stock', 'stock_minimo', 'stock_maximo',
            'precio_costo', 'precio_venta', 'es_vendible', 
            'es_comprable', 'imagen', 'activo'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
                
        # BLOQUEO VISUAL: El stock inicial no se manipula aquí
        self.fields['stock'].widget.attrs['readonly'] = True
        self.fields['stock'].initial = 0.00
        self.fields['stock'].help_text = "El stock se gestiona vía compras o ajustes."
        
        self.fields['precio_costo'].widget.attrs['min'] = 0
        self.fields['precio_venta'].widget.attrs['min'] = 0

    # 1. ANTIDUPLICADOS Y LIMPIEZA DE TEXTO
    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '').strip()
        qs = Producto.objects.filter(nombre__iexact=nombre)
        
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
            
        if qs.exists():
            raise ValidationError("Ya existe un producto registrado con este nombre exacto.")
            
        return nombre

    # 2. BLINDAJE CONTRA MANIPULACIÓN DEL STOCK
    def clean_stock(self):
        if not self.instance.pk:
            return Decimal('0.00')
        return self.instance.stock

    # 3. SEGURIDAD DE ARCHIVOS (Peso máximo de 2MB)
    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen:
            peso_mb = imagen.size / (1024 * 1024)
            if peso_mb > 2:
                raise ValidationError(f"La imagen pesa {peso_mb:.1f}MB. El límite máximo es 2MB.")
        return imagen

    # 4. REGLAS DE NEGOCIO ESTRICTAS
    def clean(self):
        cleaned_data = super().clean()
        
        precio_costo = cleaned_data.get('precio_costo')
        precio_venta = cleaned_data.get('precio_venta')
        es_vendible = cleaned_data.get('es_vendible')
        es_comprable = cleaned_data.get('es_comprable')
        stock_minimo = cleaned_data.get('stock_minimo')
        stock_maximo = cleaned_data.get('stock_maximo')
        
        # Reglas de Compras
        if es_comprable:
            if precio_costo is None or precio_costo <= 0:
                self.add_error('precio_costo', "Un producto comprable requiere un costo mayor a $0.00.")
                
        # Reglas de Ventas
        if es_vendible:
            if precio_venta is None or precio_venta <= 0:
                self.add_error('precio_venta', "Un producto vendible requiere un precio mayor a $0.00.")
            if precio_costo and precio_venta and precio_venta <= precio_costo:
                self.add_error('precio_venta', "El precio de venta debe ser estrictamente mayor al costo.")

        # Lógica de Inventario
        if stock_minimo is not None and stock_minimo < 0:
            self.add_error('stock_minimo', "El mínimo no puede ser negativo.")
        if stock_minimo is not None and stock_maximo is not None:
            if stock_maximo <= stock_minimo:
                self.add_error('stock_maximo', "El stock máximo debe ser mayor al mínimo.")

        return cleaned_data


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = [
            'nombre_comercial', 'razon_social', 'nit', 'nrc', 
            'tipo_persona', 'clasificacion', 'giro', 
            'contacto_nombre', 'telefono', 'email', 
            'direccion', 'limite_credito', 'dias_credito', 'activo' # Asegúrate de tener 'estado' si usaremos Soft Delete
        ]
        widgets = {
            'nombre_comercial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Proveedor Carnes'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'nit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0000-000000-000-0', 'id': 'id_nit_proveedor'}),
            'nrc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000000-0', 'id': 'id_nrc_proveedor'}),
            'tipo_persona': forms.Select(attrs={'class': 'form-select'}),
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'giro': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 2222-3333', 'id': 'id_telefono_proveedor'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'limite_credito': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'dias_credito': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nit(self):
        nit = self.cleaned_data.get('nit')
        if nit:
            # 1. SANITIZAR: Quitamos todo lo que no sea número
            nit_limpio = re.sub(r'\D', '', nit)
            
            # 2. EVALUAR Y FORMATEAR
            if len(nit_limpio) != 14:
                raise forms.ValidationError("El NIT debe tener exactamente 14 números.")
            
            nit_formateado = f"{nit_limpio[:4]}-{nit_limpio[4:10]}-{nit_limpio[10:13]}-{nit_limpio[13]}"
            
            # 3. VERIFICAR DUPLICADOS
            if Proveedor.objects.filter(nit=nit_formateado).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Crítico: Este NIT ya está registrado con otro proveedor.")
                
        return nit_formateado

    def clean_nrc(self):
        nrc = self.cleaned_data.get('nrc')
        if nrc:
            nrc_limpio = re.sub(r'\D', '', nrc)
            if len(nrc_limpio) < 3 or len(nrc_limpio) > 8:
                raise forms.ValidationError("El NRC debe tener entre 3 y 8 números en total.")
            
            nrc_formateado = f"{nrc_limpio[:-1]}-{nrc_limpio[-1]}"
            
            if Proveedor.objects.filter(nrc=nrc_formateado).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Crítico: Este NRC ya está registrado.")
                
            return nrc_formateado
        return nrc

    def clean_telefono(self):
        telefono = self.cleaned_data.get('telefono')
        if telefono:
            numeros = re.sub(r'\D', '', telefono)
            if len(numeros) != 8:
                raise forms.ValidationError("El teléfono debe tener exactamente 8 dígitos.")
            return f"{numeros[:4]}-{numeros[4:]}"
        return telefono

    def clean_limite_credito(self):
        limite = self.cleaned_data.get('limite_credito')
        if limite is not None:
            if limite < 0:
                raise forms.ValidationError("El límite de crédito no puede ser negativo.")
            # Redondeo automático en lugar de tirar error por muchos decimales
            return round(limite, 2)
        return limite

    def clean_dias_credito(self):
        dias = self.cleaned_data.get('dias_credito')
        if dias is not None and dias < 0:
            raise forms.ValidationError("Los días de crédito no pueden ser negativos.")
        return dias


#Categoria Formulario

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Abarrotes'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_nombre(self):
        nombre = self.cleaned_data.get('nombre', '')
        nombre_limpio = nombre.strip().upper() 
        
        # 1. Blindaje contra nombres basura (Longitud)
        if len(nombre_limpio) < 3:
            raise forms.ValidationError("El nombre es demasiado corto. Usa al menos 3 caracteres.")
            
        # 2. Blindaje contra solo numeros o simbolos (Debe tener letras)
        if not re.search(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ]', nombre_limpio):
            raise forms.ValidationError("El nombre debe contener letras, no solo números o símbolos.")
            
        # 3. Blindaje contra duplicados exactos
        query = Categoria.objects.filter(nombre__iexact=nombre_limpio)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
            
        if query.exists():
            raise forms.ValidationError("Ya existe una categoría registrada con este nombre.")
            
        return nombre_limpio

    def clean_descripcion(self):
        descripcion = self.cleaned_data.get('descripcion', '')
        if descripcion:
            descripcion = descripcion.strip()
            # 4. Blindaje contra descripciones excesivas
            if len(descripcion) > 255:
                raise forms.ValidationError("La descripción es demasiado larga (máximo 255 caracteres).")
        return descripcion

    def clean_estado(self):
        estado = self.cleaned_data.get('estado')
        
        # 5. Blindaje : Proteger dependencias al inactivar
        if self.instance.pk and not estado:
            
            if self.instance.productos.exists():
                cantidad = self.instance.productos.count()
                raise forms.ValidationError(f"No puedes inactivar esta categoría porque tiene {cantidad} producto(s) asociado(s). Reasigna los productos primero.")
                
        return estado


# === FORMULARIO DE COMPRAS ===
class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['proveedor', 'fecha_compra', 'tipo_comprobante', 'numero_comprobante']
        widgets = {
            'fecha_compra': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'tipo_comprobante': forms.Select(attrs={'class': 'form-select'}),
            'numero_comprobante': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)    

        # 1. Validación de la máquina del tiempo
    def clean_fecha_compra(self):
        fecha = self.cleaned_data.get('fecha_compra')
        if fecha and fecha > date.today():
            raise ValidationError("Auditoría fallida: No puedes registrar una compra con fecha en el futuro.")
        return fecha

    # 2. Validación cruzada (Proveedor + Factura + Año Fiscal)
    def clean(self):
        cleaned_data = super().clean()
        proveedor = cleaned_data.get('proveedor')
        numero_comprobante = cleaned_data.get('numero_comprobante')
        fecha_compra = cleaned_data.get('fecha_compra')

        if proveedor and numero_comprobante and fecha_compra:
            # Extraemos el año para aislar la validación por ejercicio fiscal
            año_fiscal = fecha_compra.year
            
            compra_duplicada = Compra.objects.filter(
                proveedor=proveedor, 
                numero_comprobante__iexact=numero_comprobante,
                fecha_compra__year=año_fiscal
            ).exclude(pk=self.instance.pk)
            
            if compra_duplicada.exists():
                self.add_error(
                    'numero_comprobante', 
                    f"Alerta de duplicidad: El proveedor {proveedor.nombre} ya tiene la factura {numero_comprobante} registrada en el ejercicio {año_fiscal}."
                )

        return cleaned_data  

# === FORMULARIO DE DETALLE DE COMPRA ===
class DetalleCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleCompra
        fields = ['producto', 'cantidad', 'precio_unitario']
        widgets = {
            'producto': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['producto'].queryset = Producto.objects.filter(activo=True)  


    # 1. Validacion estricta de la cantidad
    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise ValidationError("Intento de fraude o error: La cantidad debe ser estrictamente mayor a cero.")
        return cantidad

    # 2. Validacion estricta del precio
    def clean_precio_unitario(self):
        precio = self.cleaned_data.get('precio_unitario')
        if precio is not None and precio < 0:
            raise ValidationError("Error contable: El precio unitario no puede ser negativo.")
        return precio          

# === FORMULARIO DE AJUSTES DE INVENTARIO ===
class ProductoConStockChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.nombre} — Stock actual: {obj.stock}"

class AjusteInventarioForm(forms.ModelForm):
    producto = ProductoConStockChoiceField(
        queryset=Producto.objects.filter(activo=True), 
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = AjusteInventario
        fields = ['producto', 'tipo', 'cantidad', 'motivo']
        widgets = {
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Justificación del ajuste'}),
        }

class RegistrarPagoForm(forms.Form):
    METODO_PAGO_CHOICES = [
        ('transferencia', 'Transferencia Bancaria'),
        ('tarjeta', 'Tarjeta de Crédito/Débito'),
        ('cheque', 'Cheque'),
        ('efectivo', 'Efectivo (Administrativo)'),
    ]
    metodo_pago = forms.ChoiceField(choices=METODO_PAGO_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    comprobante_pago = forms.CharField(
        max_length=50, 
        required=False, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Num. Transferencia o Cheque'})
    )

class SolicitudAccesoForm(forms.ModelForm):
    class Meta:
        model = SolicitudAcceso
        fields = ['nombres', 'correo', 'motivo']
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan Pérez'}),
            'correo': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'tucorreo@empresa.com'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Justifica tu solicitud de acceso...'}),
        }    