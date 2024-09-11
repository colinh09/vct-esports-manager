import os
import ijson
import psycopg2
import logging
from dotenv import load_dotenv

DATABASE_URL = "postgresql://postgres:password@localhost:5432/vct-manager"

# Set up logging configuration
logging.basicConfig(
    filename="errorlogs.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def create_connection():
    """
    Establishes a connection to the PostgreSQL database using the connection string.
    Returns the connection object if successful, otherwise returns None.
    Logs an error message if connection fails.
    """
    try:
        connection = psycopg2.connect(DATABASE_URL)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        logging.error(f"Error connecting to database: {e}")
        return None

def stream_events_from_json(filepath):
    """
    Streams events from a large JSON file to avoid loading everything into memory at once.
    Yields each event as a dictionary.
    Logs an error message if file reading fails.
    """
    print(f"Streaming JSON data from file: {filepath}")
    try:
        with open(filepath, 'r') as file:
            for event in ijson.items(file, 'item'):
                yield event
    except Exception as e:
        print(f"Error streaming JSON data from file {filepath}: {e}")
        logging.error(f"Error streaming JSON data from file {filepath}: {e}")

def insert_event(connection, event_type, platform_game_id, tournament_type):
    """
    Inserts a new event into the 'events' table.
    Returns the event ID of the inserted event.
    Logs an error and rolls back the transaction if insertion fails.
    """
    cursor = connection.cursor()

    query = """
        INSERT INTO events (platform_game_id, event_type, tournament_type)
        VALUES (%s, %s, %s)
        RETURNING event_id;
    """
    
    try:
        cursor.execute(query, (
            platform_game_id,
            event_type,
            tournament_type
        ))
        event_id = cursor.fetchone()[0]
        connection.commit()
        print(f"Inserted event '{event_type}' for platform_game_id {platform_game_id}. Event ID: {event_id}")
    except Exception as e:
        connection.rollback()
        print(f"Error inserting event '{event_type}' for platform_game_id {platform_game_id}: {e}")
        logging.error(f"Error inserting event '{event_type}' for platform_game_id {platform_game_id}: {e}")
        return None
    finally:
        cursor.close()

    return event_id

def insert_event_players(connection, event_id, event_data, event_type):
    """
    Inserts player-related data into the 'event_players' table for the given event.
    Handles various event types such as 'player_died', 'spike_status', 'damage_event', 'player_revived', and 'ability_used'.
    Logs an error and rolls back the transaction if any player insertion fails.
    """
    cursor = connection.cursor()

    platform_game_id = event_data.get("platformGameId")

    try:
        if event_type == "player_died":
            deceased_id = event_data["playerDied"]["deceasedId"]["value"]
            killer_id = event_data["playerDied"]["killerId"]["value"]
            assistants = event_data["playerDied"].get("assistants", [])

            cursor.execute("""
                INSERT INTO event_players (event_id, internal_player_id, platform_game_id, death_id)
                VALUES (%s, %s, %s, %s);
            """, (event_id, deceased_id, platform_game_id, deceased_id))
            print(f"Inserted deceased player for event ID {event_id}")

            cursor.execute("""
                INSERT INTO event_players (event_id, internal_player_id, platform_game_id, kill_id)
                VALUES (%s, %s, %s, %s);
            """, (event_id, killer_id, platform_game_id, killer_id))
            print(f"Inserted killer player for event ID {event_id}")

            for assistant in assistants:
                assistant_id = assistant["assistantId"]["value"]
                cursor.execute("""
                    INSERT INTO event_players (event_id, internal_player_id, platform_game_id, assist_id)
                    VALUES (%s, %s, %s, %s);
                """, (event_id, assistant_id, platform_game_id, assistant_id))
                print(f"Inserted assistant player for event ID {event_id}")

        elif event_type == "spike_status":
            spike_carrier = event_data["spikeStatus"]["carrier"]["value"]
            spike_status = event_data["spikeStatus"]["status"]

            cursor.execute("""
                INSERT INTO event_players (event_id, internal_player_id, platform_game_id, spike_status)
                VALUES (%s, %s, %s, %s);
            """, (event_id, spike_carrier, platform_game_id, spike_status))
            print(f"Inserted spike carrier for event ID {event_id}")

        elif event_type == "damage_event":
            causer_id = event_data["damageEvent"]["causerId"]["value"]
            victim_id = event_data["damageEvent"]["victimId"]["value"]
            damage_amount = event_data["damageEvent"]["damageAmount"]
            damage_location = event_data["damageEvent"]["location"]

            cursor.execute("""
                INSERT INTO event_players (event_id, internal_player_id, platform_game_id, damage_dealt, damage_location)
                VALUES (%s, %s, %s, %s, %s);
            """, (event_id, causer_id, platform_game_id, damage_amount, damage_location))
            print(f"Inserted damage event for causer {causer_id} in event ID {event_id}")

            if event_data["damageEvent"].get("killEvent"):
                cursor.execute("""
                    INSERT INTO event_players (event_id, internal_player_id, platform_game_id, death_id)
                    VALUES (%s, %s, %s, %s);
                """, (event_id, victim_id, platform_game_id, victim_id))
                print(f"Inserted death event for victim {victim_id} in event ID {event_id}")

        elif event_type == "player_revived":
            revived_by_id = event_data["playerRevived"]["revivedById"]["value"]
            revived_id = event_data["playerRevived"]["revivedId"]["value"]

            cursor.execute("""
                INSERT INTO event_players (event_id, internal_player_id, platform_game_id, revived_by_id, revived_player_id)
                VALUES (%s, %s, %s, %s, %s);
            """, (event_id, revived_by_id, platform_game_id, revived_by_id, revived_id))
            print(f"Inserted player revived event for revived ID {revived_id} in event ID {event_id}")

        elif event_type == "ability_used":
            player_id = event_data["abilityUsed"]["playerId"]["value"]
            ability_guid = event_data["abilityUsed"]["ability"]["fallback"]["guid"]

            cursor.execute("""
                INSERT INTO event_players (event_id, internal_player_id, platform_game_id, ability_used)
                VALUES (%s, %s, %s, %s);
            """, (event_id, player_id, platform_game_id, ability_guid))
            print(f"Inserted ability used event for player {player_id} in event ID {event_id}")

        connection.commit()

    except Exception as e:
        connection.rollback()
        print(f"Error inserting event_players data for event ID {event_id}: {e}")
        logging.error(f"Error inserting event_players data for event ID {event_id}: {e}")
    finally:
        cursor.close()

def populate_events(tournament_type, year):
    """
    Populates the 'events' and 'event_players' tables by processing game files from a given tournament and year.
    Streams events from each game file (due to the large size of the json files) and inserts them into the database.
    Logs errors if directories or files are not found, or if data insertion fails.
    """
    connection = create_connection()
    if connection is None:
        print("Could not connect to the database.")
        return

    games_dir = f"../data/{tournament_type}/games/{year}/"
    
    if not os.path.exists(games_dir):
        print(f"No games directory found for {tournament_type} in year {year}.")
        logging.error(f"No games directory found for {tournament_type} in year {year}.")
        return

    # Process each game file in the directory
    for game_file in os.listdir(games_dir):
        if game_file.endswith(".json"):
            file_path = os.path.join(games_dir, game_file)
            print(f"Processing file: {file_path}")
            
            # Stream events from JSON
            for event in stream_events_from_json(file_path):
                platform_game_id = event.get("platformGameId")

                # Check for player-centric events
                if "playerDied" in event:
                    event_type = "player_died"
                elif "spikeStatus" in event:
                    event_type = "spike_status"
                elif "damageEvent" in event:
                    event_type = "damage_event"
                elif "playerRevived" in event:
                    event_type = "player_revived"
                elif "abilityUsed" in event:
                    event_type = "ability_used"
                else:
                    # Skip events that aren't player-centric
                    continue

                # Insert the event into the events table
                event_id = insert_event(connection, event_type, platform_game_id, tournament_type)
                
                # Insert player-specific data into the event_players table
                if event_id:
                    insert_event_players(connection, event_id, event, event_type)

    connection.close()

if __name__ == "__main__":
    """
    Main script entry point.
    Prompts user for tournament type and year, and processes events for the selected tournament.
    Logs errors for invalid inputs or selections.
    This script will only fetch 'important', user-centric events that will help determine a player's impact
    """
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
            populate_events(tournament_type, year)
        else:
            print("Invalid year input.")
            logging.error(f"Invalid year input: {year}")
    else:
        print("Invalid selection.")
        logging.error(f"Invalid tournament selection: {tournament_choice}")
