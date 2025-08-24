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


def transform_train(df: pd.DataFrame):
    # Clean listing type
    df['listing_type_clean'] = df['listing_type'].str.split(r'[\(,]').str[0].str.strip()
    
    # Fill numeric columns with median
    for col in ['surface_area', 'bedrooms', 'total_rooms', 'detrended_price']:
        df[col] = df[col].fillna(df[col].median())
    
    # Fill categorical columns
    for col in ['listing_type_clean', 'city', 'energy_label', 'neighborhood']:
        df[col] = df[col].fillna('Unknown')

    # Interaction features
    df['bedrooms_per_room'] = df['bedrooms'] / df['total_rooms']
    df['area_per_room'] = df['surface_area'] / df['total_rooms']
    df['bedrooms_area_interaction'] = df['bedrooms'] * df['surface_area']
    df['area_times_bedrooms'] = df['surface_area'] * df['bedrooms']

    # Clip outliers
    lower = df['detrended_price'].quantile(0.01)
    upper = df['detrended_price'].quantile(0.99)
    df['detrended_price'] = df['detrended_price'].clip(lower, upper)

    # --- Target encoding for neighborhood (train only) ---
    neighborhood_means = df.groupby('neighborhood')['detrended_price'].mean()
    df['neighborhood_te'] = df['neighborhood'].map(neighborhood_means)

    # --- Optional: clustering on target-encoded neighborhood ---
    kmeans = KMeans(n_clusters=15, random_state=42)
    df['neighborhood_cluster'] = kmeans.fit_predict(df[['neighborhood_te']])

    # One-hot encode categorical vars
    df = pd.get_dummies(df, 
                        columns=['listing_type_clean', 'city', 'energy_label', 'neighborhood_cluster'], 
                        drop_first=True)
    df = df.drop(columns=['neighborhood', 'listing_type'])


    return df, neighborhood_means, kmeans

def transform_test(df: pd.DataFrame, neighborhood_means, kmeans):
    df['listing_type_clean'] = df['listing_type'].str.split(r'[\(,]').str[0].str.strip()
    
    for col in ['surface_area', 'bedrooms', 'total_rooms', 'detrended_price']:
        df[col] = df[col].fillna(df[col].median())
    for col in ['listing_type_clean', 'city', 'energy_label', 'neighborhood']:
        df[col] = df[col].fillna('Unknown')

    df['bedrooms_per_room'] = df['bedrooms'] / df['total_rooms']
    df['area_per_room'] = df['surface_area'] / df['total_rooms']
    df['bedrooms_area_interaction'] = df['bedrooms'] * df['surface_area']
    df['area_times_bedrooms'] = df['surface_area'] * df['bedrooms']

    lower = df['detrended_price'].quantile(0.01)
    upper = df['detrended_price'].quantile(0.99)
    df['detrended_price'] = df['detrended_price'].clip(lower, upper)

    # Use training target encoding
    df['neighborhood_te'] = df['neighborhood'].map(neighborhood_means).fillna(df['neighborhood'].map(neighborhood_means).mean())

    # Apply clustering from training
    df['neighborhood_cluster'] = kmeans.predict(df[['neighborhood_te']])

    df = pd.get_dummies(df, 
                        columns=['listing_type_clean', 'city', 'energy_label', 'neighborhood_cluster'], 
                        drop_first=True)
    df = df.drop(columns=['neighborhood','listing_type'])
    
    return df

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
    print("MEAN VAL:",mean_val)
    print("detrend price:", listings['detrended_price'])

    y = listings['detrended_price'] 

    X_train, X_test, y_train, y_test = train_test_split(listings, y, test_size=0.2, random_state=42)

    X_train, neighborhood_means, kmeans  = transform_train(X_train)
    X_test = transform_test(X_test, neighborhood_means, kmeans)
    
    X_train = X_train.drop(columns=['detrended_price','trend_price','last_asking_price', 'sell_date'])
    X_test = X_test.drop(columns=['detrended_price', 'trend_price', 'last_asking_price'])

    # ensure train and test have the same columns
    X_train, X_test = X_train.align(X_test, join='left', axis=1, fill_value=0)

    dummy_point = X_test.iloc[0:1]
    print(dummy_point.T)
    dummy_point = X_train.iloc[0:1]


    print(dummy_point.T)


    # Define quantiles you want to predict
    quantiles = np.linspace(0.05,0.95,24)
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
    for i in range(1,10):
        dummy_point = X_test.iloc[i-1:i]

        print(i, dummy_point.T)

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

        p10 = np.percentile(samples, 10)
        p90 = np.percentile(samples, 90)
        mass_25_75 = kde.integrate_box_1d(p25, p75)
        print(f"Mass between p25 and p75 under KDE: {mass_25_75:.3f}")

        # Plot PDF
        plt.figure(figsize=(8,5))
        plt.plot(x, pdf, label='Verwachte prijsverdeling', color='blue')
        plt.fill_between(x, pdf, where=(x >= p25) & (x <= p75), color='orange', alpha=0.3, label='Realistische prijsklasse (25%-75%)')
        plt.fill_between(x, pdf, where=(x >= p10) & (x <= p90), color='orange', alpha=0.3, label='10%-90%')
        plt.xlabel('Voorspelde prijs')
        plt.ylabel('Dichtheid')
        plt.title('Verwachte prijsverdeling')
        plt.grid(True)
        plt.legend()
        plt.show()
