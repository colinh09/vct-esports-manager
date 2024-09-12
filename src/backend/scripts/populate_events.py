import os
import ijson
import psycopg2
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

# Error logging configuration
logging.basicConfig(
    filename="errorlogs_events.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def create_connection():
    """
    Establishes a connection to the PostgreSQL database using the connection string.
    Returns the connection object if successful, otherwise returns None.
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
    """
    print(f"Streaming JSON data from file: {filepath}")
    try:
        with open(filepath, 'r') as file:
            for event in ijson.items(file, 'item'):
                yield event
    except Exception as e:
        print(f"Error streaming JSON data from file {filepath}: {e}")
        logging.error(f"Error streaming JSON data from file {filepath}: {e}")

def insert_player_died(connection, event_data):
    """
    Inserts a player died event and related assists into the database.
    """
    cursor = connection.cursor()
    
    try:
        # Extract fields from event_data
        platform_game_id = event_data["platformGameId"]
        deceased_id = event_data["playerDied"]["deceasedId"]["value"]
        killer_id = event_data["playerDied"]["killerId"]["value"]
        
        # If weapon data isn't available, assign None - this happens a lot, but doesn't really matter!
        weapon_guid = event_data["playerDied"].get("weapon", {}).get("fallback", {}).get("guid", None)

        # Insert player died event
        cursor.execute("""
            INSERT INTO player_died (platform_game_id, deceased_id, killer_id, weapon_guid)
            VALUES (%s, %s, %s, %s)
            RETURNING event_id;
        """, (platform_game_id, deceased_id, killer_id, weapon_guid))
        
        event_id = cursor.fetchone()[0]
        print(f"Inserted player died event. Event ID: {event_id}")

        # Insert assists if any
        assistants = event_data["playerDied"].get("assistants", [])
        for assistant in assistants:
            assister_id = assistant["assistantId"]["value"]
            cursor.execute("""
                INSERT INTO player_assists (platform_game_id, assister_id)
                VALUES (%s, %s);
            """, (platform_game_id, assister_id))
            print(f"Inserted assist by player {assister_id} for event ID {event_id}")

        connection.commit()
        return event_id

    except KeyError as e:
        # Skip the event and log error if any other required field is missing
        print(f"Skipping player died event due to missing field: {e}")
        logging.error(f"Skipping player died event due to missing field: {e}")
    except Exception as e:
        connection.rollback()
        print(f"Error inserting player died event: {e}")
        logging.error(f"Error inserting player died event: {e}")
    finally:
        cursor.close()

def insert_spike_status(connection, event_data):
    """
    Inserts a spike status event into the database. Doesn't log errors for missing fields.
    """
    cursor = connection.cursor()
    
    try:
        # Extract fields from event_data
        platform_game_id = event_data["platformGameId"]
        carrier_id = event_data["spikeStatus"]["carrier"]["value"]
        status = event_data["spikeStatus"]["status"]

        cursor.execute("""
            INSERT INTO spike_status (platform_game_id, carrier_id, status)
            VALUES (%s, %s, %s);
        """, (platform_game_id, carrier_id, status))
        
        connection.commit()
        # Dont log any errors here - there are a lot of situations when the spike has no carrier
        # If no carrer - not relevant to us at all!
        print(f"Inserted spike status event for carrier {carrier_id}")

    except KeyError:
        # Silently skip spike status events with missing fields, no logging needed
        print(f"Skipping spike status event due to missing data.")
    except Exception as e:
        connection.rollback()
        print(f"Error inserting spike status event: {e}")
        logging.error(f"Error inserting spike status event: {e}")
    finally:
        cursor.close()

def insert_damage_event(connection, event_data):
    """
    Inserts a damage event into the database.
    """
    cursor = connection.cursor()
    
    try:
        # Extract fields from event_data
        platform_game_id = event_data["platformGameId"]
        causer_id = event_data["damageEvent"]["causerId"]["value"]
        victim_id = event_data["damageEvent"]["victimId"]["value"]
        location = event_data["damageEvent"]["location"]
        damage_amount = event_data["damageEvent"]["damageAmount"]
        kill_event = event_data["damageEvent"]["killEvent"]

        cursor.execute("""
            INSERT INTO damage_event (platform_game_id, causer_id, victim_id, location, damage_amount, kill_event)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (platform_game_id, causer_id, victim_id, location, damage_amount, kill_event))
        
        connection.commit()
        print(f"Inserted damage event for causer {causer_id} and victim {victim_id}")

    except KeyError as e:
        # Skip the event and log error if any required field is missing
        print(f"Skipping damage event due to missing field: {e}")
        logging.error(f"Skipping damage event due to missing field: {e}")
    except Exception as e:
        connection.rollback()
        print(f"Error inserting damage event: {e}")
        logging.error(f"Error inserting damage event: {e}")
    finally:
        cursor.close()

def insert_player_revived(connection, event_data):
    """
    Inserts a player revived event into the database.
    """
    cursor = connection.cursor()
    
    try:
        # Extract fields from event_data
        platform_game_id = event_data["platformGameId"]
        revived_by_id = event_data["playerRevived"]["revivedById"]["value"]
        revived_id = event_data["playerRevived"]["revivedId"]["value"]

        cursor.execute("""
            INSERT INTO player_revived (platform_game_id, revived_by_id, revived_id)
            VALUES (%s, %s, %s);
        """, (platform_game_id, revived_by_id, revived_id))
        
        connection.commit()
        print(f"Inserted player revived event for revived player {revived_id}")

    except KeyError as e:
        # Skip the event and log error if any required field is missing
        print(f"Skipping player revived event due to missing field: {e}")
        logging.error(f"Skipping player revived event due to missing field: {e}")
    except Exception as e:
        connection.rollback()
        print(f"Error inserting player revived event: {e}")
        logging.error(f"Error inserting player revived event: {e}")
    finally:
        cursor.close()

def insert_ability_used(connection, event_data):
    """
    Inserts an ability used event into the database.
    """
    cursor = connection.cursor()
    
    try:
        # Extract fields from event_data
        platform_game_id = event_data["platformGameId"]
        player_id = event_data["abilityUsed"]["playerId"]["value"]
        ability_guid = event_data["abilityUsed"]["ability"]["fallback"]["guid"]
        inventory_slot = event_data["abilityUsed"]["ability"]["fallback"]["inventorySlot"]["slot"]
        charges_consumed = event_data["abilityUsed"]["chargesConsumed"]

        cursor.execute("""
            INSERT INTO ability_used (platform_game_id, player_id, ability_guid, inventory_slot, charges_consumed)
            VALUES (%s, %s, %s, %s, %s);
        """, (platform_game_id, player_id, ability_guid, inventory_slot, charges_consumed))
        
        connection.commit()
        print(f"Inserted ability used event for player {player_id}")

    except KeyError as e:
        # Skip the event and log error if any required field is missing
        print(f"Skipping ability used event due to missing field: {e}")
        logging.error(f"Skipping ability used event due to missing field: {e}")
    except Exception as e:
        connection.rollback()
        print(f"Error inserting ability used event: {e}")
        logging.error(f"Error inserting ability used event: {e}")
    finally:
        cursor.close()

def populate_events(tournament_type, year):
    """
    Populates the event-specific tables by processing game files from a given tournament and year.
    """
    connection = create_connection()
    if connection is None:
        print("Could not connect to the database.")
        return

    games_dir = os.path.join(BASE_DATA_DIR, tournament_type, 'games', year)

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
                    insert_player_died(connection, event)
                elif "spikeStatus" in event:
                    insert_spike_status(connection, event)
                elif "damageEvent" in event:
                    insert_damage_event(connection, event)
                elif "playerRevived" in event:
                    insert_player_revived(connection, event)
                elif "abilityUsed" in event:
                    insert_ability_used(connection, event)

    connection.close()

if __name__ == "__main__":
    """
    Main script entry point.
    Prompts user for tournament type and year, and processes events for the selected tournament.
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
