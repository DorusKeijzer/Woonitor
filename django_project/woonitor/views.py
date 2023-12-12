from django.http import HttpResponse
from django.shortcuts import render
from django.http import Http404
from django.db.models import Avg  
from django.utils import timezone
import json
from .models import Listing
from django.core.serializers.json import DjangoJSONEncoder


def index(request):
    listings = Listing.objects.all()
    aantal = listings.count
    context = {"listings": listings,
               "aantal" : aantal}
    return render(request, "woonitor/modern.html", context)

def item(request, stad, id):
    try: 
        item = Listing.objects.get(id=id)
    except:
        raise Http404("House does not exist")

    scrapedate = item.datescraped.strftime('%m/%d/%Y - %H:%M:%S')
    aangebodensinds = item.aangebodensinds.strftime('%m/%d/%Y')
    verkoopdatum = item.verkoopdatum.strftime('%m/%d/%Y')
    
    vraagprijs = f"€ {item.vraagprijs:,}".replace(',','.')

    context = {"item": item, 
               "date": scrapedate, 
               "aangebodensinds" : aangebodensinds,
               "verkoopdatum" : verkoopdatum,
               "vraagprijs": vraagprijs,
                }
    
    return render(request, "woonitor/item.html", context)

def stad(request, stad):
    listings = Listing.objects.filter(stad=stad)
    aantal = listings.count
    avg_prijs = listings.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
    avg_prijs = f'€ {avg_prijs:,.2f}'
    avg_verkooptijd = listings.aggregate(Avg('verkooptijd'))['verkooptijd__avg']
    avg_verkooptijd = f'{avg_verkooptijd:.1f} dagen'
    
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=30)  # Assuming a month is approximately 30 days

    # finds the number corresponding to last month's date
    lastmonthnumber = ((end_date.month-2) % 12)+1
    lastmonthname = maand(lastmonthnumber)

    now = timezone.now()
    start_date = timezone.datetime(now.year, now.month - 1, 1)
    end_date = timezone.datetime(now.year, now.month, 1) - timezone.timedelta(days=1)
    lastmonth = listings.filter(verkoopdatum__range=[start_date, end_date])

    avg_prijs_lastmonth = lastmonth.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
    if not avg_prijs_lastmonth:
        avg_prijs_lastmonth = "N/A"
    else:
        avg_prijs_lastmonth = f'€ {avg_prijs_lastmonth:,.2f}'
    avg_verkooptijd_lastmonth = lastmonth.aggregate(Avg('verkooptijd'))['verkooptijd__avg']
    if not avg_verkooptijd_lastmonth:
        avg_verkooptijd_lastmonth = "N/A"
    else:
        avg_verkooptijd_lastmonth = f'{avg_verkooptijd_lastmonth:.1f} dagen'


    context = {"listings": listings,
               "stad": stad,
               "gemiddeldePrijs" : avg_prijs,
               "gemiddeldeVerkooptijd" : avg_verkooptijd,
               "vorigemaand": lastmonthname,
               "maandPrijs" : avg_prijs_lastmonth,
               "maandTijd": avg_verkooptijd_lastmonth,
               "aantal" : aantal}
    
    return render(request, "woonitor/stad.html", context)

def analyse(request, stad):
    listings = Listing.objects.filter(stad=stad)
    aantal  = listings.count
    ids = [item.id for item in listings]

    avg_prijs = listings.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
    if not avg_prijs:
        avg_prijs = "N/A"
    else:
        avg_prijs = f'€ {avg_prijs:,.2f}'
    avg_verkooptijd = listings.aggregate(Avg('verkooptijd'))['verkooptijd__avg']
    if not avg_verkooptijd:
        avg_verkooptijd = "N/A"
    else:
        avg_verkooptijd = f'€ {avg_verkooptijd:,.2f}'
    
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=30)  # Assuming a month is approximately 30 days

    # finds the number corresponding to last month's date
    lastmonthnumber = ((end_date.month-2) % 12)+1
    lastmonthname = maand(lastmonthnumber)

    now = timezone.now()
    start_date = timezone.datetime(now.year, now.month - 1, 1)
    end_date = timezone.datetime(now.year, now.month, 1) - timezone.timedelta(days=1)
    lastmonth = listings.filter(verkoopdatum__range=[start_date, end_date])

    avg_prijs_lastmonth = lastmonth.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
    if not avg_prijs_lastmonth:
        avg_prijs_lastmonth = "N/A"
    else:
        avg_prijs_lastmonth = f'€ {avg_prijs_lastmonth:,.2f}'
    avg_verkooptijd_lastmonth = lastmonth.aggregate(Avg('verkooptijd'))['verkooptijd__avg']
    if not avg_verkooptijd_lastmonth:
        avg_verkooptijd_lastmonth = "N/A"
    else:
        avg_verkooptijd_lastmonth = f'{avg_verkooptijd_lastmonth:.1f} dagen'

    context = {"listings": listings,
            "stad": stad,
            "gemiddeldePrijs" : avg_prijs,
            "gemiddeldeVerkooptijd" : avg_verkooptijd,
            "vorigemaand": lastmonthname,
            "maandPrijs" : avg_prijs_lastmonth,
            "maandTijd": avg_verkooptijd_lastmonth,
            "aantal" : aantal}

    verkoopdatum_list = list(listings.values_list('verkoopdatum', flat=True))

    # Format datetime data as strings in ISO 8601 format
    formatted_verkoopdatum = [dt.strftime('%Y-%m-%dT%H:%M:%S') for dt in verkoopdatum_list]

    # Other data
    adres_list = list(listings.values_list('adres', flat=True))
    prijs_list = list(listings.values_list('vraagprijs', flat=True))
    tijd_list = list(listings.values_list('verkooptijd', flat=True))

    # Construct the JSON data
    data = json.dumps(
        {
            "adres": adres_list,
            "id": ids,
            "prijs": prijs_list,
            "tijd": tijd_list,
            "verkoopdatum": formatted_verkoopdatum
        },
        cls=DjangoJSONEncoder  # Use Django's JSON encoder to handle datetime objects
    )

    context["data"] = data

    return render(request, "woonitor/analyse.html", context)

def maand(integer)->str:
    """Returns the month in Dutch that corresponds to the integer
    e.g.: maand(3) -> 'maart'"""
    monthdict = {
    1:'januari',
    2:'februari',
    3:'maart',
    4:'april',
    5:'mei',
    6:'juni',
    7:'juli',
    8:'augustus',
    9:'september',
    10:'oktober',
    11:'november',
    12:'december'}
    if integer<=12 and integer >=0:
        return monthdict[integer]
    else:
        raise ValueError(f"{integer} does not correspond to a month. Pick a number between 0 and 12")


#TODO implementeer buurten (eerst: buurt in scraper)
# def buurt(request, stad, buurt):
#     listings = Listing.objects.filter(stad=stad)
#     avg_prijs = listings.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
#     avg_oppervlak = listings.aggregate(Avg('oppervlakte'))['oppervlakte__avg']

#     avg_prijs = f'€ {avg_prijs:,.2f}'
#     avg_oppervlak = f"{int(avg_oppervlak)} m²"

#     context = {"listings": listings,
#                "stad": stad,
#                "gemiddeldePrijs" : avg_prijs,
#                "gemiddeldeOppervlak" : avg_oppervlak}
    
#     return render(request, "woonitor/stad.html", context)
