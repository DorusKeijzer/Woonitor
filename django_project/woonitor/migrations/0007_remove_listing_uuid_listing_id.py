# Generated by Django 4.2.7 on 2023-12-03 07:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("woonitor", "0006_rename_id_listing_uuid"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="listing",
            name="uuid",
        ),
        migrations.AddField(
            model_name="listing",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                default=1,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
            preserve_default=False,
        ),
    ]
