from django import template

register = template.Library()

@register.filter(name='tiene_rol')
def tiene_rol(user, nombre_rol):
    """
    Permite usar un condicional en el HTML: {% if request.user|tiene_rol:"Administrador" %}
    """
    if user.is_superuser:
        return True
    return user.groups.filter(name=nombre_rol).exists()