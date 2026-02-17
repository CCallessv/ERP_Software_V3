from django import forms
import re
from .models import Cliente, Producto, Proveedor
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
        fields = ['codigo', 'nombre', 'categoria', 'tipo', 'unidad_medida', 'padre', 'stock', 'stock_minimo', 'stock_maximo', 'precio_costo', 'precio_venta', 'es_vendible', 'es_comprable', 'ubicacion', 'activo', 'imagen']
        
        widgets = {
            'tipo': forms.HiddenInput(), 
            'codigo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: PROD-001'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select'}),
            'padre': forms.Select(attrs={'class': 'form-select'}),
            'stock': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '5'}),
            'stock_maximo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '100'}),
            'precio_costo': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'precio_venta': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: A-01-01'}),
            'es_vendible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'es_comprable': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtramos para que en "Padre" solo salgan materias primas
        self.fields['padre'].queryset = Producto.objects.filter(tipo='materia_prima')        

# forms.py
from django import forms
from .models import Proveedor
import re

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