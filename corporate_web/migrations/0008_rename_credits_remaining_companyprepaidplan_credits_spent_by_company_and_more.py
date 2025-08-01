# Generated by Django 5.2.1 on 2025-07-14 05:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('corporate_web', '0007_alter_companyprepaidplan_company'),
    ]

    operations = [
        migrations.RenameField(
            model_name='companyprepaidplan',
            old_name='credits_remaining',
            new_name='credits_spent_by_company',
        ),
        migrations.AddField(
            model_name='companyprepaidplan',
            name='credits_spent_by_employees',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
