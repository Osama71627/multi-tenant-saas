from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("suppliers", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="supplier",
            old_name="provider_key",
            new_name="provider",
        ),
    ]
