# Global Nomad Tracker - Project Analysis

## Overview
Real-time tracking dashboard for global flights (ADS-B via OpenSky) and maritime vessels. Built with Python/FastAPI backend, PostgreSQL+PostGIS database, and Leaflet.js frontend.

## Project Structure
```
├── main.py                   # FastAPI backend (286 lines)
├── ingestor.py               # Data ingestion script (210 lines)
├── historical_ingestor.py    # Historical data processor (10452 lines)
├── schema.sql                # Database schema (PostGIS tables)
├── index.html                # Leaflet.js map dashboard (modern UI)
├── requirements.txt          # Python dependencies
├── docker-compose.yml         # Docker orchestration
├── .env / .env.example       # Environment configuration
├── Dockerfile.api            # API container definition
├── ingestor.Dockerfile       # Ingestor container definition
└── PROJECT_ANALYSIS.md       # This file
```

## Tech Stack
- **Backend**: FastAPI 0.109.0, Uvicorn, psycopg2
- **Database**: PostgreSQL with PostGIS
- **Frontend**: HTML5, Tailwind CSS, Leaflet.js
- **APIs**: OpenSky Network (flights), Datalastic (vessels - disabled)

## Database Schema (schema.sql)
```sql
-- live_traffic: Real-time positions with PostGIS geometry
-- position_history: Historical track data
-- Indexes on category, identifier, location, timestamp
```

## API Endpoints (main.py)
| Endpoint | Line | Description |
|----------|------|-------------|
| `GET /` | 17-19 | Serve index.html |
| `GET /api/v1/traffic` | 39-110 | GeoJSON with filters (category, country, identifier, limit) |
| `GET /api/v1/path/{id}` | 113-179 | Historical path with time range |
| `GET /api/v1/flights` | 182-226 | List available flights |
| `GET /api/v1/time-range` | 229-247 | Data time range |
| `GET /api/v1/stats` | 250-275 | Traffic statistics |
| `GET /health` | 278-280 | Health check |

## Ingestion (ingestor.py)
- `TrafficIngestor` class (line 22)
- OAuth2 authentication (line 44-69)
- Fetches all flight states every 60s (configurable)
- UPSERT to live_traffic + INSERT to position_history
- Vessel fetching disabled (line 119-121)

## Configuration (.env)
```
OPensky_*        # OpenSky OAuth2 credentials
DATALASTIC_KEY   # Vessel API (unused)
DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
API_PORT=8000
INGESTION_INTERVAL=60
```

## Frontend (index.html)
### UI Features (Last Updated: v2 - Modern UI)
- **Glassmorphism design** - translucent panels with backdrop blur
- **Floating header** - compact stats with gradient icons, live status
- **Bottom-left control panel** - filters for country, flight ID, history, date
- **Dark theme popups** - grid layout showing speed, altitude, heading
- **OpenStreetMap tiles** - line 178
- **Flight path playback** - play/stop animation with time display
- **Responsive** - works on desktop

### Key JS Functions
| Function | Line | Description |
|----------|------|-------------|
| `fetchTraffic()` | 194-207 | Fetch traffic with filters |
| `fetchFlightPath()` | 209-216 | Get historical path |
| `updateMarkers()` | 263-310 | Render/update map markers |
| `showPath()` | 335-365 | Show flight path polyline |
| `togglePlayback()` | 367-382 | Play/stop path animation |
| `refreshMap()` | 438-443 | Manual refresh + 30s auto-refresh |

### Markers
- **Plane icon** - blue SVG, line 182-188
- **Ship icon** - emerald SVG, line 190-196
- Rotation based on heading property
- Glow effect via CSS filter

## Change Log
- **v3 (2026-03-27)**: Fixed popup sizing - replaced Tailwind arbitrary values with custom CSS, fixed button onclick via event delegation
- **v2 (2026-03-27)**: Modernized UI with glassmorphism, floating header, dark popups
- **v1 (2026-03-27)**: Initial implementation

## Key Code References
- DB connection: `main.py:29-36`
- Traffic API: `main.py:39-110`
- OpenSky OAuth: `ingestor.py:44-69`
- Flight fetch: `ingestor.py:76-117`
- Schema: `schema.sql:1-36`
- Map init: `index.html:166-179`
- Markers: `index.html:182-196`
- Popup: `index.html:218-249`
