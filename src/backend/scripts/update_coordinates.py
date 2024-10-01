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
import time

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

def setup_logging(log_file_name):
    logger = logging.getLogger('game_data_updater')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file_name, maxBytes=100*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_db_connection():
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            connection = psycopg2.connect(DATABASE_URL)
            return connection
        except Exception as e:
            logger.error(f"Error connecting to database (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    return None

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
        
        connection.commit()
        logger.info("Ensured columns exist for coordinates in event tables")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error ensuring columns exist: {e}")
    finally:
        cursor.close()

def reset_game_coordinates(connection, platform_game_id):
    cursor = connection.cursor()
    try:
        # Reset coordinates in player_died table
        cursor.execute("""
            UPDATE player_died
            SET killer_x = NULL, killer_y = NULL, deceased_x = NULL, deceased_y = NULL
            WHERE platform_game_id = %s;
        """, (platform_game_id,))
        
        # Reset coordinates in player_assists table
        cursor.execute("""
            UPDATE player_assists
            SET assister_x = NULL, assister_y = NULL
            WHERE platform_game_id = %s;
        """, (platform_game_id,))
        
        connection.commit()
        logger.info(f"Reset coordinates for platform_game_id: {platform_game_id}")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error resetting coordinates for platform_game_id {platform_game_id}: {e}")
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
            logger.info(f"Downloaded: {platform_game_id}.json for year {year}")

            reset_game_coordinates(connection, platform_game_id)
            process_json_file(file_path, connection, platform_game_id)
            logger.info(f"Processed: {platform_game_id}.json for year {year}")

            os.remove(file_path)
            logger.info(f"Deleted: {platform_game_id}.json for year {year}")
            return True
        else:
            logger.warning(f"Failed to download {platform_game_id}.json for year {year}")
            return False
    except Exception as e:
        logger.error(f"Error processing game {platform_game_id} for year {year}: {e}")
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
        else:
            logger.warning(f"No matching row found for update: platform_game_id={platform_game_id}, "
                           f"killer_id={killer_id}, deceased_id={deceased_id}")
        
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
                else:
                    logger.warning(f"No matching row found for assist update: platform_game_id={platform_game_id}, "
                                   f"assister_id={assister_id}")
        
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating player_died event: {e}")
    finally:
        cursor.close()

def update_specific_game(tournament_type, platform_game_id):
    connection = get_db_connection()
    if connection is None:
        logger.error("Could not connect to the database.")
        return

    ensure_columns_exist(connection)
    connection.close()

    years = [2022, 2023, 2024] if tournament_type != "vct-challengers" else [2023, 2024]
    
    for year in years:
        result = download_and_process_game(tournament_type, year, platform_game_id)
        if result:
            logger.info(f"Successfully updated game {platform_game_id} for year {year}")
            return  # Exit the function if successful
        else:
            logger.warning(f"Failed to update game {platform_game_id} for year {year}")
    
    logger.error(f"Failed to update game {platform_game_id} for any year")

if __name__ == "__main__":
    log_file_name = input("Enter the name for the log file (default: game_data_updater.log): ").strip() or "game_data_updater.log"
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
        platform_game_ids = input("Enter the platform game IDs to update (comma-separated): ").strip().split(',')

        logger.info(f"Starting game events coordinate update for {tournament_type}")
        for platform_game_id in platform_game_ids:
            update_specific_game(tournament_type, platform_game_id.strip())
        logger.info(f"Completed game events coordinate update for {tournament_type}")
    else:
        print("Invalid selection.")
        logger.error(f"Invalid tournament selection: {tournament_choice}")