from django import forms
import re
from .models import Cliente, Producto, Proveedor, Categoria, PresentacionProducto, Compra,DetalleCompra,AjusteInventario
from .models import Caja, SesionCaja
#Django necesita saber cómo validar los datos antes de guardarlos entonces Vamos a crear un archivo para "traducir" el modelo a HTML.
class ClienteForm(forms.ModelForm): # ClienteForm es el nombre del formulario que vamos a usar en la vista
    class Meta: # Meta es un diccionario que contiene la configuración del formulario
        model = Cliente #modelo cliente
        fields = ['nombres', 'documento', 'nrc', 'giro', 'email', 'telefono', 'direccion', 'limite_credito', 'plazo_credito', 'estado']
        
        # Esto hace que los inputs se vean bonitos con Tabler (Bootstrap)
        widgets = { # widgets es un diccionario que contiene los widgets que vamos a usar en el formulario
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
        
        # Inyectar clases de Bootstrap a todos los campos
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
                
        # BLOQUEO EMPRESARIAL: El stock inicial no se puede manipular
        self.fields['stock'].widget.attrs['readonly'] = True
        self.fields['stock'].initial = 0.00
        self.fields['stock'].help_text = "Bloqueado. El stock se gestiona vía compras o ajustes."  


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
            # Aplicamos clases de Tabler para que se vea profesional
            'nombre_comercial': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Carnicería La Bendición'}),
            'razon_social': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Juan Pérez S.A. de C.V.'}),
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

    # --- Validaciones de Seguridad (Blindaje de Datos) ---

    def clean_nit(self):
        nit = self.cleaned_data.get('nit')
        # Formato: 0614-200190-101-5 (4-6-3-1 dígitos)
        regex_nit = r'^\d{4}-\d{6}-\d{3}-\d{1}$'
        if nit and not re.match(regex_nit, nit):
            raise forms.ValidationError("El NIT debe seguir el formato legal: 0000-000000-000-0")
        return nit

    def clean_nrc(self):
        nrc = self.cleaned_data.get('nrc')
        # El NRC suele ser de 6 a 8 dígitos seguidos de un guion y un dígito
        if nrc and '-' not in nrc:
             raise forms.ValidationError("El NRC (Registro de IVA) debe incluir el guion verificador.")
        return nrc    

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nombre', 'descripcion', 'estado']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Ej. Lácteos, Electrónica...'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Breve descripción de la categoría (Opcional)'
            }),
            'estado': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

class PresentacionForm(forms.ModelForm):
    class Meta:
        model = PresentacionProducto
        fields = ['nombre', 'codigo_barras', 'factor_conversion', 'precio_venta']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            
        # Forzar que el factor de conversión no pueda ser menor a 0.0001
        self.fields['factor_conversion'].widget.attrs.update({
            'min': '0.0001', 
            'step': '0.0001'
        })
        self.fields['precio_venta'].widget.attrs.update({
            'min': '0.00', 
            'step': '0.01'
        })

class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ['proveedor', 'fecha_compra', 'tipo_comprobante', 'numero_comprobante']
        widgets = {
            'fecha_compra': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'proveedor': forms.Select(attrs={'class': 'form-select'}),
            'tipo_comprobante': forms.Select(attrs={'class': 'form-select'}),
            'numero_comprobante': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 0001-00000456'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtramos para que solo salgan proveedores activos
        from .models import Proveedor
        self.fields['proveedor'].queryset = Proveedor.objects.filter(activo=True)        


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
        # Solo mostrar productos que estén activos en el inventario
        self.fields['producto'].queryset = Producto.objects.filter(activo=True)        


class ProductoConStockChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        # Aquí definimos exactamente cómo se lee cada opción en el dropdown
        return f"{obj.nombre} ({obj.codigo}) — Stock actual: {obj.stock}"

class AjusteInventarioForm(forms.ModelForm):
    # Forzamos al formulario a usar nuestro campo personalizado
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
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Producto dañado, devolución, etc.'}),
        }

class AbrirSesionCajaForm(forms.ModelForm):
    class Meta:
        model = SesionCaja
        fields = ['caja', 'saldo_inicial']
        widgets = {
            'caja': forms.Select(attrs={'class': 'form-select'}),
            'saldo_inicial': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Ej. 50.00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Solo mostrar cajas que estén activas
        self.fields['caja'].queryset = Caja.objects.filter(activa=True)        

class CerrarSesionCajaForm(forms.ModelForm):
    class Meta:
        model = SesionCaja
        fields = ['saldo_fisico']
        widgets = {
            'saldo_fisico': forms.NumberInput(attrs={'class': 'form-control fs-2', 'step': '0.01', 'placeholder': 'Ej. 85.00'}),
        }
        labels = {
            'saldo_fisico': 'Efectivo total en gaveta (Billetes y monedas)'
        }