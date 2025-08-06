import streamlit as st
import psycopg2

def get_listings():
    conn = psycopg2.connect(
        host="localhost",  # or your Docker network host
        port=5432,
        database="your_db_name",
        user="postgres",
        password="your_password"
    )
    cur = conn.cursor()
    cur.execute("SELECT funda_id, title, last_asking_price FROM listings LIMIT 20;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

st.title("Woonitor")

listings = get_listings()

for funda_id, title, price in listings:
    st.write(f"ID: {funda_id}, Title: {title}, Price: €{price}")

