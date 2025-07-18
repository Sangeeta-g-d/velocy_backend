# Generated by Django 5.2.1 on 2025-06-28 05:45

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CarPoolRide',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_location_name', models.CharField(max_length=255)),
                ('start_latitude', models.FloatField()),
                ('start_longitude', models.FloatField()),
                ('end_location_name', models.CharField(max_length=255)),
                ('end_latitude', models.FloatField()),
                ('end_longitude', models.FloatField()),
                ('date', models.DateField()),
                ('time', models.TimeField()),
                ('total_seats', models.PositiveIntegerField()),
                ('available_seats', models.PositiveIntegerField()),
                ('final_price', models.DecimalField(decimal_places=2, help_text='Total price from start to end location', max_digits=10)),
                ('estimated_duration', models.DurationField(blank=True, help_text='Estimated total travel time', null=True)),
                ('distance_km', models.DecimalField(blank=True, decimal_places=2, help_text='Distance in kilometers', max_digits=6, null=True)),
                ('driver_notes', models.TextField(blank=True, help_text='Optional notes or instructions from the driver', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='carpool_rides', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RideSegment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_location_name', models.CharField(max_length=255)),
                ('from_latitude', models.FloatField()),
                ('from_longitude', models.FloatField()),
                ('to_location_name', models.CharField(max_length=255)),
                ('to_latitude', models.FloatField()),
                ('to_longitude', models.FloatField()),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('ride', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='segments', to='car_pooling.carpoolride')),
            ],
        ),
        migrations.CreateModel(
            name='RideStop',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location_name', models.CharField(max_length=255)),
                ('latitude', models.FloatField()),
                ('longitude', models.FloatField()),
                ('order', models.PositiveIntegerField(help_text='Order of the stop along the route')),
                ('ride', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stops', to='car_pooling.carpoolride')),
            ],
            options={
                'ordering': ['order'],
            },
        ),
    ]
