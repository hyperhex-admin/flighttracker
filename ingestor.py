import os
import json
import logging
import time
from datetime import datetime
from typing import Optional

import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class TrafficIngestor:
    def __init__(self):
        self.opensky_client_id = os.getenv('OPENSKY_CLIENT_ID')
        self.opensky_client_secret = os.getenv('OPENSKY_CLIENT_SECRET')
        self.datalastic_key = os.getenv('DATALASTIC_KEY')
        
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'dbname': os.getenv('DB_NAME', 'traffic'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        
        self.opensky_token: Optional[str] = None
        self.opensky_token_expiry: Optional[float] = None
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json'})
    
    def connect_db(self):
        return psycopg2.connect(**self.db_config)
    
    def authenticate_opensky(self) -> bool:
        if not self.opensky_client_id or not self.opensky_client_secret:
            logger.warning("OpenSky OAuth2 credentials not configured, skipping flight data")
            return False
        
        try:
            token_url = 'https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token'
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.opensky_client_id,
                'client_secret': self.opensky_client_secret
            }
            response = self.session.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                self.opensky_token = token_data.get('access_token')
                self.opensky_token_expiry = time.time() + token_data.get('expires_in', 3600)
                self.session.headers.update({'Authorization': f'Bearer {self.opensky_token}'})
                logger.info("OpenSky OAuth2 authentication successful")
                return True
            else:
                logger.error(f"OpenSky auth failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"OpenSky auth error: {e}")
            return False
    
    def ensure_opensky_token(self) -> bool:
        if self.opensky_token and self.opensky_token_expiry and time.time() < self.opensky_token_expiry - 60:
            return True
        return self.authenticate_opensky()
    
    def fetch_flights(self) -> list:
        if not self.ensure_opensky_token():
            logger.warning("No OpenSky token, skipping flights")
            return []
        
        try:
            url = 'https://opensky-network.org/api/states/all'
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                states = data.get('states', [])
                flights = []
                for state in states:
                    icao24 = state[0]
                    callsign = state[1] or ''
                    origin_country = state[2] or ''
                    longitude = state[5]
                    latitude = state[6]
                    velocity = state[7]
                    heading = state[10]
                    altitude = state[13]
                    
                    if longitude and latitude:
                        flights.append({
                            'identifier': icao24.upper(),
                            'category': 'flight',
                            'longitude': longitude,
                            'latitude': latitude,
                            'velocity': velocity or 0,
                            'heading': int(heading) % 360 if heading is not None else 0,
                            'altitude': altitude or 0,
                            'callsign': callsign.strip(),
                            'origin_country': origin_country
                        })
                logger.info(f"Fetched {len(flights)} flights")
                return flights
            else:
                logger.error(f"Failed to fetch flights: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching flights: {e}")
            return []
    
    def fetch_vessels(self) -> list:
        logger.info("Vessel fetching disabled")
        return []
    
    def upsert_traffic(self, items: list):
        if not items:
            return
        
        try:
            conn = self.connect_db()
            cur = conn.cursor()
            
            query = """
                INSERT INTO live_traffic (identifier, category, location, velocity, heading, altitude, callsign, origin_country, last_update)
                VALUES %s
                ON CONFLICT (identifier) DO UPDATE SET
                    category = EXCLUDED.category,
                    location = EXCLUDED.location,
                    velocity = EXCLUDED.velocity,
                    heading = EXCLUDED.heading,
                    altitude = EXCLUDED.altitude,
                    callsign = EXCLUDED.callsign,
                    origin_country = EXCLUDED.origin_country,
                    last_update = EXCLUDED.last_update
            """
            
            values = [
                (
                    item['identifier'],
                    item['category'],
                    f"SRID=4326;POINT({item['longitude']} {item['latitude']})",
                    item['velocity'],
                    item['heading'],
                    item['altitude'],
                    item.get('callsign', ''),
                    item.get('origin_country', ''),
                    datetime.utcnow()
                )
                for item in items
            ]
            
            execute_values(cur, query, values)
            
            history_query = """
                INSERT INTO position_history (identifier, category, location, velocity, heading, altitude, callsign, origin_country, timestamp)
                VALUES %s
            """
            
            history_values = [
                (
                    item['identifier'],
                    item['category'],
                    f"SRID=4326;POINT({item['longitude']} {item['latitude']})",
                    item['velocity'],
                    item['heading'],
                    item['altitude'],
                    item.get('callsign', ''),
                    item.get('origin_country', ''),
                    datetime.utcnow()
                )
                for item in items
            ]
            
            execute_values(cur, history_query, history_values)
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Upserted {len(items)} traffic items and stored history")
        except Exception as e:
            logger.error(f"Database error: {e}")
    
    def run(self, interval: int = 60):
        logger.info("Starting traffic ingestor...")
        
        self.authenticate_opensky()
        
        while True:
            flights = self.fetch_flights()
            
            if flights:
                self.upsert_traffic(flights)
            
            logger.info(f"Sleeping for {interval} seconds...")
            time.sleep(interval)


if __name__ == '__main__':
    interval = int(os.getenv('INGESTION_INTERVAL', '60'))
    ingestor = TrafficIngestor()
    ingestor.run(interval)
