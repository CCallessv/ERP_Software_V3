from django.core.exceptions import PermissionDenied

def rol_requerido(*nombres_roles):
    """
    Verifica si el usuario pertenece a alguno de los roles permitidos.
    Si es superusuario, siempre pasa. Si no tiene el rol, lanza error 403.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # El superusuario (tu) tiene acceso a todo por defecto
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Verificamos si el usuario pertenece a alguno de los roles exigidos
            if request.user.groups.filter(name__in=nombres_roles).exists():
                return view_func(request, *args, **kwargs)
            
            # Si llega aquí, es un intento de intrusión
            raise PermissionDenied("Acceso denegado: Tu rol no tiene permisos para realizar esta acción.")
        return _wrapped_view
    return decorator