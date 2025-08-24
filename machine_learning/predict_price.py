import math
from scipy.stats import gaussian_kde

import optuna
from sklearn.model_selection import cross_val_score, KFold
from sklearn.metrics import mean_absolute_error
import numpy as np

from sklearn.cluster import KMeans
import pandas as pd
import psycopg
import os
from dotenv import load_dotenv
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import matplotlib.pyplot as plt
import seaborn as sns
from xgboost import XGBRegressor
from sklearn.ensemble import RandomForestRegressor
from catboost import CatBoostRegressor
from sklearn.linear_model import Ridge, Lasso


load_dotenv()

def get_listings():
    conn = psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=5432,
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )
    query = """
        SELECT
            last_asking_price,
            surface_area,
            bedrooms,
            total_rooms,
            listing_type,
            neighborhood,
            city,
            energy_label,
            building_year,
            sell_date
        FROM listings
        WHERE last_asking_price IS NOT NULL
          AND city IN ('Amsterdam', 'Rotterdam', 'Den', 'Groningen', 'Tilburg', 'Eindhoven', 'Utrecht')
          AND sell_date > '2025-02-01'
        LIMIT 100000;
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def detrend(dataframe: pd.DataFrame) -> pd.DataFrame:
    dataframe['sell_date'] = pd.to_datetime(dataframe['sell_date'])
    dataframe = dataframe.sort_values('sell_date')
    
    # Set sell_date as index for time-based rolling
    dataframe = dataframe.set_index('sell_date')
    
    # Rolling median over  days
    dataframe['trend_price'] = dataframe['last_asking_price'].rolling('30D').median()
    
    # Fill any NaNs at start or end
    dataframe['trend_price'] = dataframe['trend_price'].fillna(method='bfill').fillna(method='ffill')
    
    # Compute detrended residuals
    dataframe['detrended_price'] = dataframe['last_asking_price'] - dataframe['trend_price']
    
    # Restore sell_date as a column
    dataframe = dataframe.reset_index()
    
    return dataframe


from sklearn.cluster import KMeans

def transform(dataframe: pd.DataFrame):
    # Clean listing type
    dataframe['listing_type_clean'] = dataframe['listing_type'].str.split(r'[\(,]').str[0].str.strip()
    
    # Keep relevant columns including neighborhood
    dataframe = dataframe[['surface_area',
                           'listing_type_clean',
                           'bedrooms', 
                           'total_rooms',
                           'city', 
                           'energy_label', 
                           'neighborhood',
                           'detrended_price']]

    # Fill numeric columns with median
    for col in ['surface_area', 'bedrooms', 'total_rooms', 'detrended_price']:
        dataframe[col] = dataframe[col].fillna(dataframe[col].median())

    # Fill categorical columns with 'Unknown'
    for col in ['listing_type_clean', 'city', 'energy_label', 'neighborhood']:
        dataframe[col] = dataframe[col].fillna('Unknown')

    # Interaction features
    dataframe['bedrooms_per_room'] = dataframe['bedrooms'] / dataframe['total_rooms']
    dataframe['area_per_room'] = dataframe['surface_area'] / dataframe['total_rooms']
    dataframe['bedrooms_area_interaction'] = dataframe['bedrooms'] * dataframe['surface_area']
    dataframe['area_times_bedrooms'] = dataframe['surface_area'] * dataframe['bedrooms']

    # Clip outliers in detrended price (1st and 99th percentile)
    lower = dataframe['detrended_price'].quantile(0.01)
    upper = dataframe['detrended_price'].quantile(0.99)
    dataframe['detrended_price'] = dataframe['detrended_price'].clip(lower, upper)

    # Neighborhood clustering
    neighborhood_medians = dataframe.groupby('neighborhood')['detrended_price'].median().reset_index()
    kmeans = KMeans(n_clusters=15, random_state=42)
    neighborhood_medians['cluster'] = kmeans.fit_predict(neighborhood_medians[['detrended_price']])
    cluster_map = neighborhood_medians.set_index('neighborhood')['cluster']
    dataframe['neighborhood_cluster'] = dataframe['neighborhood'].map(cluster_map)

    # One-hot encode categorical variables (including neighborhood cluster)
    dataframe = pd.get_dummies(dataframe, 
                               columns=['listing_type_clean', 'city', 'energy_label', 'neighborhood_cluster'], 
                               drop_first=True)

    # Drop original neighborhood column
    dataframe = dataframe.drop(columns=['neighborhood'])

    return dataframe
def visualize(df: pd.DataFrame):
    plt.figure(figsize=(8, 5))
    sns.histplot(df['detrended_price'], bins=50, kde=True)
    plt.title('Distribution of Detrended Prices')
    plt.xlabel('Detrended Price')
    plt.ylabel('Count')
    plt.show()

def tune_catboost(X_train, y_train, n_trials=10):
    def objective(trial):
        params = {
            "depth": trial.suggest_int("depth", 4, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
            "iterations": trial.suggest_int("iterations", 500, 1500),
            "l2_leaf_reg": trial.suggest_int("l2_leaf_reg", 1, 10),
            "random_seed": 42,
            "verbose": 0
        }
        model = CatBoostRegressor(**params)
        cv = KFold(n_splits=3, shuffle=True, random_state=42)
        scores = -cross_val_score(model, X_train, y_train, cv=cv, scoring='neg_mean_absolute_error', n_jobs=-1)
        return scores.mean()
    
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials)
    return study.best_params



if __name__ == "__main__":
    listings = get_listings()
    listings = detrend(listings)
    mean_val = listings['trend_price'].sample(n=1, random_state=42).iloc[0]
    listings = transform(listings)
    print("MEAN VAL:",mean_val)

    X = listings.drop(columns=['detrended_price'])
    y = listings['detrended_price'] 

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Define quantiles you want to predict
    quantiles = np.linspace(0.05,0.95,50)
    models = {}

    results = {}
    for q in quantiles:
        print(f"Training CatBoost for quantile {q}...")
        model = CatBoostRegressor(loss_function=f'Quantile:alpha={q}', verbose=0)
        model.fit(X_train, y_train)
        models[q] = model

        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = math.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        results[q] = {"MAE": mae, "RMSE": rmse, "R2": r2}

    for q, metrics in sorted(results.items()):
        print(f"Quantile {q}: MAE={metrics['MAE']:.2f}, RMSE={metrics['RMSE']:.2f}, R2={metrics['R2']:.4f}")

    # Visualization for a dummy data point
    dummy_point = X_test.iloc[0:1]


    predicted_prices = [models[q].predict(dummy_point)[0] + mean_val for q in quantiles]

# Generate samples by interpolating between quantiles
    n_samples = 10000
    uniform_samples = np.random.rand(n_samples)
    samples = np.interp(uniform_samples, quantiles, predicted_prices)

# Fit KDE
    kde = gaussian_kde(samples)

# Define plotting range
    x = np.linspace(min(predicted_prices)*0.95, max(predicted_prices)*1.05, 1000)
    pdf = kde(x)

# Compute 25th and 75th percentile for shading
    p25 = np.percentile(samples, 25)
    p75 = np.percentile(samples, 75)

# Plot PDF
    plt.figure(figsize=(8,5))
    plt.plot(x, pdf, label='Estimated PDF', color='blue')
    plt.fill_between(x, pdf, where=(x >= p25) & (x <= p75), color='orange', alpha=0.3, label='25%-75% range')
    plt.xlabel('Predicted Price')
    plt.ylabel('Density')
    plt.title('Smoothed PDF with Interquartile Range')
    plt.grid(True)
    plt.legend()
    plt.show()
