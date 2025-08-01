# Generated by Django 5.2.1 on 2025-07-29 06:57

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ride_sharing', '0028_remove_ridesharebooking_is_return_ride_and_more'),
        ('rider_part', '0021_favoritetolocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='ridereportsubmission',
            name='ride_share_booking',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='report_submissions', to='ride_sharing.ridesharebooking'),
        ),
        migrations.AlterField(
            model_name='ridereportsubmission',
            name='ride',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='report_submissions', to='rider_part.riderequest'),
        ),
    ]
