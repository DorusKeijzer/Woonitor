import scrapy
import re
from datetime import datetime

class spider(scrapy.Spider):
    name = "het_fundamannetje"
    start_urls = [r"https://www.funda.nl/zoeken/koop?selected_area=%5B%22tilburg%22%5D&search_result=1"]
 
    def parse(self, response):
        if "Geen resultaten" in response.text:
            # klaar met zoeken.
            pass 

        else:
            # geeft alle huizenlinks op een "zoeken" page 
            huizenlinks = response.css("div.p-4 a::attr(href)").re(r".*/koop/tilburg.*")
            huizenlinks = set(huizenlinks) # remove duplicates

            # bezoek alle huizenpaginas en sla ze op:
            for huizenlink in huizenlinks:
                yield scrapy.Request(url=huizenlink, callback=self.parsehuis)

            # volgende pagina is de huidige pagina + 1
            page = re.match(r"(.*search_result=)(\d+)",
                                response.url)
            next_page = page.group(1) + str(int(page.group(2))+1)

            # bezoek en parseer de volgende pagina
            if int(page.group(2)+1) < 4:
                yield scrapy.Request(url=next_page, callback=self.parse)

    def parsehuis(self, response):
        # de elementen die adres, postcode en prijs geven staan niet tussen de kenmerkenlijst
        adres = response.css("span.object-header__title::text").get()
        postcodeEnStad = response.css("span.object-header__subtitle::text")
        postcode = response.css("span.object-header__subtitle::text").re("\d{4} \w\w")[0]
        postcode = response.css("span.object-header__subtitle::text").re("\d{4} \w\w (\w+)")[0]
        kenmerken = { 
                "datescraped": datetime.now(),
                "url" : response.url,
                "Adres": adres,
                "Postcode" : postcode,
              }
        
        # bevat alle kenmerken van het huis
        kenmerkenbody = response.css("div.object-kenmerken-body dt")

        for kenmerk in kenmerkenbody:
            naam = kenmerk.css('::text').re_first(r"[\n\r]*(.*)[\n\r]*")
            dd_element = kenmerk.xpath('following-sibling::dd[1]')
            waarde = dd_element.css('span::text').re_first(r"[\n\r]*(.*)[\n\r]*")
           
            # Add the data to the dictionary
            kenmerken[naam] = waarde
       
        yield kenmerken

        self.log(f'url: {response.url}')





# TODO fix login

  # def start_requests(self): # TODO mask password
    #     login_url = "https://login.funda.nl/account/login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3Dfunda.website%26redirect_uri%3Dhttps%253A%252F%252Fwww.funda.nl%252Fauth%252Fsignin-oidc%252F%26response_type%3Dcode%2520id_token%26scope%3Dopenid%2520profile%2520funda_basic%2520funda_login_metadata%26state%3DOpenIdConnect.AuthenticationProperties%253DyTId6lwTSo4lSH76setIDKX4VRbw0teqLmdjRavEsFe9_jCARy1LnVP-iAHt7K-Iqj89SF2gPhLnRwsvBedmTCh_gL45N1C-EC1tg1XwvsKE0froFkSXPX7C0r7iUdxmmHaiQGZKqcFmnUrf8spTvjvx8rqkpcNctbgJgh1YcXfzkZOYQReWaTjsvbaqrTpOimRwXq-nTFF8j8Ai6_WXpAqLeZU%26response_mode%3Dform_post%26nonce%3D638367132241725717.NjJiOTU1NTYtN2M4Zi00MjcyLWEzNjUtOTI1YzBhNzY3ZTQ2MzlkMzFjY2MtMmY1ZS00YjZhLTlmYmMtZWM3NjRmZmQ0NjI5%26x-client-SKU%3DID_NET461%26x-client-ver%3D6.7.1.0"
    #     yield scrapy.FormRequest(login_url, formdata={'UserName': 'HarryKanker@proton.me', 'Password': 'Costello1'}, callback=self.after_login)

    # def after_login(self,response):
    #     if "Harry" in response.txt:
    #         self.log("Login succesful")
    #         yield scrapy.Request(url=r'https://www.funda.nl/zoeken/koop?selected_area=%5B%22tilburg%22%5D', callback=self.parse_data)
    #     else:
    #         self.log("Login failed")
