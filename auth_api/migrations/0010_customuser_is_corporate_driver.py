# Generated by Django 5.2.1 on 2025-07-08 12:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_api', '0009_alter_customuser_driver_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='is_corporate_driver',
            field=models.BooleanField(default=False),
        ),
    ]
