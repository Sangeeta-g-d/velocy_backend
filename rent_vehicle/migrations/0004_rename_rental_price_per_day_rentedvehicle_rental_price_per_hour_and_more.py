# Generated by Django 5.2.1 on 2025-06-10 06:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rent_vehicle', '0003_rentedvehiclerating'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rentedvehicle',
            old_name='rental_price_per_day',
            new_name='rental_price_per_hour',
        ),
        migrations.AddField(
            model_name='rentedvehicle',
            name='security_deposite',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
