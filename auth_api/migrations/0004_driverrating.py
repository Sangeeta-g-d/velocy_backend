# Generated by Django 5.2.1 on 2025-06-12 11:43

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_api', '0003_customuser_is_online'),
        ('rider_part', '0006_riderequest_end_time_riderequest_start_time'),
    ]

    operations = [
        migrations.CreateModel(
            name='DriverRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.DecimalField(decimal_places=1, max_digits=2, validators=[django.core.validators.MinValueValidator(1.0), django.core.validators.MaxValueValidator(5.0)])),
                ('review', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('driver', models.ForeignKey(limit_choices_to={'role': 'driver'}, on_delete=django.db.models.deletion.CASCADE, related_name='received_ratings', to=settings.AUTH_USER_MODEL)),
                ('rated_by', models.ForeignKey(limit_choices_to={'role': 'rider'}, on_delete=django.db.models.deletion.CASCADE, related_name='given_ratings', to=settings.AUTH_USER_MODEL)),
                ('ride', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='driver_rating', to='rider_part.riderequest')),
            ],
            options={
                'unique_together': {('ride', 'driver')},
            },
        ),
    ]
