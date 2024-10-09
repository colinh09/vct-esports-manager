import os
import ijson
import psycopg2
from psycopg2 import pool
import psycopg2.extras
import logging
from logging.handlers import RotatingFileHandler
import requests
import json
import gzip
from io import BytesIO
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

# Global connection pool
connection_pool = None

# Global logger
logger = None

def setup_logging(log_file_name):
    global logger
    logger = logging.getLogger('player_died_side_updater')
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_file_name, maxBytes=100*1024*1024, backupCount=5)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_db_connection():
    conn = connection_pool.getconn()
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_READ_COMMITTED)
    return conn

def return_db_connection(conn):
    connection_pool.putconn(conn)

def add_attacking_columns():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            ALTER TABLE player_died 
            ADD COLUMN IF NOT EXISTS deceased_is_attacking BOOLEAN,
            ADD COLUMN IF NOT EXISTS killer_is_attacking BOOLEAN;
        """)
        conn.commit()
        logger.info("Added attacking columns to player_died table")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding attacking columns: {e}")
    finally:
        cursor.close()
        return_db_connection(conn)

def process_game_file(tournament, year, platform_game_id):
    conn = get_db_connection()
    try:
        file_path = f"{BASE_DATA_DIR}/{tournament}/games/{year}/{platform_game_id}.json"
        full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{platform_game_id}.json.gz"

        response = requests.get(full_url)
        if response.status_code == 200:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                with open(file_path, 'wb') as output_file:
                    output_file.write(gzipped_file.read())
            logger.info(f"Downloaded: {platform_game_id}.json")

            process_json_file(file_path, conn, platform_game_id)
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
        return_db_connection(conn)

def process_json_file(filepath, connection, platform_game_id):
    updates = []
    team_players = {}
    attacking_team = None
    last_known_positions = {}

    try:
        with open(filepath, 'rb') as file:
            events = ijson.items(file, 'item')

            for event in events:
                if 'configuration' in event:
                    for team in event['configuration'].get('teams', []):
                        team_id = team['teamId']['value']
                        team_players[team_id] = [str(player['value']) for player in team.get('playersInTeam', [])]

                elif 'roundStarted' in event:
                    attacking_team = event['roundStarted']['spikeMode']['attackingTeam']['value']

                elif 'snapshot' in event:
                    update_last_known_positions(event['snapshot']['players'], last_known_positions)

                elif 'playerDied' in event:
                    update = process_player_died_event(platform_game_id, event, last_known_positions, team_players, attacking_team)
                    if update:
                        updates.append(update)

        if updates:
            perform_bulk_upsert(connection, updates)
            logger.info(f"Bulk upsert completed for game {platform_game_id} with {len(updates)} updates")

    except Exception as e:
        logger.error(f"Error processing file {filepath}: {e}")

def update_last_known_positions(players, last_known_positions):
    for player in players:
        player_id = str(player['playerId']['value'])
        if 'aliveState' in player:
            x = player['aliveState']['position']['x']
            y = player['aliveState']['position']['y']
            last_known_positions[player_id] = (x, y)

def process_player_died_event(platform_game_id, event, last_known_positions, team_players, attacking_team):
    killer_id = str(event['playerDied']['killerId']['value'])
    deceased_id = str(event['playerDied']['deceasedId']['value'])
    
    killer_pos = last_known_positions.get(killer_id, (None, None))
    deceased_pos = last_known_positions.get(deceased_id, (None, None))
    
    deceased_is_attacking = any(deceased_id in players for team, players in team_players.items() if team == attacking_team)
    killer_is_attacking = any(killer_id in players for team, players in team_players.items() if team == attacking_team)
    
    return (
        platform_game_id, killer_id, deceased_id,
        killer_pos[0], killer_pos[1], deceased_pos[0], deceased_pos[1],
        deceased_is_attacking, killer_is_attacking
    )

def perform_bulk_upsert(connection, updates):
    cursor = connection.cursor()
    try:
        psycopg2.extras.execute_values(
            cursor,
            """
            UPDATE player_died
            SET deceased_is_attacking = data.deceased_is_attacking,
                killer_is_attacking = data.killer_is_attacking
            FROM (VALUES %s) AS data(platform_game_id, killer_id, deceased_id,
                                     killer_x, killer_y, deceased_x, deceased_y,
                                     deceased_is_attacking, killer_is_attacking)
            WHERE player_died.platform_game_id = data.platform_game_id
              AND player_died.killer_id = data.killer_id
              AND player_died.deceased_id = data.deceased_id
              AND player_died.killer_x = data.killer_x
              AND player_died.killer_y = data.killer_y
              AND player_died.deceased_x = data.deceased_x
              AND player_died.deceased_y = data.deceased_y
            """,
            updates
        )
        
        affected_rows = cursor.rowcount
        connection.commit()
        logger.info(f"Bulk update completed: {affected_rows} rows affected")
    except psycopg2.Error as e:
        connection.rollback()
        logger.error(f"Error performing bulk update: {e}")
    finally:
        cursor.close()

def update_player_died_side(tournament_type, log_file_name, start_game):
    global connection_pool
    connection_pool = pool.ThreadedConnectionPool(20, 50, DATABASE_URL)

    add_attacking_columns()

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
        result = process_game_file(tournament, year, platform_game_id)
        with lock:
            if result:
                processed_games += 1
                logger.info(f"Processed game {processed_games}/{total_games}: {platform_game_id} (Year: {year})")
                if processed_games % 10 == 0 or processed_games == total_games:
                    logger.info(f"----- Processed {processed_games}/{total_games} games")
            else:
                logger.warning(f"Failed to process game {platform_game_id} for year {year}")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for esports_game in mappings_data[start_game:]:
            platform_game_id = esports_game["platformGameId"]
            for year in years:
                futures.append(executor.submit(process_game, tournament_type, year, platform_game_id))
        
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error processing game: {e}")

    logger.info(f"Player died side update complete for {tournament_type}.")
    
    # Close all connections in the pool
    connection_pool.closeall()

if __name__ == "__main__":
    log_file_name = input("Enter the name for the log file (default: player_died_side_update.log): ").strip() or "player_died_side_update.log"
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

        logger.info(f"Starting player died side update for {tournament_type} from game {start_game}")
        update_player_died_side(tournament_type, log_file_name, start_game)
        logger.info(f"Completed player died side update for {tournament_type}")
    else:
        print("Invalid selection.")
        logger.error(f"Invalid tournament selection: {tournament_choice}")