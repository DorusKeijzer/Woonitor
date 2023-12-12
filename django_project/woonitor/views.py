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
    
    lastmonthname, avg_verkooptijd_lastmonth, avg_prijs_lastmonth, numberssold = monthdata(listings, timezone.now().month, timezone.now.year)


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
    
    now = timezone.now()    
    lastmonthnumber = ((now.month-2) % 12)+1
    year = now.year -1 if lastmonthnumber == 12 else now.year

    lastmonthname, avg_verkooptijd_lastmonth, avg_prijs_lastmonth, _ = monthdata(listings, lastmonthnumber, year)
    avg_prijs_lastmonth, avg_verkooptijd_lastmonth = formataverage(avg_prijs_lastmonth, avg_verkooptijd_lastmonth)

    avg_prijs, avg_verkooptijd = averages(listings)
    avg_prijs, avg_verkooptijd = formataverage(avg_prijs,avg_verkooptijd)

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

    monthlyaverage, months, numberssold = avgpermonth(now, listings,24)
    # Construct the JSON data
    data = json.dumps(
        {
            "adres": adres_list,
            "id": ids,
            "prijs": prijs_list,
            "tijd": tijd_list,
            "verkoopdatum": formatted_verkoopdatum,
            "avgpermonth" : monthlyaverage,
            "months" : months,
            "numberssold" : numberssold,
        },
        cls=DjangoJSONEncoder  # Use Django's JSON encoder to handle datetime objects
    )

    context["data"] = data

    return render(request, "woonitor/analyse.html", context)

def averages(listings):
    avg_prijs = listings.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
    avg_verkooptijd = listings.aggregate(Avg('verkooptijd'))['verkooptijd__avg']

    return avg_prijs, avg_verkooptijd

def formataverage(avg_prijs, avg_verkooptijd):
    if avg_prijs:
        prijs ="$ {:,.2f}".format(avg_prijs)
    else:
        prijs = "N/A"
    if avg_verkooptijd:
        tijd = f"{avg_verkooptijd:.0f} dagen"
    else:
        tijd = "N/A"
    
    return prijs, tijd

def monthdata(listings, monthnumber, yearnumber):
    """returns the name of last month, the average sell time, the average price and the number of units sold"""
    lastmonthname = month(monthnumber)

    start_date = timezone.datetime(yearnumber, monthnumber, 1)
    if monthnumber == 12:
        end_date = timezone.datetime(yearnumber+1, 1, 1) - timezone.timedelta(days=1)
    else:
        end_date = timezone.datetime(yearnumber, monthnumber+1, 1) - timezone.timedelta(days=1)
    lastmonth = listings.filter(verkoopdatum__range=[start_date, end_date])
    
    avg_prijs_lastmonth, avg_verkooptijd_lastmonth = averages(lastmonth)
    housesSold = lastmonth.count()
    return lastmonthname, avg_verkooptijd_lastmonth, avg_prijs_lastmonth, housesSold

def avgpermonth(enddate, listings, no_of_months):
    prices = []
    months = []
    housesSold = []
    j = 0
    for n in range(1,no_of_months):
        monthnumber = ((enddate.month-1-n) % 12)+1
        if monthnumber == 12:
            j+=1
        if (avgs := monthdata(listings, monthnumber, enddate.year-j)):
            _, _, avgprice, numberSold = avgs
            prices.insert(0,avgprice)
        else:
            prices.insert(0,0)
        housesSold.insert(0,numberSold)
        months.insert(0,month(monthnumber))
    return prices, months, housesSold


def month(integer)->str:
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
