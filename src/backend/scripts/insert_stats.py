import os
import ijson
import psycopg2
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

logging.basicConfig(
    filename="errorlogs_player_stats.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def create_connection():
    try:
        connection = psycopg2.connect(DATABASE_URL)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        logging.error(f"Error connecting to database: {e}")
        return None

def ensure_columns_exist(connection, reset=False):
    cursor = connection.cursor()
    try:
        if reset:
            cursor.execute("""
                ALTER TABLE player_mapping
                DROP COLUMN IF EXISTS kills,
                DROP COLUMN IF EXISTS deaths,
                DROP COLUMN IF EXISTS assists,
                DROP COLUMN IF EXISTS combat_score;
            """)
            print("Dropped existing stat columns.")

        cursor.execute("""
            ALTER TABLE player_mapping
            ADD COLUMN IF NOT EXISTS kills INTEGER,
            ADD COLUMN IF NOT EXISTS deaths INTEGER,
            ADD COLUMN IF NOT EXISTS assists INTEGER,
            ADD COLUMN IF NOT EXISTS combat_score INTEGER;
        """)
        connection.commit()
        print("Ensured necessary columns exist in player_mapping table.")
    except Exception as e:
        connection.rollback()
        print(f"Error ensuring columns: {e}")
        logging.error(f"Error ensuring columns: {e}")
    finally:
        cursor.close()

def stream_events_from_json(filepath):
    print(f"Streaming JSON data from file: {filepath}")
    try:
        with open(filepath, 'rb') as file:
            for event in ijson.items(file, 'item'):
                yield event
    except Exception as e:
        print(f"Error streaming JSON data from file {filepath}: {e}")
        logging.error(f"Error streaming JSON data from file {filepath}: {e}")

def update_player_stats(connection, platform_game_id, player_stats):
    cursor = connection.cursor()
    try:
        for player in player_stats:
            internal_player_id = str(player['playerId']['value'])
            kills = player.get('kills')
            deaths = player.get('deaths')
            assists = player.get('assists')
            combat_score = player.get('scores', {}).get('combatScore', {}).get('totalScore')

            cursor.execute("""
                UPDATE player_mapping
                SET kills = %s, deaths = %s, assists = %s, combat_score = %s
                WHERE internal_player_id = %s AND platform_game_id = %s;
            """, (kills, deaths, assists, combat_score, internal_player_id, platform_game_id))
            
            if cursor.rowcount == 0:
                print(f"No matching entry found for internal player ID {internal_player_id} in game {platform_game_id}")
            else:
                print(f"Updated stats for internal player ID {internal_player_id} in game {platform_game_id}")

        connection.commit()
    except Exception as e:
        connection.rollback()
        print(f"Error updating player stats: {e}")
        logging.error(f"Error updating player stats: {e}")
    finally:
        cursor.close()

def populate_player_stats(tournament_type, year, reset_columns):
    connection = create_connection()
    if connection is None:
        print("Could not connect to the database.")
        return

    ensure_columns_exist(connection, reset_columns)

    games_dir = os.path.join(BASE_DATA_DIR, tournament_type, 'games', year)

    if not os.path.exists(games_dir):
        print(f"No games directory found for {tournament_type} in year {year}.")
        logging.error(f"No games directory found for {tournament_type} in year {year}.")
        return

    for game_file in os.listdir(games_dir):
        if game_file.endswith(".json"):
            file_path = os.path.join(games_dir, game_file)
            print(f"Processing file: {file_path}")

            final_snapshot = None
            platform_game_id = None

            for event in stream_events_from_json(file_path):
                if "snapshot" in event:
                    final_snapshot = event["snapshot"]
                    platform_game_id = event["platformGameId"]

            if final_snapshot and 'players' in final_snapshot:
                if platform_game_id:
                    update_player_stats(connection, platform_game_id, final_snapshot['players'])
                else:
                    print(f"No platform game ID found in file {file_path}")
            else:
                print(f"No valid final snapshot found in file {file_path}")

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
        year = input("Enter the year of the tournament: ").strip()
        reset_option = input("Do you want to reset the stat columns? (y/n): ").strip().lower()
        reset_columns = reset_option == 'y'

        if year.isdigit():
            populate_player_stats(tournament_type, year, reset_columns)
        else:
            print("Invalid year input.")
            logging.error(f"Invalid year input: {year}")
    else:
        print("Invalid selection.")
        logging.error(f"Invalid tournament selection: {tournament_choice}")