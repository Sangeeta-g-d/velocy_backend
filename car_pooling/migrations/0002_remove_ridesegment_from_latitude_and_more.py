# Generated by Django 5.2.1 on 2025-06-28 06:06

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('car_pooling', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ridesegment',
            name='from_latitude',
        ),
        migrations.RemoveField(
            model_name='ridesegment',
            name='from_longitude',
        ),
        migrations.RemoveField(
            model_name='ridesegment',
            name='to_latitude',
        ),
        migrations.RemoveField(
            model_name='ridesegment',
            name='to_longitude',
        ),
    ]
