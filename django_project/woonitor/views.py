from django.http import HttpResponse
from django.shortcuts import render
from django.http import Http404
from django.db.models import Avg  


from .models import Listing

def index(request):
    listings = Listing.objects.all()
    context = {"listings": listings}
    return render(request, "woonitor/index.html", context)

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
    avg_prijs = listings.aggregate(Avg('vraagprijs'))['vraagprijs__avg']
    avg_prijs = f'€ {avg_prijs:,.2f}'
    avg_verkooptijd = listings.aggregate(Avg('verkooptijd'))['verkooptijd__avg']
    avg_verkooptijd = f'{avg_verkooptijd:.1f} dagen'

    context = {"listings": listings,
               "stad": stad,
               "gemiddeldePrijs" : avg_prijs,
               "gemiddeldeVerkooptijd" : avg_verkooptijd}
    
    return render(request, "woonitor/stad.html", context)

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
