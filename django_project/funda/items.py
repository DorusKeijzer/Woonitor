# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class FundaItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    url = scrapy.Field()
    adres = scrapy.Field()
    postcode = scrapy.Field()
    stad= scrapy.Field()
    buurt = scrapy.Field()
    vraagprijs = scrapy.Field()
    datescraped = scrapy.Field()
    aangebodensinds = scrapy.Field()
    verkoopdatum = scrapy.Field()
    verkooptijd = scrapy.Field()
    fundaID = scrapy.Field()
    duplicate = scrapy.Field()


