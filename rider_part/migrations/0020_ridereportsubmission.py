# Generated by Django 5.2.1 on 2025-07-25 11:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_part', '0009_remove_ridereport_ride'),
        ('rider_part', '0019_rename_shared_ride_driverwallettransaction_shared_join_ride'),
    ]

    operations = [
        migrations.CreateModel(
            name='RideReportSubmission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField()),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('report_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_submissions', to='admin_part.ridereport')),
                ('ride', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_submissions', to='rider_part.riderequest')),
            ],
        ),
    ]
