# Generated by Django 5.2.1 on 2025-07-01 07:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('driver_part', '0002_cashoutrequest'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cashoutrequest',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('processed', 'Processed')], default='pending', max_length=10),
        ),
    ]
