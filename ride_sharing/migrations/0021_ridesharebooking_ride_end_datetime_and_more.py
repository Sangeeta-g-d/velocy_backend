# Generated by Django 5.2.1 on 2025-07-23 09:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ride_sharing', '0020_alter_ridesharebooking_vehicle'),
    ]

    operations = [
        migrations.AddField(
            model_name='ridesharebooking',
            name='ride_end_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ridesharebooking',
            name='ride_start_datetime',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
