from django import forms
import re
from .models import (
    Cliente, Producto, Proveedor, Categoria, 
    PresentacionProducto, Compra, DetalleCompra, AjusteInventario
)

# === FORMULARIO DE CLIENTES (B2B) ===
class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nombres', 'documento', 'nrc', 'giro', 'email', 'telefono', 'direccion', 'limite_credito', 'plazo_credito', 'estado']
        
        widgets = {
            'nombres': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Juan Pérez S.A. de C.V.'}),
            'documento': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DUI o NIT'}),
            'nrc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registro'}),
            'giro': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Venta de repuestos'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'limite_credito': forms.NumberInput(attrs={'class': 'form-control'}),
            'plazo_credito': forms.NumberInput(attrs={'class': 'form-control'}),
            'estado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

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

# === FORMULARIO DE PROVEEDORES ===
class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = [
            'nombre_comercial', 'razon_social', 'nit', 'nrc', 
            'tipo_persona', 'clasificacion', 'giro', 
            'contacto_nombre', 'telefono', 'email', 
            'direccion', 'limite_credito', 'dias_credito'
        ]
        widgets = {
            'nombre_comercial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Proveedor Carnes'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control'}),
            'nit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0000-000000-000-0'}),
            'nrc': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '000000-0'}),
            'tipo_persona': forms.Select(attrs={'class': 'form-select'}),
            'clasificacion': forms.Select(attrs={'class': 'form-select'}),
            'giro': forms.TextInput(attrs={'class': 'form-control'}),
            'contacto_nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'limite_credito': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'dias_credito': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean_nit(self):
        nit = self.cleaned_data.get('nit')
        regex_nit = r'^\d{4}-\d{6}-\d{3}-\d{1}$'
        if nit and not re.match(regex_nit, nit):
            raise forms.ValidationError("El NIT debe seguir el formato legal de El Salvador.")
        return nit

    def clean_nrc(self):
        nrc = self.cleaned_data.get('nrc')
        if nrc and '-' not in nrc:
             raise forms.ValidationError("El NRC debe incluir el guion verificador.")
        return nrc    

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