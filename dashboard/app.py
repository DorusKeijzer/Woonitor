import streamlit as st
import psycopg
import pandas as pd
from dotenv import load_dotenv
import os
import plotly.express as px

load_dotenv()

@st.cache_data(ttl=600)
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
            listing_type,
            sell_date,
            neighborhood,
            offer_since,
            sell_duration,
            city,
            energy_label
        FROM listings
        WHERE last_asking_price IS NOT NULL
          AND surface_area IS NOT NULL
          AND sell_duration IS NOT NULL
          AND sell_date IS NOT NULL
          AND offer_since IS NOT NULL
          AND city IS NOT NULL
          AND energy_label IS NOT NULL
          AND city IN ('Amsterdam', 'Rotterdam', 'Den', 'Groningen', 'Tilburg', 'Eindhoven', 'Utrecht')
        LIMIT 100000;
    """
    df = pd.read_sql(query, conn)
    conn.close()

    # Convert times & durations
    df['sell_duration_seconds'] = df['sell_duration'].apply(lambda x: x.total_seconds())
    df['sell_duration_days'] = df['sell_duration_seconds'] / (60 * 60 * 24)
    df['offer_since'] = pd.to_datetime(df['offer_since'])
    df['sell_date'] = pd.to_datetime(df['sell_date'])

    # Month grouping
    df['sell_month'] = df['sell_date'].dt.to_period('M').dt.to_timestamp()
    return df

df = get_listings()

# Sidebar city selector
st.sidebar.title("Selecteer Stad")
city_selected = st.sidebar.selectbox("Kies een stad:", ["Alle", "Tilburg", "Eindhoven", "Utrecht", "Den", "Amsterdam", "Groningen", "Rotterdam"])

if city_selected != "Alle":
    df_filtered = df[df['city'].str.lower() == city_selected.lower()]
else:
    df_filtered = df

st.title("Woonitor")

# 1. Price trends over time
if city_selected == "Alle":
    price_trends = df.groupby(['sell_month', 'city'])['last_asking_price'].mean().reset_index()
    fig1 = px.line(price_trends, x='sell_month', y='last_asking_price', color='city',
                   title='Gemiddelde Vraagprijs door de Tijd')
else:
    price_trends = df_filtered.groupby('sell_month')['last_asking_price'].mean().reset_index()
    fig1 = px.line(price_trends, x='sell_month', y='last_asking_price',
                   title='Gemiddelde Vraagprijs over tijd')

fig1.update_yaxes(range=[0, price_trends['last_asking_price'].max() * 1.1])
fig1.update_layout(xaxis_title="Verkoopmaand", yaxis_title="Gemiddelde Vraagprijs (€)")
st.plotly_chart(fig1, use_container_width=True)

# sell time over time
if city_selected == "Alle":
    sell_duration_trends = df.groupby(['sell_month', 'city'])['sell_duration_days'].mean().reset_index()
    fig_sell_duration = px.line(sell_duration_trends, x='sell_month', y='sell_duration_days', color='city',
                               title='Gemiddelde Verkooptijd over tijd (Dagen)')
else:
    sell_duration_trends = df_filtered.groupby('sell_month')['sell_duration_days'].mean().reset_index()
    fig_sell_duration = px.line(sell_duration_trends, x='sell_month', y='sell_duration_days',
                               title='Gemiddelde Verkooptijd over tijd (Dagen)')

fig_sell_duration.update_yaxes(range=[0, sell_duration_trends['sell_duration_days'].max() * 1.1])
fig_sell_duration.update_layout(xaxis_title="Verkoopmaand", yaxis_title="Gemiddelde Verkooptijd (Dagen)")
st.plotly_chart(fig_sell_duration, use_container_width=True)


# 2. Average price per city
city_prices = df.groupby('city')['last_asking_price'].mean().sort_values(ascending=False).reset_index()
fig_city = px.bar(city_prices, x='city', y='last_asking_price',
                  title='Gemiddelde Vraagprijs per Stad',
                  labels={'city': 'Stad', 'last_asking_price': 'Gemiddelde Vraagprijs (€)'},
                  color='city')
fig_city.update_layout(xaxis_title="Stad", yaxis_title="Gemiddelde Vraagprijs (€)")
st.plotly_chart(fig_city, use_container_width=True)

# 3. Price vs surface area
fig2 = px.scatter(df_filtered, x='surface_area', y='last_asking_price', color='city',
                  title='Vraagprijs vs woonoppervlak',
                  labels={'surface_area': 'Oppervlakte (m²)', 'last_asking_price': 'Vraagprijs (€)'},
                  hover_data=['listing_type', 'bedrooms'])
fig2.update_layout(xaxis_title="Oppervlakte (m²)", yaxis_title="Vraagprijs (€)")
st.plotly_chart(fig2, use_container_width=True)

# 4. Sell duration histogram
fig4 = px.histogram(df_filtered, x='sell_duration_days', nbins=200, color='city', barmode='stack',
                    title='Verdeling van verkooptijd (dagen)',
                    labels={'sell_duration_days': 'Aantal Dagen'})
fig4.update_layout(xaxis_title="Aantal Dagen op de Markt", yaxis_title="Aantal Woningen", bargap=0.1)
st.plotly_chart(fig4, use_container_width=True)

# 5. Energy labels
energy_order = ['a++++', 'a+++', 'a++', 'a+', 'a', 'b', 'c', 'd', 'e', 'f', 'g']
df_filtered['energy_label'] = pd.Categorical(df_filtered['energy_label'].str.lower(),
                                    categories=[e.lower() for e in energy_order], ordered=True)
energy_city = df_filtered.groupby(['energy_label', 'city']).size().reset_index(name='Aantal')

fig5 = px.bar(energy_city, x='energy_label', y='Aantal', color='city',
              category_orders={'energy_label': [e.lower() for e in energy_order]},
              title='Verdeling van energielabels',
              labels={'energy_label': 'Energielabel', 'Aantal': 'Aantal Woningen', 'city': 'Stad'},
              barmode='stack')
fig5.update_layout(xaxis_title="Energielabel", yaxis_title="Aantal Woningen")
st.plotly_chart(fig5, use_container_width=True)

# 6. Price vs days on market
st.header("Vraagprijs versus Aantal Dagen op de Markt")
fig_days_price = px.scatter(df_filtered, x='sell_duration_days', y='last_asking_price',
                            color='city',
                            title='Vraagprijs versus aantal dagen op de markt',
                            labels={'sell_duration_days': 'Aantal Dagen op de Markt',
                                    'last_asking_price': 'Vraagprijs (€)'},
                            hover_data=['listing_type', 'bedrooms'])
fig_days_price.update_layout(xaxis_title="Aantal Dagen op de Markt", yaxis_title="Vraagprijs (€)")
st.plotly_chart(fig_days_price, use_container_width=True)


# 7. Monthly listings over time
if city_selected == "Alle":
    maandelijks_aanbod = df.groupby(['sell_month', 'city']).size().reset_index(name='Aantal Woningen')
    fig_aanbod = px.bar(maandelijks_aanbod, x='sell_month', y='Aantal Woningen', color='city',
                        title='Maandelijks verkocht per stad',
                        labels={'sell_month': 'Verkoopmaand', 'Aantal Woningen': 'Aantal Listings', 'city': 'Stad'},
                        barmode='stack')
else:
    maandelijks_aanbod = df_filtered.groupby('sell_month').size().reset_index(name='Aantal Woningen')
    fig_aanbod = px.bar(maandelijks_aanbod, x='sell_month', y='Aantal Woningen',
                        title=f'Maandelijks verkocht in {city_selected}',
                        labels={'sell_month': 'Verkoopmaand', 'Aantal Woningen': 'Aantal Listings'})

fig_aanbod.update_layout(xaxis_title="Verkoopmaand", yaxis_title="Aantal Listings")
st.plotly_chart(fig_aanbod, use_container_width=True)


# # 2. Average price per city
# city_prices = df.groupby('city')['last_asking_price'].mean().sort_values(ascending=False).reset_index()
# fig_city = px.bar(city_prices, x='city', y='last_asking_price',
#                   title='Gemiddelde Vraagprijs per Stad',
#                   labels={'city': 'Stad', 'last_asking_price': 'Gemiddelde Vraagprijs (€)'},
#                   color='city')
# fig_city.update_layout(xaxis_title="Stad", yaxis_title="Gemiddelde Vraagprijs (€)")
# st.plotly_chart(fig_city, use_container_width=True)
#

if city_selected != "Alle":
    df_filtered['listing_type_clean'] = df['listing_type'].str.split(r'[\(,]').str[0].str.strip()

    # Now group by the cleaned listing type
    listing_type_prices = df_filtered.groupby("listing_type_clean")['last_asking_price'] \
                            .mean() \
                            .sort_values(ascending=False) \
                            .reset_index()

    fig_listing_type = px.bar(listing_type_prices, x="listing_type_clean", y='last_asking_price',
                              title=f'Gemiddelde vraagrprijs per woningtype in {city_selected}',
                              labels={'listing_type':'woningtype', 'last_asking_price':'Gemiddelde vraagrprijs ()' })
    fig_listing_type.update_layout(xaxis_title="Woningtype", yaxis_title="Gemiddelde laatste vraagprijs")
                                    
    st.plotly_chart(fig_listing_type, use_container_width=True)



if city_selected != "Alle":
    # Now group by the cleaned listing type
    neighborhood_prices = df_filtered.groupby("neighborhood")['last_asking_price'] \
                            .mean() \
                            .sort_values(ascending=False) \
                            .reset_index()

    fig_listing_type = px.bar(neighborhood_prices, x="neighborhood", y='last_asking_price',
                              title=f'Gemiddelde vraagrprijs per buurt in {city_selected}',
                              labels={'neighborhood':'buurt', 'last_asking_price':'Gemiddelde vraagrprijs ()' })
    fig_listing_type.update_layout(xaxis_title="Buurt", yaxis_title="Gemiddelde laatste vraagprijs")
                                    
    st.plotly_chart(fig_listing_type, use_container_width=True)
