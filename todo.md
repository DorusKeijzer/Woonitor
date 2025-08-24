DE

1. scrape all data
  funda restricts queries to 9990 results. Need to reinstate crawler class to accept queries some other way (perhaps deeplink) as to be able to have both small and big queries)
2. fix automatic rescraping + backoff
    - store all cities a message queue template
    - scrape the total number of listings for a city
    - auto generate crawler message queue
    - run message queue every day / x days

Viz 

3. map caching
4. difference per month visualization
5. cut time trend visualizatioin short until current month ends

DS 
1. clustering model

2. time to sell model
3. price model
4. anomaly detection: probabilistic regression and find outliers

2 & 3: take into account drift. Detrend the drifted data, and use this to obtain a large dataset to train on. Then predict general price drift, perhaps over clusters, then reapply trend

5. price explanation




MLE

Serve above models.

