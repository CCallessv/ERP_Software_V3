from django import forms
import re
from .models import (
    Cliente, Producto, Proveedor, Categoria, 
    PresentacionProducto, Compra, DetalleCompra, AjusteInventario
)

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
                
        # BLOQUEO: El stock inicial no se puede manipular manualmente
        self.fields['stock'].widget.attrs['readonly'] = True
        self.fields['stock'].initial = 0.00
        self.fields['stock'].help_text = "El stock se gestiona vía compras o ajustes."  

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


# === FORMULARIO DE CATEGORÍAS ===
class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

# === FORMULARIO DE PRESENTACIONES ===
class PresentacionForm(forms.ModelForm):
    class Meta:
        model = PresentacionProducto
        fields = ['nombre', 'codigo_barras', 'factor_conversion', 'precio_venta']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        self.fields['factor_conversion'].widget.attrs.update({'min': '0.0001', 'step': '0.0001'})
        self.fields['precio_venta'].widget.attrs.update({'min': '0.00', 'step': '0.01'})

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