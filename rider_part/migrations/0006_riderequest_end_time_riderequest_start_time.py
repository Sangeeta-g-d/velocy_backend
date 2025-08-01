# Generated by Django 5.2.1 on 2025-06-12 10:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rider_part', '0005_riderequest_driver'),
    ]

    operations = [
        migrations.AddField(
            model_name='riderequest',
            name='end_time',
            field=models.DateTimeField(blank=True, help_text='Ride end time (in IST)', null=True),
        ),
        migrations.AddField(
            model_name='riderequest',
            name='start_time',
            field=models.DateTimeField(blank=True, help_text='Ride start time (in IST)', null=True),
        ),
    ]
