from django.db import migrations

def crear_cliente_mostrador(apps, schema_editor):
    # Obtenemos el modelo desde el registro de apps (seguro para migraciones)
    Cliente = apps.get_model('core', 'Cliente')
    
    # Creamos el registro solo si no existe
    Cliente.objects.get_or_create(
        documento="0000-000000-000-0",
        defaults={
            'nombres': 'CLIENTE MOSTRADOR',
            'giro': 'CONSUMIDOR FINAL',
            'estado': True
        }
    )

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_compra_condicion_pago_compra_dias_credito_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_cliente_mostrador),
    ]