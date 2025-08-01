# Generated by Django 5.2.1 on 2025-07-25 10:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_api', '0013_remove_driverrating_unique_normal_ride_rating_and_more'),
        ('ride_sharing', '0026_rename_driverupipayment_sharedrideupipayment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='driverrating',
            name='ride_sharing',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='driver_ratings', to='ride_sharing.ridejoinrequest'),
        ),
    ]
