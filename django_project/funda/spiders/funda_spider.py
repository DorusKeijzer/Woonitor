import scrapy
import re
from datetime import datetime
from datetime import date
from django.utils import timezone

class spider(scrapy.Spider):
    name = "het_fundamannetje"
    # start_urls should end in "search_result=1"
    start_urls = [r"https://www.funda.nl/zoeken/koop?selected_area=%5B%22tilburg%22%5D&availability=%5B%22unavailable%22%5D&search_result=1"]
    # start_urls = [r"https://www.funda.nl/zoeken/koop?selected_area=%5B%22tiel%22%5D&availability=%5B%22unavailable%22%5D&search_result=1"]
    # start_urls = [r'https://www.funda.nl/koop/verkocht/tiel/huis-42352883-dr-schaepmanstraat-47/']
    def parse(self, response):

        if "Geen resultaten" in response.text:
            # klaar met zoeken.
            pass 

        else:
            # geeft alle huizenlinks op een "zoeken" page 
            # TODO fix deeplink
            huizenlinks = response.css("div.p-4 a::attr(href)").re(r".*/koop/tilburg.*")
            huizenlinks = set(huizenlinks) # remove duplicates

            # bezoek alle huizenpaginas en sla ze op:
            for huizenlink in huizenlinks:
                yield scrapy.Request(url=huizenlink, callback=self.parsehuis)

            next_page = self.nextpage(response.url)
            yield scrapy.Request(url=next_page, callback=self.parse)

    def parsehuis(self, response):
        """Gets the data specified in models.py of one house"""      
        adres = clean(response.css("span.object-header__title::text").get())
        postcode = response.css("span.object-header__subtitle::text").re("\d{4} \w\w")[0].replace(" ", "")
        stad = clean(response.css("span.object-header__subtitle::text").re("\d{4} \w\w (.*)")[0])
        buurt = response.css("a.fd-m-left-2xs--bp-m::text").get()
        kenmerken = { 
                "datescraped": timezone.now(),
                "url" : response.url,
                "adres": adres,
                "stad" : stad,
                "postcode" : postcode,
                "buurt" : buurt
              }
        
        # Extracting data from Verkoopgeschiedenis section
        linkerkolom = response.css('.object-kenmerken-list dt::text').getall()
        rechterkolom = response.css('.object-kenmerken-list dd::text').getall()
    
        for links, rechts in zip(linkerkolom, rechterkolom):
            if links in ["Verkoopdatum", "Aangeboden sinds"]:
                kenmerken[links.strip()] = parseDate(rechts.strip())

        # Extracting data from Kenmerken section
        laatste_vraagprijs = response.css('.object-kenmerken-list dt:contains("Laatste vraagprijs") + dd span::text').get()
        kenmerken['Vraagprijs'] = laatste_vraagprijs
        print(kenmerken)
        self.log(kenmerken)
        yield kenmerken

    def nextpage(self, url) -> str:
        """When given a lisnk that ends in 'search_results=[integer]', 
        this function returns that link, ending in 'search_results=[integer + 1]
        
        e.g. : .../search_results=2 -> .../search_results=3'"""
        page = re.match(r"(.*search_result=)(\d+)",url)
        return page.group(1) + str(int(page.group(2))+1)

        
    # legacy, version, scrapes everything there is to scrape. 
    # does not work well with database

    # def parsehuis(self, response):
    #     # de elementen die adres, postcode en prijs geven staan niet tussen de kenmerkenlijst
    #     adres = response.css("span.object-header__title::text").get()
    #     postcode = response.css("span.object-header__subtitle::text").re("\d{4} \w\w")[0]
    #     stad = response.css("span.object-header__subtitle::text").re("\d{4} \w\w (.*)")[0]
    #     kenmerken = { 
    #             "datescraped": datetime.now(),
    #             "url" : response.url,
    #             "adres": adres,
    #             "stad" : stad,
    #             "postcode" : postcode,
    #           }
        
    #     # bevat alle kenmerken van het huis
    #     kenmerkenbody = response.css("div.object-kenmerken-body dt")

    #     for kenmerk in kenmerkenbody:
    #         naam = kenmerk.css('::text').re_first(r"[\n\r]*(.*)[\n\r]*")
    #         dd_element = kenmerk.xpath('following-sibling::dd[1]')
    #         waarde = dd_element.css('span::text').re_first(r"[\n\r]*(.*)[\n\r]*")
           
    #         # Add the data to the dictionary
    #         kenmerken[naam] = waarde
       
    #     yield kenmerken

    #     self.log(f'url: {response.url}')





def parseDate(datestring) -> date:
    """Parses a natural language string into a date
    
    e.g. 9 November 2013->datetime(2013,11,9)"""

    monthdict = {
        'januari':1,
        'februari':2,
        'maart':3,
        'april':4,
        'mei':5,
        'juni':6,
        'juli':7,
        'augustus':8,
        'september':9,
        'oktober':10,
        'november':11,
        'december':12}
    datesplit = datestring.split(" ")

    day = int(datesplit[0])
    month = monthdict[datesplit[1]]
    year = int(datesplit[2])

    return timezone.datetime(year, month, day)


def clean(text)->str:
    r"""Removes '\r' and '\n' tags"""
    return re.sub(r"[\r\n]","",text)