import os
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from psycopg2 import connect
import json

app = FastAPI(title="Global Nomad Tracker API", version="1.0.0")

if os.path.exists("index.html"):
    app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_index():
    return FileResponse("index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_connection():
    return connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'traffic'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )


@app.get("/api/v1/traffic")
def get_traffic(
    category: Optional[str] = Query(None, description="Filter by category: flight or vessel"),
    country: Optional[str] = Query(None, description="Filter by origin country"),
    identifier: Optional[str] = Query(None, description="Filter by identifier"),
    limit: int = Query(1000, ge=1, le=5000, description="Max results")
):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            identifier,
            category,
            ST_AsGeoJSON(location) as geojson,
            velocity,
            heading,
            altitude,
            callsign,
            origin_country,
            last_update
        FROM live_traffic
        WHERE 1=1
    """
    
    params = []
    if category:
        query += " AND category = %s"
        params.append(category)
    if country:
        query += " AND origin_country ILIKE %s"
        params.append(f"%{country}%")
    if identifier:
        query += " AND identifier = %s"
        params.append(identifier.upper())
    
    query += " ORDER BY last_update DESC LIMIT %s"
    params.append(limit)
    
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    features = []
    for row in rows:
        identifier, category, geojson, velocity, heading, altitude, callsign, origin_country, last_update = row
        
        geometry = json.loads(geojson) if geojson else None
        
        properties = {
            "identifier": identifier,
            "category": category,
            "velocity": velocity,
            "heading": heading,
            "altitude": altitude,
            "callsign": callsign,
            "origin_country": origin_country,
            "last_update": last_update.isoformat() if last_update else None
        }
        
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        })
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features)
    }


@app.get("/api/v1/path/{flight_id}")
def get_flight_path(
    flight_id: str,
    minutes: int = Query(60, ge=1, le=1440, description="History in minutes")
):
    conn = get_db_connection()
    cur = conn.cursor()
    
    query = """
        SELECT 
            identifier,
            category,
            ST_AsGeoJSON(location) as geojson,
            velocity,
            heading,
            altitude,
            callsign,
            origin_country,
            timestamp
        FROM position_history
        WHERE identifier = %s
        AND timestamp > NOW() - INTERVAL '%s minutes'
        ORDER BY timestamp ASC
    """
    
    cur.execute(query, (flight_id.upper(), minutes))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        return {"type": "FeatureCollection", "features": [], "count": 0}
    
    features = []
    timestamps = []
    for row in rows:
        identifier, category, geojson, velocity, heading, altitude, callsign, origin_country, timestamp = row
        
        geometry = json.loads(geojson) if geojson else None
        
        properties = {
            "identifier": identifier,
            "category": category,
            "velocity": velocity,
            "heading": heading,
            "altitude": altitude,
            "callsign": callsign,
            "origin_country": origin_country,
            "timestamp": timestamp.isoformat() if timestamp else None
        }
        
        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": properties
        })
        timestamps.append(timestamp)
    
    return {
        "type": "FeatureCollection",
        "features": features,
        "count": len(features),
        "time_range": {
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None
        }
    }


@app.get("/api/v1/time-range")
def get_time_range():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT MIN(timestamp), MAX(timestamp), COUNT(DISTINCT identifier)
        FROM position_history
        WHERE timestamp > NOW() - INTERVAL '24 hours'
    """)
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    return {
        "earliest": row[0].isoformat() if row[0] else None,
        "latest": row[1].isoformat() if row[1] else None,
        "unique_flights": row[2] or 0
    }


@app.get("/api/v1/stats")
def get_stats():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            category,
            COUNT(*) as count,
            AVG(velocity) as avg_velocity
        FROM live_traffic
        GROUP BY category
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    stats = {}
    for row in rows:
        category, count, avg_velocity = row
        stats[category] = {
            "count": count,
            "avg_velocity": round(avg_velocity, 2) if avg_velocity else 0
        }
    
    return stats


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('API_PORT', '8000'))
    uvicorn.run(app, host="0.0.0.0", port=port)
