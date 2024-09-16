import os
import ijson
import psycopg2
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

logging.basicConfig(
    filename="update_player_mapping_logs.txt",
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

def check_and_add_agent_guid_column(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='player_mapping' AND column_name='agent_guid';
        """)
        if not cursor.fetchone():
            cursor.execute("""
                ALTER TABLE player_mapping
                ADD COLUMN agent_guid VARCHAR(255);
            """)
            connection.commit()
            print("Added agent_guid column to player_mapping table.")
        else:
            print("agent_guid column already exists in player_mapping table.")
    except Exception as e:
        print(f"Error checking/adding agent_guid column: {e}")
        logging.error(f"Error checking/adding agent_guid column: {e}")
    finally:
        cursor.close()

def process_configuration_event(connection, event_data):
    cursor = connection.cursor()
    try:
        platform_game_id = event_data["platformGameId"]
        for player in event_data["configuration"]["players"]:
            internal_player_id = str(player["playerId"]["value"])
            agent_guid = player["selectedAgent"]["fallback"]["guid"]

            cursor.execute("""
                UPDATE player_mapping
                SET agent_guid = %s
                WHERE internal_player_id = %s 
                  AND platform_game_id = %s;
            """, (agent_guid, internal_player_id, platform_game_id))
            
            if cursor.rowcount == 0:
                print(f"No matching entry found for internal player ID {internal_player_id} in game {platform_game_id}")
            else:
                print(f"Updated agent for internal player ID {internal_player_id} in game {platform_game_id}")

        connection.commit()
    except Exception as e:
        connection.rollback()
        print(f"Error processing configuration event: {e}")
        logging.error(f"Error processing configuration event: {e}")
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

def process_game_file(connection, file_path):
    for event in stream_events_from_json(file_path):
        if "configuration" in event:
            process_configuration_event(connection, event)
            break  # Stop after processing the configuration event

def update_player_mapping(tournament_type, year):
    connection = create_connection()
    if connection is None:
        return

    check_and_add_agent_guid_column(connection)

    games_dir = os.path.join(BASE_DATA_DIR, tournament_type, 'games', year)

    if not os.path.exists(games_dir):
        print(f"No games directory found for {tournament_type} in year {year}.")
        logging.error(f"No games directory found for {tournament_type} in year {year}.")
        return

    for game_file in os.listdir(games_dir):
        if game_file.endswith(".json"):
            file_path = os.path.join(games_dir, game_file)
            print(f"Processing file: {file_path}")
            process_game_file(connection, file_path)

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

        if year.isdigit():
            update_player_mapping(tournament_type, year)
        else:
            print("Invalid year input.")
            logging.error(f"Invalid year input: {year}")
    else:
        print("Invalid selection.")
        logging.error(f"Invalid tournament selection: {tournament_choice}")