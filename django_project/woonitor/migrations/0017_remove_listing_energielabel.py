# Generated by Django 4.2.7 on 2023-12-03 19:29

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("woonitor", "0016_remove_listing_oppervlakte"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="listing",
            name="energielabel",
        ),
    ]
