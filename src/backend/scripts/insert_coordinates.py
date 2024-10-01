import os
import ijson
import psycopg2
import logging
from logging.handlers import RotatingFileHandler
import requests
import json
import gzip
import shutil
from io import BytesIO
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import re

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

# Thread-local storage for database connections
thread_local = threading.local()

def setup_logging(log_file_name):
    logger = logging.getLogger('game_data_processor')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file_name, maxBytes=100*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_db_connection():
    if not hasattr(thread_local, "connection") or thread_local.connection.closed:
        max_retries = 3
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                thread_local.connection = psycopg2.connect(DATABASE_URL)
                return thread_local.connection
            except Exception as e:
                logger.error(f"Error connecting to database (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return None
    return thread_local.connection

def ensure_columns_exist(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            ALTER TABLE player_died 
            ADD COLUMN IF NOT EXISTS killer_x FLOAT,
            ADD COLUMN IF NOT EXISTS killer_y FLOAT,
            ADD COLUMN IF NOT EXISTS deceased_x FLOAT,
            ADD COLUMN IF NOT EXISTS deceased_y FLOAT;
        """)
        
        cursor.execute("""
            ALTER TABLE player_assists 
            ADD COLUMN IF NOT EXISTS assister_x FLOAT,
            ADD COLUMN IF NOT EXISTS assister_y FLOAT;
        """)
        
        cursor.execute("""
            ALTER TABLE ability_used 
            ADD COLUMN IF NOT EXISTS player_x FLOAT,
            ADD COLUMN IF NOT EXISTS player_y FLOAT;
        """)
        
        connection.commit()
        logger.info("Added new columns for coordinates to event tables")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error ensuring columns exist: {e}")
    finally:
        cursor.close()

def download_and_process_game(tournament, year, platform_game_id):
    connection = get_db_connection()
    if not connection:
        return False

    try:
        directory = f"{BASE_DATA_DIR}/{tournament}/games/{year}"
        file_path = f"{directory}/{platform_game_id}.json"
        full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{platform_game_id}.json.gz"

        response = requests.get(full_url)
        if response.status_code == 200:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                with open(file_path, 'wb') as output_file:
                    shutil.copyfileobj(gzipped_file, output_file)
            logger.info(f"Downloaded: {platform_game_id}.json")

            process_json_file(file_path, connection, platform_game_id)
            logger.info(f"Processed: {platform_game_id}.json")

            os.remove(file_path)
            logger.info(f"Deleted: {platform_game_id}.json")
            return True
        else:
            logger.error(f"Failed to download {platform_game_id}.json")
            return False
    except Exception as e:
        logger.error(f"Error processing game {platform_game_id}: {e}")
        return False
    finally:
        connection.close()

def process_json_file(filepath, connection, platform_game_id):
    try:
        with open(filepath, 'rb') as file:
            events = ijson.items(file, 'item')
            last_known_positions = {}

            for event in events:
                if 'snapshot' in event:
                    update_last_known_positions(event['snapshot']['players'], last_known_positions)
                elif 'playerDied' in event:
                    process_player_died_event(connection, platform_game_id, event, last_known_positions)
                # Uncomment if you want to process ability_used events
                # elif 'abilityUsed' in event:
                #     process_ability_used_event(connection, platform_game_id, event, last_known_positions)

    except Exception as e:
        logger.error(f"Error processing file {filepath}: {e}")

def update_last_known_positions(players, last_known_positions):
    for player in players:
        player_id = str(player['playerId']['value'])
        if 'aliveState' in player:
            x = player['aliveState']['position']['x']
            y = player['aliveState']['position']['y']
            last_known_positions[player_id] = (x, y)

def process_player_died_event(connection, platform_game_id, event, last_known_positions):
    cursor = connection.cursor()
    try:
        killer_id = str(event['playerDied']['killerId']['value'])
        deceased_id = str(event['playerDied']['deceasedId']['value'])
        
        killer_pos = last_known_positions.get(killer_id, (None, None))
        deceased_pos = last_known_positions.get(deceased_id, (None, None))
        
        cursor.execute("""
            UPDATE player_died
            SET killer_x = %s, killer_y = %s, deceased_x = %s, deceased_y = %s
            WHERE platform_game_id = %s AND killer_id = %s AND deceased_id = %s
            AND event_id = (
                SELECT event_id 
                FROM player_died 
                WHERE platform_game_id = %s AND killer_id = %s AND deceased_id = %s
                AND killer_x IS NULL
                ORDER BY event_id
                LIMIT 1
            )
            RETURNING event_id;
        """, (killer_pos[0], killer_pos[1], deceased_pos[0], deceased_pos[1], 
              platform_game_id, killer_id, deceased_id,
              platform_game_id, killer_id, deceased_id))
        
        updated_row = cursor.fetchone()
        if updated_row:
            logger.info(f"Updated player_died: event_id={updated_row[0]}, platform_game_id={platform_game_id}, "
                        f"killer_id={killer_id}, deceased_id={deceased_id}, "
                        f"coordinates=(killer: {killer_pos}, deceased: {deceased_pos})")
        
        # Process assists
        if 'assistants' in event['playerDied']:
            for assistant in event['playerDied']['assistants']:
                assister_id = str(assistant['assistantId']['value'])
                assister_pos = last_known_positions.get(assister_id, (None, None))
                
                cursor.execute("""
                    UPDATE player_assists
                    SET assister_x = %s, assister_y = %s
                    WHERE platform_game_id = %s AND assister_id = %s
                    AND event_id = (
                        SELECT event_id 
                        FROM player_assists 
                        WHERE platform_game_id = %s AND assister_id = %s
                        AND assister_x IS NULL
                        ORDER BY event_id
                        LIMIT 1
                    )
                    RETURNING event_id;
                """, (assister_pos[0], assister_pos[1], platform_game_id, assister_id,
                      platform_game_id, assister_id))
                
                updated_row = cursor.fetchone()
                if updated_row:
                    logger.info(f"Updated player_assists: event_id={updated_row[0]}, platform_game_id={platform_game_id}, "
                                f"assister_id={assister_id}, coordinates={assister_pos}")
        
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating player_died event: {e}")
    finally:
        cursor.close()

def update_game_events_coordinates(tournament_type, log_file_name, start_game):
    connection = get_db_connection()
    if connection is None:
        logger.error("Could not connect to the database.")
        return

    ensure_columns_exist(connection)
    connection.close()

    mapping_file = f"{BASE_DATA_DIR}/{tournament_type}/esports-data/mapping_data.json"
    
    if not os.path.isfile(mapping_file):
        logger.error(f"Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, "r") as json_file:
        mappings_data = json.load(json_file)

    years = [2022, 2023, 2024] if tournament_type != "vct-challengers" else [2023, 2024]
    total_games = len(mappings_data)
    
    processed_games = start_game
    logger.info(f"Starting from game {processed_games}")
    
    lock = threading.Lock()

    def process_game(tournament, year, platform_game_id):
        nonlocal processed_games
        result = download_and_process_game(tournament, year, platform_game_id)
        with lock:
            if result:
                processed_games += 1
                logger.info(f"Processed game {processed_games}/{total_games}: {platform_game_id} (Year: {year})")
                if processed_games % 10 == 0 or processed_games == total_games:
                    logger.info(f"----- Processed {processed_games}/{total_games} games")
            else:
                logger.warning(f"Failed to process game {platform_game_id} for year {year}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for esports_game in mappings_data[start_game:]:
            platform_game_id = esports_game["platformGameId"]
            for year in years:
                futures.append(executor.submit(process_game, tournament_type, year, platform_game_id))
        
        # Wait for all tasks to complete
        for future in as_completed(futures):
            try:
                future.result()  # This will raise any exceptions that occurred during execution
            except Exception as e:
                logger.error(f"Error processing game: {e}")

    logger.info(f"Game events coordinate update complete for {tournament_type}.")

if __name__ == "__main__":
    log_file_name = input("Enter the name for the log file (default: game_data_processor.log): ").strip() or "game_data_processor.log"
    logger = setup_logging(log_file_name)

    print("Available tournaments:")
    print("1: vct-international")
    print("2: vct-challengers")
    print("3: game-changers")

    tournament_choice = input("Select the tournament by number: ").strip()

    tournament_map = {
        "1": "vct-international",
        "2": "vct-challengers",
        "3": "game-changers"
    }

    tournament_type = tournament_map.get(tournament_choice)

    if tournament_type:
        start_game = input("Enter the game number to start from (default: 0): ").strip()
        start_game = int(start_game) if start_game.isdigit() else 0

        logger.info(f"Starting game events coordinate update for {tournament_type} from game {start_game}")
        update_game_events_coordinates(tournament_type, log_file_name, start_game)
        logger.info(f"Completed game events coordinate update for {tournament_type}")
    else:
        print("Invalid selection.")
        logger.error(f"Invalid tournament selection: {tournament_choice}")