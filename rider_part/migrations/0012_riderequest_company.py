# Generated by Django 5.2.1 on 2025-07-03 09:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('corporate_web', '0002_employeecredit'),
        ('rider_part', '0011_ridemessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='riderequest',
            name='company',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='corporate_web.companyaccount'),
        ),
    ]
