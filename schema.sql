CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS live_traffic (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(50) NOT NULL UNIQUE,
    category VARCHAR(20) NOT NULL CHECK (category IN ('flight', 'vessel')),
    location GEOMETRY(Point, 4326),
    velocity FLOAT,
    heading INTEGER CHECK (heading >= 0 AND heading <= 359),
    altitude FLOAT,
    callsign VARCHAR(20),
    origin_country VARCHAR(100),
    last_update TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS position_history (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(50) NOT NULL,
    category VARCHAR(20) NOT NULL,
    location GEOMETRY(Point, 4326),
    velocity FLOAT,
    heading INTEGER,
    altitude FLOAT,
    callsign VARCHAR(20),
    origin_country VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_traffic_category ON live_traffic(category);
CREATE INDEX IF NOT EXISTS idx_traffic_identifier ON live_traffic(identifier);
CREATE INDEX IF NOT EXISTS idx_traffic_location ON live_traffic USING GIST(location);
CREATE INDEX IF NOT EXISTS idx_traffic_last_update ON live_traffic(last_update);

CREATE INDEX IF NOT EXISTS idx_history_identifier ON position_history(identifier);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON position_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_identifier_timestamp ON position_history(identifier, timestamp);
