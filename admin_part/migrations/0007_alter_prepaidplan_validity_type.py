# Generated by Django 5.2.1 on 2025-07-07 06:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_part', '0006_prepaidplan'),
    ]

    operations = [
        migrations.AlterField(
            model_name='prepaidplan',
            name='validity_type',
            field=models.CharField(choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('half_yearly', 'Half-Yearly'), ('yearly', 'Yearly')], max_length=20),
        ),
    ]
