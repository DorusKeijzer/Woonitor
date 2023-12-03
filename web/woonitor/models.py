from django.db import models
import uuid
from django.core.validators import RegexValidator


class Listing(models.Model):
    """Contains the data of a single house"""
    url = models.CharField(max_length=200)
    adres = models.CharField(max_length=200)
    postcode = models.CharField(
        max_length=6,
        # is postcode formatted correctly
        validators=[
            RegexValidator(
                regex=r'^\d{4}[A-Z]{2}',
                message='Enter a valid format (e.g., 2424DD)',
                code='invalid_format'
            ),]
    )
    stad = models.CharField(max_length=100)
    buurt = models.CharField(max_length=100)
    oppervlakte = models.IntegerField(default=0)
    vraagprijs = models.IntegerField(default=0)
    datescraped = models.DateTimeField("Date scraped")

    def __str__(self):
        return f"{self.id}, {self.adres}, {self.postcode}, {self.stad}"