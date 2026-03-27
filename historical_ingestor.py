import os
import json
import logging
import time
from datetime import datetime, timedelta
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


class HistoricalIngestor:
    def __init__(self):
        self.opensky_client_id = os.getenv('OPENSKY_CLIENT_ID')
        self.opensky_client_secret = os.getenv('OPENSKY_CLIENT_SECRET')
        
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
            logger.error("OpenSky OAuth2 credentials not configured")
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
                logger.error(f"OpenSky auth failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"OpenSky auth error: {e}")
            return False
    
    def ensure_opensky_token(self) -> bool:
        if self.opensky_token and self.opensky_token_expiry and time.time() < self.opensky_token_expiry - 60:
            return True
        return self.authenticate_opensky()
    
    def get_flights_in_range(self, begin: int, end: int) -> list:
        if not self.ensure_opensky_token():
            return []
        
        try:
            url = 'https://opensky-network.org/api/flights/all'
            params = {
                'begin': begin,
                'end': end
            }
            response = self.session.get(url, params=params, timeout=60)
            
            if response.status_code == 200:
                flights = response.json()
                logger.info(f"Fetched {len(flights)} flights for range {begin}-{end}")
                return flights
            elif response.status_code == 404:
                logger.info(f"No flights found for range {begin}-{end}")
                return []
            else:
                logger.error(f"Failed to fetch flights: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching flights: {e}")
            return []
    
    def get_track(self, icao24: str, time: int, retries: int = 3) -> list:
        if not self.ensure_opensky_token():
            return []
        
        for attempt in range(retries):
            try:
                url = f'https://opensky-network.org/api/tracks/all'
                params = {
                    'icao24': icao24.lower(),
                    'time': time
                }
                response = self.session.get(url, params=params, timeout=30)
                
                if response.status_code == 200:
                    track_data = response.json()
                    path = track_data.get('path', [])
                    if path:
                        logger.info(f"Fetched {len(path)} track points for {icao24}")
                    return path
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 10
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    self.authenticate_opensky()
                else:
                    if attempt == retries - 1:
                        logger.error(f"Failed to fetch track: {response.status_code}")
                    return []
            except Exception as e:
                if attempt == retries - 1:
                    logger.error(f"Error fetching track: {e}")
                return []
        return []
    
    def insert_flights(self, flights: list):
        if not flights:
            return
        
        try:
            conn = self.connect_db()
            cur = conn.cursor()
            
            query = """
                INSERT INTO position_history (identifier, category, location, velocity, heading, altitude, callsign, origin_country, timestamp)
                VALUES %s
            """
            
            values = []
            for flight in flights:
                icao24 = flight.get('icao24')
                callsign = flight.get('callsign', '')
                origin_country = flight.get('originCountry', '')
                departure_time = flight.get('firstSeen', 0)
                arrival_time = flight.get('lastSeen', 0)
                departure_airport = flight.get('departureAirport', '')
                arrival_airport = flight.get('arrivalAirport', '')
                
                if icao24:
                    values.append((
                        icao24.upper(),
                        'flight',
                        None,
                        0,
                        0,
                        0,
                        callsign,
                        origin_country,
                        datetime.utcfromtimestamp(departure_time)
                    ))
            
            if values:
                execute_values(cur, query, values)
                conn.commit()
                logger.info(f"Inserted {len(values)} flight records")
            
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Database error: {e}")
    
    def insert_track_points(self, icao24: str, path: list, category: str = 'flight'):
        if not path:
            return
        
        try:
            conn = self.connect_db()
            cur = conn.cursor()
            
            query = """
                INSERT INTO position_history (identifier, category, location, velocity, heading, altitude, callsign, origin_country, timestamp)
                VALUES %s
            """
            
            values = []
            for point in path:
                timestamp = point[0]
                lat = point[1]
                lon = point[2]
                altitude = point[3]
                heading = point[4]
                
                if lat and lon:
                    values.append((
                        icao24.upper(),
                        category,
                        f"SRID=4326;POINT({lon} {lat})",
                        0,
                        int(heading) % 360 if heading else 0,
                        altitude or 0,
                        '',
                        '',
                        datetime.utcfromtimestamp(timestamp)
                    ))
            
            if values:
                execute_values(cur, query, values)
                conn.commit()
                logger.info(f"Inserted {len(values)} track points for {icao24}")
            
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Database error: {e}")
    
    def run(self, days_back: int = 7):
        logger.info(f"Starting historical data ingestor for {days_back} days...")
        
        if not self.ensure_opensky_token():
            logger.error("Cannot authenticate with OpenSky")
            return
        
        end_time = datetime.utcnow() - timedelta(days=1)
        end_timestamp = int(end_time.timestamp())
        
        for day_offset in range(days_back, 0, -1):
            day_start = end_time - timedelta(days=day_offset)
            day_end = end_time - timedelta(days=day_offset - 1)
            
            begin_ts = int(day_start.timestamp())
            end_ts = int(day_end.timestamp())
            
            logger.info(f"Fetching flights for {day_start.date()} to {day_end.date()}")
            
            flights = self.get_flights_in_range(begin_ts, end_ts)
            
            if flights:
                self.insert_flights(flights)
                
                unique_aircraft = list(set([f.get('icao24') for f in flights if f.get('icao24')]))
                logger.info(f"Found {len(unique_aircraft)} unique aircraft")
                
                unique_aircraft = list(set([f.get('icao24') for f in flights if f.get('icao24')]))
                sample_size = min(20, len(unique_aircraft))
                
                logger.info(f"Fetching tracks for {sample_size} sample aircraft")
                
                for i, icao24 in enumerate(unique_aircraft[:sample_size]):
                    mid_time = begin_ts + (end_ts - begin_ts) // 2
                    track = self.get_track(icao24, mid_time)
                    if track:
                        self.insert_track_points(icao24, track)
                    
                    if (i + 1) % 5 == 0:
                        logger.info(f"Processed {i + 1}/{sample_size} aircraft")
                        time.sleep(3)
            
            time.sleep(5)
        
        logger.info("Historical data ingestion complete")


if __name__ == '__main__':
    days = int(os.getenv('HISTORY_DAYS', '7'))
    ingestor = HistoricalIngestor()
    ingestor.run(days)
