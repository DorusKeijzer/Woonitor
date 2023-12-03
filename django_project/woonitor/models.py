from django.db import models
import uuid
from django.core.validators import RegexValidator


class Listing(models.Model):
    """Contains the data of a single house
    
    url: url where house can be found
    adres: streetname and number
    postcode: postcode i.e. 5035LN
    stad: city
    buurt: buurt
    oppervlakte: integer
    vraagprijs: integer
    datescraped: datetime
    """
    # funda url van de woning
    url = models.CharField(max_length=200)
    # straat en huisnummer
    adres = models.CharField(max_length=200)
    # zescijferige postcode zonder spatie
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
    gemeente = models.CharField(max_length=100)
    stad = models.CharField(max_length=100)
    buurt = models.CharField(max_length=100)
    oppervlakte = models.IntegerField(default=0)
    vraagprijs = models.IntegerField(default=0)
    bouwjaar = models.IntegerField(default=0)
    energielabel = models.CharField(max_length=6)
    aangebodensinds = models.DateTimeField("Offered since")
    verkoopdatum = models.DateTimeField("Sold on")
    datescraped = models.DateTimeField("Date scraped")

    def __str__(self):
        return f"{self.adres}, {self.postcode}, {self.stad}, id: {self.id}"