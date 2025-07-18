# Generated by Django 5.2.1 on 2025-06-24 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ride_sharing', '0004_alter_ridesharevehicle_vehicle_number'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ride',
            old_name='available_seats',
            new_name='seats_left',
        ),
        migrations.AddField(
            model_name='ride',
            name='total_seats',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
