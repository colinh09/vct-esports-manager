import os
import json
import logging
import time
import signal
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from math import sqrt
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set up logging
logging.basicConfig(filename='player_map_performance.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

PROCESSED_PLAYERS_FILE = 'processed_players.json'
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 5  # seconds

def get_db_connection():
    for attempt in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(os.getenv('RDS_DATABASE_URL'))
            return conn
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                retry_delay = INITIAL_RETRY_DELAY * (2 ** attempt)
                logging.warning(f"Connection attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logging.error(f"Failed to connect to database after {MAX_RETRIES} attempts: {e}")
                raise

def create_player_map_performance_table(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS player_map_performance (
                player_id VARCHAR,
                map VARCHAR NOT NULL,
                games_played INT,
                total_kills INT,
                total_deaths INT,
                total_assists INT,
                average_kda NUMERIC(5,2),
                site_a_events INT,
                site_b_events INT,
                site_c_events INT,
                map_type VARCHAR(3),
                PRIMARY KEY (player_id, map)
            )
        """)
    conn.commit()
    logging.info("player_map_performance table created or updated")

def load_map_data(file_path='event_locations/maps.json'):
    with open(file_path, 'r') as f:
        return json.load(f)

def get_map_info(map_data, map_url):
    for map_info in map_data:
        if map_info['mapUrl'] == map_url:
            return map_info
    return None

def calculate_distance(x1, y1, x2, y2):
    return sqrt((x2 - x1)**2 + (y2 - y1)**2)

def get_nearest_site(x, y, site_locations):
    distances = {site: calculate_distance(x, y, loc['x'], loc['y']) for site, loc in site_locations.items()}
    return min(distances, key=distances.get)

def process_player_map_performance(conn, player_id, map_url, map_data):
    map_info = get_map_info(map_data, map_url)
    if not map_info:
        logging.error(f"Map info not found for {map_url}")
        return None

    with conn.cursor() as cur:
        # First, check if the player has any games on this map
        cur.execute("""
            SELECT COUNT(DISTINCT gm.platform_game_id) as games_played
            FROM game_mapping gm
            JOIN player_mapping pm ON gm.platform_game_id = pm.platform_game_id
            WHERE gm.map = %s AND pm.player_id = %s
        """, (map_url, player_id))
        
        result = cur.fetchone()
        games_played = result[0] if result else 0

        site_locations = {}
        for callout in map_info['callouts']:
            if callout['superRegionName'] in ['A', 'B', 'C'] and callout['regionName'] == 'Site':
                site_locations[callout['superRegionName']] = callout['location']

        map_type = 'ABC' if 'C' in site_locations else 'AB'

        if games_played == 0:
            logging.info(f"No games played for player {player_id} on map {map_url}")
            return {
                'player_id': player_id,
                'map': map_url,
                'games_played': 0,
                'total_kills': 0,
                'total_deaths': 0,
                'total_assists': 0,
                'average_kda': 0,
                'site_a_events': 0,
                'site_b_events': 0,
                'site_c_events': 0,
                'map_type': map_type
            }

        # If games_played > 0, proceed with the rest of the processing
        # Get kills and deaths
        cur.execute("""
            SELECT killer_x, killer_y, deceased_x, deceased_y, true_killer_id, true_deceased_id
            FROM player_died
            WHERE (true_killer_id = %s OR true_deceased_id = %s) AND platform_game_id IN (
                SELECT platform_game_id FROM game_mapping WHERE map = %s
            )
        """, (player_id, player_id, map_url))
        
        events = cur.fetchall()

        site_counts = {'A': 0, 'B': 0, 'C': 0}

        for killer_x, killer_y, deceased_x, deceased_y, true_killer_id, true_deceased_id in events:
            if true_killer_id == player_id and killer_x is not None and killer_y is not None:
                site = get_nearest_site(killer_x, killer_y, site_locations)
                site_counts[site] += 1
            elif true_deceased_id == player_id and deceased_x is not None and deceased_y is not None:
                site = get_nearest_site(deceased_x, deceased_y, site_locations)
                site_counts[site] += 1

        # Get other performance data
        cur.execute("""
            SELECT 
                SUM(pm.kills) as total_kills,
                SUM(pm.deaths) as total_deaths,
                SUM(pm.assists) as total_assists
            FROM 
                game_mapping gm
            JOIN 
                player_mapping pm ON gm.platform_game_id = pm.platform_game_id
            WHERE 
                gm.map = %s AND pm.player_id = %s
        """, (map_url, player_id))
        
        result = cur.fetchone()
        if result:
            total_kills, total_deaths, total_assists = result
            total_kills = total_kills or 0
            total_deaths = total_deaths or 0
            total_assists = total_assists or 0
            
            average_kda = (total_kills + total_assists) / total_deaths if total_deaths > 0 else 0

            return {
                'player_id': player_id,
                'map': map_url,
                'games_played': games_played,
                'total_kills': total_kills,
                'total_deaths': total_deaths,
                'total_assists': total_assists,
                'average_kda': round(average_kda, 2),
                'site_a_events': site_counts['A'],
                'site_b_events': site_counts['B'],
                'site_c_events': site_counts['C'],
                'map_type': map_type
            }
        else:
            logging.info(f"No performance data for player {player_id} on map {map_url}")
            return None

def batch_update_player_map_performance(conn, data):
    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO player_map_performance 
            (player_id, map, games_played, total_kills, total_deaths, total_assists, average_kda, 
             site_a_events, site_b_events, site_c_events, map_type)
            VALUES (%(player_id)s, %(map)s, %(games_played)s, %(total_kills)s, %(total_deaths)s, 
                    %(total_assists)s, %(average_kda)s, %(site_a_events)s, %(site_b_events)s, 
                    %(site_c_events)s, %(map_type)s)
            ON CONFLICT (player_id, map) DO UPDATE
            SET 
                games_played = EXCLUDED.games_played,
                total_kills = EXCLUDED.total_kills,
                total_deaths = EXCLUDED.total_deaths,
                total_assists = EXCLUDED.total_assists,
                average_kda = EXCLUDED.average_kda,
                site_a_events = EXCLUDED.site_a_events,
                site_b_events = EXCLUDED.site_b_events,
                site_c_events = EXCLUDED.site_c_events,
                map_type = EXCLUDED.map_type
        """, data)
    conn.commit()
    logging.info(f"Batch update completed for {len(data)} player-map combinations")

def process_player(player_id, map_urls, map_data, conn):
    results = []
    with ThreadPoolExecutor(max_workers=len(map_urls)) as executor:
        future_to_map = {executor.submit(process_player_map_performance, conn, player_id, map_url, map_data): map_url for map_url in map_urls}
        for future in as_completed(future_to_map):
            map_url = future_to_map[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as exc:
                logging.error(f"Error processing player {player_id} on map {map_url}: {exc}")
    return results

def load_processed_players():
    if os.path.exists(PROCESSED_PLAYERS_FILE):
        with open(PROCESSED_PLAYERS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_processed_players(processed_players):
    with open(PROCESSED_PLAYERS_FILE, 'w') as f:
        json.dump(list(processed_players), f)

def graceful_shutdown(signum, frame):
    logging.info("Received shutdown signal. Closing connections and exiting...")
    if 'conn' in globals() and conn:
        conn.close()
    sys.exit(0)

def main_loop():
    global conn  # Make conn global so we can close it in graceful_shutdown
    while True:
        try:
            conn = get_db_connection()
            create_player_map_performance_table(conn)
            
            map_data = load_map_data()
            map_urls = [
                "/Game/Maps/Ascent/Ascent", "/Game/Maps/Bonsai/Bonsai", "/Game/Maps/Canyon/Canyon",
                "/Game/Maps/Duality/Duality", "/Game/Maps/Foxtrot/Foxtrot", "/Game/Maps/Infinity/Infinity",
                "/Game/Maps/Jam/Jam", "/Game/Maps/Juliett/Juliett", "/Game/Maps/Pitt/Pitt",
                "/Game/Maps/Port/Port", "/Game/Maps/Triad/Triad"
            ]

            processed_players = load_processed_players()
            logging.info(f"Loaded {len(processed_players)} previously processed players")

            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT player_id FROM players")
                all_players = [row[0] for row in cur.fetchall()]

            players_to_process = [player for player in all_players if player not in processed_players]
            logging.info(f"Found {len(players_to_process)} players to process")

            for player_id in players_to_process:
                player_results = process_player(player_id, map_urls, map_data, conn)
                batch_update_player_map_performance(conn, player_results)
                processed_players.add(player_id)
                save_processed_players(processed_players)
                logging.info(f"Processed and saved data for player {player_id}")

            logging.info("Player map performance aggregation completed successfully")

        except Exception as e:
            logging.error(f"An error occurred in the main loop: {e}")
            logging.info("Waiting for 5 minutes before retrying...")
            time.sleep(300)  # Wait for 5 minutes before retrying
        finally:
            if conn:
                conn.close()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    logging.info("Starting continuous player map performance aggregation")
    main_loop()