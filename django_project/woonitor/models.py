from django.db import models
import uuid
from django.core.validators import RegexValidator


class Listing(models.Model):
    """Contains the data of a single house
    
    url: url where house can be found
    adres: string; streetname and number
    postcode: string; postcode e.g. 5035LN
    gemeente: string
    stad: string
    buurt: string
    oppervlakte: integer
    vraagprijs: integer
    energielabel: string 
    aangebodensinds: datetime
    verkoopdatum: date
    datescraped: date
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
    stad = models.CharField(max_length=100)
    buurt = models.CharField(max_length=100)
    vraagprijs = models.IntegerField(default=0)
    aangebodensinds = models.DateTimeField("Offered since")
    verkoopdatum = models.DateTimeField("Sold on")
    verkooptijd = models.IntegerField(default=0)
    datescraped = models.DateTimeField("Date scraped")

    def __str__(self):
        return f"{self.adres}, {self.postcode}, {self.stad}, id: {self.id}"