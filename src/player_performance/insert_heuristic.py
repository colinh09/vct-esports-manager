import os
import json
import gzip
import shutil
import psycopg2
import logging
from io import BytesIO
import requests
from dotenv import load_dotenv
from heuristic import process_game_file  # Import the function directly
import traceback
load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"
LOGS_DIR = "logs"  # New constant for logs directory

def setup_logger(log_name):
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(LOGS_DIR, f'{log_name}.log'))
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def download_and_process_game(tournament, year, platform_game_id, connection, logger):
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

            # Process the game file using the imported function
            player_stats = process_game_file(file_path)
            update_player_stats(connection, platform_game_id, player_stats, logger)
            logger.info(f"Processed: {platform_game_id}.json")

            os.remove(file_path)
            logger.info(f"Deleted: {platform_game_id}.json")
            return True
        else:
            logger.error(f"Failed to download {platform_game_id}.json")
            return False
    except Exception as e:
        error_message = f"Error processing game {platform_game_id}:\n{traceback.format_exc()}"
        logger.error(error_message)
        raise SystemExit(error_message)

def update_player_stats(connection, platform_game_id, player_stats, logger):
    cursor = connection.cursor()
    try:
        for player_id, stats in player_stats.items():
            cursor.execute("""
                UPDATE player_mapping
                SET kills_attacking = %s, kills_defending = %s,
                    deaths_attacking = %s, deaths_defending = %s,
                    assists_attacking = %s, assists_defending = %s,
                    econ_kills = %s, rounds_won = %s, rounds_survived = %s,
                    ability_usage_damaging = %s, ability_usage_non_damaging = %s,
                    ability_effectiveness_damaging = %s, ability_effectiveness_non_damaging = %s,
                    first_bloods = %s, multi_kills = %s, clutch_wins = %s,
                    initiator_ability_deaths = %s,
                    final_score = %s, normalized_score = %s
                WHERE internal_player_id = %s AND platform_game_id = %s;
            """, (
                stats['kills_attacking'], stats['kills_defending'],
                stats['deaths_attacking'], stats['deaths_defending'],
                stats['assists_attacking'], stats['assists_defending'],
                stats['econ_kills'], stats['rounds_won'], stats['rounds_survived'],
                stats['ability_usage_damaging'], stats['ability_usage_non_damaging'],
                stats['ability_effectiveness_damaging'], stats['ability_effectiveness_non_damaging'],
                stats['first_bloods'], stats['multi_kills'], stats['clutch_wins'],
                stats['initiator_ability_deaths'],
                round(stats['final_score'], 2), round(stats['normalized_score'], 2),
                str(player_id), platform_game_id
            ))
        connection.commit()
        logger.info(f"Updated stats for {len(player_stats)} players in game {platform_game_id}")
    except Exception as e:
        connection.rollback()
        logger.error(f"Error updating player stats for game {platform_game_id}: {e}")
    finally:
        cursor.close()

def update_player_statistics(tournament_type, logger, start_from=0):
    connection = create_connection()
    if connection is None:
        logger.error("Could not connect to the database.")
        return

    mapping_file = f"{BASE_DATA_DIR}/{tournament_type}/esports-data/mapping_data.json"
    
    if not os.path.isfile(mapping_file):
        logger.error(f"Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, "r") as json_file:
        mappings_data = json.load(json_file)

    years = [2022, 2023, 2024] if tournament_type != "vct-challengers" else [2023, 2024]
    total_games = len(mappings_data)

    for i, esports_game in enumerate(mappings_data):
        current_game = i + 1  # This represents the actual game number
        
        if current_game < start_from:
            continue

        platform_game_id = esports_game["platformGameId"]

        for year in years:
            if download_and_process_game(tournament_type, year, platform_game_id, connection, logger):
                logger.info(f"Processed game {current_game}/{total_games}: {platform_game_id} (Year: {year})")
                break
        else:
            logger.warning(f"Game {platform_game_id} not found in any year directory")

        if current_game % 10 == 0:
            logger.info(f"----- Processed up to game {current_game}/{total_games}")

    logger.info(f"Player statistics update complete for {tournament_type}.")
    connection.close()

if __name__ == "__main__":
    print("Available tournaments:")
    print("1: vct-international")
    print("2: vct-challengers")
    print("3: game-changers")

    tournament_choice = input("Select the tournament by number: ").strip()
    log_name = input("Enter the desired log name (without .log extension): ").strip()
    start_from = int(input("Enter the game number to start from (1 to start from beginning): ").strip())

    tournament_map = {
        "1": "vct-international",
        "2": "vct-challengers",
        "3": "game-changers"
    }

    tournament_type = tournament_map.get(tournament_choice)

    if tournament_type:
        logger = setup_logger(log_name)
        logger.info(f"Starting player statistics update for {tournament_type} from game {start_from}")
        update_player_statistics(tournament_type, logger, start_from)
        logger.info(f"Completed player statistics update for {tournament_type}")
    else:
        print("Invalid selection.")
        print(f"Invalid tournament selection: {tournament_choice}")