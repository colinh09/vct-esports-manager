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

# Set up logging
logger = logging.getLogger('acs_update_logger')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('acs_update.log', maxBytes=100*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def ensure_columns_exist(connection):
    cursor = connection.cursor()
    try:
        # Check and add average_combat_score column to player_mapping table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='player_mapping' AND column_name='average_combat_score';
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE player_mapping 
                ADD COLUMN average_combat_score FLOAT;
            """)
            logger.info("Added average_combat_score column to player_mapping table")

        # Check and add total_rounds and winning_team columns to game_mapping table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='game_mapping' AND column_name IN ('total_rounds', 'winning_team');
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if 'total_rounds' not in existing_columns:
            cursor.execute("""
                ALTER TABLE game_mapping 
                ADD COLUMN total_rounds INTEGER;
            """)
            logger.info("Added total_rounds column to game_mapping table")
        
        if 'winning_team' not in existing_columns:
            cursor.execute("""
                ALTER TABLE game_mapping 
                ADD COLUMN winning_team VARCHAR;
            """)
            logger.info("Added winning_team column to game_mapping table")

        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f"Error ensuring columns exist: {e}")
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
            events = ijson.items(file, 'item')
            final_snapshot = None
            total_rounds = None
            winning_team = None

            for event in events:
                if 'snapshot' in event:
                    final_snapshot = event['snapshot']
                elif 'gameDecided' in event:
                    game_decided = event['gameDecided']
                    total_rounds = game_decided['spikeMode']['currentRound']
                    winning_team = str(game_decided['winningTeam']['value'])

            if final_snapshot and 'players' in final_snapshot and total_rounds is not None:
                update_player_acs(connection, platform_game_id, final_snapshot['players'], total_rounds)
                update_game_mapping(connection, platform_game_id, total_rounds, winning_team)
            else:
                logger.warning(f"No valid data found for ACS calculation in file {filepath}")

    except Exception as e:
        logger.error(f"Error processing file {filepath}: {e}")

def update_player_acs(connection, platform_game_id, players, total_rounds):
    cursor = connection.cursor()
    try:
        for player in players:
            internal_player_id = str(player['playerId']['value'])
            combat_score = player.get('scores', {}).get('combatScore', {}).get('totalScore', 0)
            acs = combat_score / total_rounds if total_rounds > 0 else 0
            
            cursor.execute("""
                UPDATE player_mapping
                SET average_combat_score = %s
                WHERE internal_player_id = %s AND platform_game_id = %s;
            """, (acs, internal_player_id, platform_game_id))
        
        connection.commit()
        logger.info(f"Updated ACS for {len(players)} players in game {platform_game_id}")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating ACS for game {platform_game_id}: {e}")
    finally:
        cursor.close()

def update_game_mapping(connection, platform_game_id, total_rounds, winning_team):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            UPDATE game_mapping
            SET total_rounds = %s, winning_team = %s
            WHERE platform_game_id = %s;
        """, (total_rounds, winning_team, platform_game_id))
        
        connection.commit()
        logger.info(f"Updated game mapping for game {platform_game_id}")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating game mapping for game {platform_game_id}: {e}")
    finally:
        cursor.close()

def update_acs_and_game_mapping(tournament_type):
    connection = create_connection()
    if connection is None:
        logger.error("Could not connect to the database.")
        return

    ensure_columns_exist(connection)

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

    logger.info(f"ACS and game mapping update complete for {tournament_type}.")
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
        logger.info(f"Starting ACS and game mapping update for {tournament_type}")
        update_acs_and_game_mapping(tournament_type)
        logger.info(f"Completed ACS and game mapping update for {tournament_type}")
    else:
        print("Invalid selection.")
        logger.error(f"Invalid tournament selection: {tournament_choice}")