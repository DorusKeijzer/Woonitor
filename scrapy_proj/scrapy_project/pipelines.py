# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json
from datetime import datetime
import re
import os
import sys
# Add the path to the directory containing your Django project
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web.web.settings")
django.setup()

from web.woonitor.models import Listing

class FundaPipeline:
    def process_item(self, item, spider):
        return item
    
class webPipeLine:
    def process_item(self, item, spider):
        myListing = Listing(
            url = item['url'], 
            adres = item['adres'],
            postcode = item['postcode'],
            stad= item['stad']
        )

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
