# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from asgiref.sync import sync_to_async
import json
from datetime import datetime
import re
import os
import sys
# Add the path to the directory containing your Django project
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ['DJANGO_SETTINGS_MODULE'] = 'project.settings'  # Replace with your actual project's settings module

import django
django.setup()
    
from woonitor.models import Listing

class FundaPipeline:
    def process_item(self, item, spider):
        return item
    
class webPipeLine:
    def convertInt(self, number)->int:
        """removes anything that is not a number and converts to integer"""
        return int(re.sub(r"\D","",number))
    
    def controlInt(self, dict, key)-> int:
        """Returns 0 if entry cannot be converted"""
        try: 
            return self.convertInt(dict[key])
        except:
            return 0
    
    @sync_to_async
    def process_item(self, item, spider):
        myListing = Listing(
            url = item['url'], 
            adres = item['adres'].strip(),
            postcode = item['postcode'],
            stad= item['stad'].strip(),
            buurt = "???",
            vraagprijs = self.controlInt(item, 'Vraagprijs'),
            datescraped = item['datescraped'],
            aangebodensinds = item['Aangeboden sinds'],
            verkoopdatum = item['Verkoopdatum'],
        )
        myListing.save()
        return myListing

class JsonWriterPipeline:
    global firstline
    firstline = True

    def open_spider(self, spider):
        now = self.now()
        self.file = open(f".\data\{now}.json", 'w')
        self.file.write("[\n")

    def close_spider(self, spider):
        self.file.write("\n]")
        self.file.close()

    def clean(self, item):
    # cleans up certain entries: cuts out html artifacts and converts entries to integers
        for k in item:
            match k:
                case "Vraagprijs":
                    if "Prijs op aanvraag" in item[k]:
                        pass
                    else:
                        # cut out anything but numbers
                        prijs = re.sub(r"\D", "", item[k])
                        item[k] = int(prijs)
                case "Energielabel":
                    try:
                        item[k] = re.sub(r"\r","", item[k])
                    except: 
                        pass
                case "Bouwjaar":
                    item[k] = int(item[k])
                case _:
                    pass
        return item

    def process_item(self, item, spider):
        global firstline
        if firstline:
            line = json.dumps(self.clean(dict(item)))
            firstline = False
        else:
            line = ",\n"+json.dumps(self.clean(dict(item)))

        self.file.write(line)
        return item

    def now(self):
        "formats the current date and time as YYYY-MM-DD--HH-MM"
        now = datetime.now()
        return now.strftime("%Y-%m-%d--%H-%M")
