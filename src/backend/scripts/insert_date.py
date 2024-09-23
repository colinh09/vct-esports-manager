import os
import psycopg2
import logging
from logging.handlers import RotatingFileHandler
import json
import gzip
from io import BytesIO
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

# Set up logging
logger = logging.getLogger('game_date_updater')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('game_date_updater.log', maxBytes=100*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def ensure_game_date_column(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='game_mapping' AND column_name='game_date';
        """)
        if cursor.fetchone() is None:
            cursor.execute("""
                ALTER TABLE game_mapping 
                ADD COLUMN game_date DATE;
            """)
            logger.info("Added game_date column to game_mapping table")
        connection.commit()
    except Exception as e:
        connection.rollback()
        logger.error(f"Error ensuring game_date column exists: {e}")
    finally:
        cursor.close()

def download_and_extract_date(tournament, year, platform_game_id):
    try:
        full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{platform_game_id}.json.gz"
        response = requests.get(full_url)
        if response.status_code == 200:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                content = gzipped_file.read().decode('utf-8')
                json_data = json.loads(content)
                for event in json_data:
                    if 'metadata' in event:
                        wall_time = event['metadata'].get('wallTime')
                        if wall_time:
                            return wall_time.split('T')[0]  # Extract just the date part
        else:
            logger.error(f"Failed to download {platform_game_id}.json")
    except Exception as e:
        logger.error(f"Error processing game {platform_game_id}: {e}")
    return None

def update_game_dates(connection, tournament_type):
    cursor = connection.cursor()
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
            game_date = download_and_extract_date(tournament_type, year, platform_game_id)
            if game_date:
                try:
                    cursor.execute("""
                        UPDATE game_mapping
                        SET game_date = %s
                        WHERE platform_game_id = %s;
                    """, (game_date, platform_game_id))
                    connection.commit()
                    logger.info(f"Updated game date for {platform_game_id}: {game_date}")
                    break
                except Exception as e:
                    connection.rollback()
                    logger.error(f"Error updating game date for {platform_game_id}: {e}")

        if processed_games % 10 == 0:
            logger.info(f"----- Processed {processed_games}/{total_games} games")

    logger.info(f"Game date update complete for {tournament_type}.")

def perform_time_series_analysis(connection):
    cursor = connection.cursor()
    try:
        # Example: Get player performance over time
        cursor.execute("""
            SELECT 
                gm.game_date,
                pm.handle,
                AVG(pm.kills) as avg_kills,
                AVG(pm.deaths) as avg_deaths,
                AVG(pm.assists) as avg_assists,
                AVG(pm.average_combat_score) as avg_acs
            FROM 
                game_mapping gm
            JOIN 
                player_mapping pm ON gm.platform_game_id = pm.platform_game_id
            GROUP BY 
                gm.game_date, pm.handle
            ORDER BY 
                gm.game_date, pm.handle
        """)
        results = cursor.fetchall()
        
        # Process and print results
        print("Player Performance Over Time:")
        for row in results:
            print(f"Date: {row[0]}, Player: {row[1]}, Avg Kills: {row[2]:.2f}, Avg Deaths: {row[3]:.2f}, Avg Assists: {row[4]:.2f}, Avg ACS: {row[5]:.2f}")

        # You can add more analysis queries here

    except Exception as e:
        logger.error(f"Error performing time series analysis: {e}")
    finally:
        cursor.close()

if __name__ == "__main__":
    connection = create_connection()
    if connection is None:
        logger.error("Could not connect to the database.")
    else:
        ensure_game_date_column(connection)

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
            logger.info(f"Starting game date update for {tournament_type}")
            update_game_dates(connection, tournament_type)
            logger.info(f"Completed game date update for {tournament_type}")

            print("Performing time series analysis...")
            perform_time_series_analysis(connection)
        else:
            print("Invalid selection.")
            logger.error(f"Invalid tournament selection: {tournament_choice}")

        connection.close()