# Generated by Django 4.2.7 on 2023-12-03 07:24

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("woonitor", "0005_listing_oppervlakte_listing_vraagprijs_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="listing",
            old_name="id",
            new_name="uuid",
        ),
    ]
