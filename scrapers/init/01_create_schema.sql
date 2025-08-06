CREATE TABLE listings (
    id SERIAL PRIMARY KEY,
    funda_id TEXT UNIQUE NOT NULL,  -- Funda's listing ID
    title TEXT,                     -- The title of the page on funda
    last_asking_price INTEGER,      
    surface_area NUMERIC,           -- Main surface area (?)
    bedrooms INTEGER, 
    bathrooms INTEGER, 
    listing_type TEXT,              -- House, apartment, etc.
    sell_date DATE,
    offer_since DATE,               -- listed since
    sell_duration INTERVAL,         -- time between offer date and sell date
    city TEXT,  
    postcode TEXT, 
    neighborhood TEXT, 
    energy_label TEXT,
    building_year TIMESTAMP,
    scraped_at TIMESTAMP NOT NULL,
    url TEXT,
    misc_data JSONB                   -- Other data from the listing
);


-- core indices --
CREATE INDEX idx_funda_id ON listings(funda_id);
CREATE INDEX idx_scraped_at ON listings(scraped_at);
CREATE INDEX idx_sell_date ON listings(sell_date);
CREATE INDEX idx_offer_date ON listings(offer_date);

-- location indices --
CREATE INDEX idx_city ON listings(city);
CREATE INDEX idx_postcode ON listings(postcode);
CREATE INDEX idx_neighborhood ON listings(neighborhood);

-- analytics indices --
CREATE INDEX idx_listing_type ON listings(listing_type);
CREATE INDEX idx_building_year ON listings(building_year);
CREATE INDEX idx_energy_label ON listings(energy_label);


