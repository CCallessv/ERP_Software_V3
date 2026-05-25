from django.db import migrations

def crear_cliente_mostrador(apps, schema_editor):
    Cliente = apps.get_model('core', 'Cliente')
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
        ('core', '000X_tu_migracion_anterior'), # Asegúrate que este nombre coincida con tu migración anterior
    ]

    operations = [
        migrations.RunPython(crear_cliente_mostrador),
    ]