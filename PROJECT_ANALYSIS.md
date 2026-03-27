# Global Nomad Tracker - Project Analysis

## Overview
Real-time tracking dashboard for global flights (ADS-B via OpenSky) and maritime vessels. Built with Python/FastAPI backend, PostgreSQL+PostGIS database, and Leaflet.js frontend.

## Project Structure
```
├── main.py              # FastAPI backend (286 lines)
├── ingestor.py          # Data ingestion script (210 lines)
├── historical_ingestor.py  # Historical data processor
├── schema.sql           # Database schema (PostGIS tables)
├── index.html           # Leaflet.js map dashboard
├── requirements.txt     # Python dependencies
├── docker-compose.yml   # Docker orchestration
├── .env / .env.example  # Environment configuration
├── Dockerfile.api       # API container definition
└── ingestor.Dockerfile  # Ingestor container definition
```

## Tech Stack
- **Backend**: FastAPI 0.109.0, Uvicorn, psycopg2
- **Database**: PostgreSQL with PostGIS
- **Frontend**: HTML5, Tailwind CSS, Leaflet.js
- **APIs**: OpenSky Network (flights), Datalastic (vessels - disabled)

## Database Schema
- **live_traffic**: Real-time positions with PostGIS geometry
- **position_history**: Historical track data

## API Endpoints (main.py:39-280)
| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/traffic` | GeoJSON FeatureCollection with filters |
| `GET /api/v1/path/{id}` | Historical path for flight |
| `GET /api/v1/flights` | List available flights |
| `GET /api/v1/time-range` | Data time range |
| `GET /api/v1/stats` | Traffic statistics |
| `GET /health` | Health check |

## Ingestion (ingestor.py)
- OAuth2 authentication with OpenSky
- Fetches all flight states every 60 seconds (configurable)
- UPSERT to live_traffic + INSERT to position_history

## Configuration (.env)
```
OPENSKY_CLIENT_ID, OPENSKY_CLIENT_SECRET  # OpenSky OAuth2
DATALASTIC_KEY                              # Vessel API (unused)
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
API_PORT, INGESTION_INTERVAL
```

## Key Files for Context
- `main.py:29-36` - DB connection config
- `main.py:39-110` - Traffic API endpoint
- `ingestor.py:44-69` - OpenSky OAuth
- `ingestor.py:76-117` - Flight fetching
- `schema.sql:1-36` - PostGIS schema
