# Generated by Django 5.2.1 on 2025-06-10 07:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rent_vehicle', '0005_rentalrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='rentalrequest',
            name='duration_hours',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='rentalrequest',
            name='total_rent_price',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]
