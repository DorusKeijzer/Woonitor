# Woonitor:
Met wonitor kun je de Nederlandse huizenmarkt in de gaten houden. Woonitor bestaat uit een scraper die huizendata van Funda haalt, en een web-app die je kunt gebruiken om deze data te visualiseren. 

## Hoe te gebruiken:
### Environment
Installeer anaconda, clone deze repository. Maak een conda-environment doormiddel van het volgende commando:

```
conda create --name woonitor --file requirements.txt
```

### Scraper

De scraper wordt aangeroepen vanuit ``root\django_project``. Voorlopig staat tilburg gehardcode als enige stad om te scrapen. Het volgende commando laat de scraper zijn gang gaan:

```
cd .\django_project
scrapy crawl het_fundamannetje
```

### Web app
De web app wordt ook gestard vanuit ``root\django_project``. Het volgende commando start de web-app:
```
cd .\django_project
py manage.py runserver
```


## To do:
* maak hem iets mooier
* Implementeer datavisualisatie met charts.js
    * filteren per maand
    * filteren per buurt
    * prijsontwikkelingen over tijd
* Schedling
* Implementeer uuid
* Voorkom dat de scraper reeds bezochte links nog eens scrapet
* gebruiksvriendelijk maken 
    * Eerst startlink kiezen via CMD
    * Daarna bash script
    * Later grafische interface
