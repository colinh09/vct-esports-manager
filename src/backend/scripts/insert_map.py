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

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

# Logger will be set up in the main function after tournament type is selected

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def ensure_map_column_exists(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='game_mapping' AND column_name='map';
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE game_mapping 
                ADD COLUMN map VARCHAR;
            """)
            logger.info("Added map column to game_mapping table")
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f"Error ensuring map column exists: {e}")
    finally:
        cursor.close()

def download_and_process_game(tournament, year, platform_game_id, connection):
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

def process_json_file(filepath, connection, platform_game_id):
    try:
        with open(filepath, 'rb') as file:
            events = ijson.parse(file)
            map_guid = None

            for prefix, event, value in events:
                if prefix == 'item.configuration.selectedMap.fallback.guid':
                    map_guid = value
                    break  # We only need the first occurrence

            if map_guid:
                update_game_map(connection, platform_game_id, map_guid)
            else:
                logger.warning(f"No map GUID found for game {platform_game_id}")

    except Exception as e:
        logger.error(f"Error processing file {filepath}: {e}")

def update_game_map(connection, platform_game_id, map_guid):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE game_mapping
            SET map = %s
            WHERE platform_game_id = %s;
        """, (map_guid, platform_game_id))
        
        connection.commit()
        logger.info(f"Updated map for game {platform_game_id}")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating map for game {platform_game_id}: {e}")
    finally:
        cursor.close()

def update_game_maps(tournament_type):
    connection = create_connection()
    if connection is None:
        logger.error("Could not connect to the database.")
        return

    ensure_map_column_exists(connection)

    mapping_file = f"{BASE_DATA_DIR}/{tournament_type}/esports-data/mapping_data.json"
    
    if not os.path.isfile(mapping_file):
        logger.error(f"Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, "r") as json_file:
        mappings_data = json.load(json_file)

    years = [2022, 2023, 2024] if tournament_type != "vct-challengers" else [2023, 2024]
    total_games = len(mappings_data)
    processed_games = 0

    for esports_game in mappings_data:
        platform_game_id = esports_game["platformGameId"]
        processed_games += 1

        for year in years:
            if download_and_process_game(tournament_type, year, platform_game_id, connection):
                logger.info(f"Processed game {processed_games}/{total_games}: {platform_game_id} (Year: {year})")
                break
        else:
            logger.warning(f"Game {platform_game_id} not found in any year directory")

        if processed_games % 10 == 0:
            logger.info(f"----- Processed {processed_games}/{total_games} games")

    logger.info(f"Game map update complete for {tournament_type}.")
    connection.close()

if __name__ == "__main__":
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
        # Set up logging with dynamic file name
        log_file_name = f'game_map_update_{tournament_type}.log'
        logger = logging.getLogger(f'game_map_update_logger_{tournament_type}')
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_file_name, maxBytes=100*1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        logger.info(f"Starting game map update for {tournament_type}")
        update_game_maps(tournament_type)
        logger.info(f"Completed game map update for {tournament_type}")
    else:
        print("Invalid selection.")
        print(f"Invalid tournament selection: {tournament_choice}")