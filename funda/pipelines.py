# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
import json
from datetime import datetime


class FundaPipeline:
    def process_item(self, item, spider):
        return item

class JsonWriterPipeline:
    global firstline
    firstline = True
    
    def open_spider(self, spider):
        now = self.now()
        self.file = open(f"{now}--output.json", 'w')
        self.file.write("[\n")

    def close_spider(self, spider):
        self.file.write("]")
        self.file.close()

    def process_item(self, item, spider):
        global firstline
        if firstline:
            line = json.dumps(dict(item))
            firstline = False
        else:
            line = ",\n"+json.dumps(dict(item))

        self.file.write(line)
        return item

    def now(self):
        "formats the current date and time as YYYY-MM-DD--HH-MM"
        now = datetime.now()
        return now.strftime("%Y-%m-%d--%H-%M")
