import os
import ijson
import psycopg2
import logging
from logging.handlers import RotatingFileHandler
import requests
import json
import gzip
import shutil
import time
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

# Set up logging for non-error events
info_logger = logging.getLogger('info_logger')
info_logger.setLevel(logging.INFO)
info_handler = RotatingFileHandler('data_processor.log', maxBytes=100*1024*1024, backupCount=5)
info_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
info_handler.setFormatter(info_formatter)
info_logger.addHandler(info_handler)

# Set up logging for error events
error_logger = logging.getLogger('error_logger')
error_logger.setLevel(logging.ERROR)
error_handler = RotatingFileHandler('error.log', maxBytes=100*1024*1024, backupCount=5)
error_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
error_handler.setFormatter(error_formatter)
error_logger.addHandler(error_handler)

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        error_logger.error(f"Error connecting to database: {e}")
        return None

def download_and_process_game(tournament, year, platform_game_id, connection):
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT 1 FROM game_mapping WHERE platform_game_id = %s", (platform_game_id,))
        if cursor.fetchone() is None:
            info_logger.info(f"Skipping game {platform_game_id}: Not present in game_mapping table")
            return None

        directory = f"{BASE_DATA_DIR}/{tournament}/games/{year}"
        if not os.path.exists(directory):
            os.makedirs(directory)

        file_path = f"{directory}/{platform_game_id}.json"
        full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{platform_game_id}.json.gz"

        response = requests.get(full_url)
        if response.status_code == 200:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                with open(file_path, 'wb') as output_file:
                    shutil.copyfileobj(gzipped_file, output_file)
            info_logger.info(f"Downloaded: {platform_game_id}.json")

            event_counts = process_json_file(file_path, connection)
            info_logger.info(f"Processed: {platform_game_id}.json")
            info_logger.info(f"Event counts: {event_counts}")

            os.remove(file_path)
            info_logger.info(f"Deleted: {platform_game_id}.json")

            return event_counts
        else:
            error_logger.error(f"Failed to download {platform_game_id}.json")
            return None
    except Exception as e:
        error_logger.error(f"Error processing game {platform_game_id}: {e}")
        return None
    finally:
        cursor.close()

def process_json_file(filepath, connection):
    try:
        with open(filepath, 'rb') as file:
            events = ijson.items(file, 'item')
            final_snapshot = None
            platform_game_id = None
            processed_config = False
            event_counts = {
                'configuration': 0,
                'player_died': 0,
                'spike_status': 0,
                'damage_event': 0,
                'player_revived': 0,
                'ability_used': 0
            }

            info_logger.info("Processing JSON file...")
            for event in events:
                if 'snapshot' in event:
                    final_snapshot = event['snapshot']
                    platform_game_id = event.get('platformGameId')

                try:
                    if "configuration" in event and not processed_config:
                        process_configuration_event(connection, event)
                        processed_config = True
                        event_counts['configuration'] += 1
                    elif "playerDied" in event:
                        insert_player_died(connection, event)
                        event_counts['player_died'] += 1
                    elif "spikeStatus" in event:
                        insert_spike_status(connection, event)
                        event_counts['spike_status'] += 1
                    elif "damageEvent" in event:
                        insert_damage_event(connection, event)
                        event_counts['damage_event'] += 1
                    elif "playerRevived" in event:
                        insert_player_revived(connection, event)
                        event_counts['player_revived'] += 1
                    elif "abilityUsed" in event:
                        insert_ability_used(connection, event)
                        event_counts['ability_used'] += 1
                except psycopg2.errors.ForeignKeyViolation as fk_error:
                    error_logger.error(f"Foreign key violation for game {platform_game_id}: {fk_error}")
                    connection.rollback()
                    return None

            info_logger.info("Finished processing events, updating player stats...")
            if final_snapshot and 'players' in final_snapshot:
                update_player_stats(connection, platform_game_id, final_snapshot['players'])
            else:
                error_logger.warning(f"No valid final snapshot found in file {filepath}")

            return event_counts

    except Exception as e:
        error_logger.error(f"Error processing file {filepath}: {e}")
        return None

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
            
        connection.commit()
        info_logger.info("Updated player stats successfully")
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error updating player stats: {e}")
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
                WHERE internal_player_id = %s AND platform_game_id = %s;
            """, (agent_guid, internal_player_id, platform_game_id))
            
        connection.commit()
        info_logger.info("Processed configuration event and updated agent GUIDs")
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error processing configuration event: {e}")
    finally:
        cursor.close()

def insert_player_died(connection, event_data):
    cursor = connection.cursor()
    try:
        platform_game_id = event_data["platformGameId"]
        deceased_id = event_data["playerDied"]["deceasedId"]["value"]
        killer_id = event_data["playerDied"]["killerId"]["value"]
        weapon_guid = event_data["playerDied"].get("weapon", {}).get("fallback", {}).get("guid", None)

        cursor.execute("""
            INSERT INTO player_died (platform_game_id, deceased_id, killer_id, weapon_guid)
            VALUES (%s, %s, %s, %s)
            RETURNING event_id;
        """, (platform_game_id, deceased_id, killer_id, weapon_guid))
        
        event_id = cursor.fetchone()[0]

        assistants = event_data["playerDied"].get("assistants", [])
        for assistant in assistants:
            assister_id = assistant["assistantId"]["value"]
            cursor.execute("""
                INSERT INTO player_assists (platform_game_id, assister_id)
                VALUES (%s, %s);
            """, (platform_game_id, assister_id))

        connection.commit()
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error inserting player died event: {e}")
    finally:
        cursor.close()

def insert_spike_status(connection, event_data):
    cursor = connection.cursor()
    try:
        platform_game_id = event_data["platformGameId"]
        carrier_id = event_data["spikeStatus"]["carrier"]["value"]
        status = event_data["spikeStatus"]["status"]

        cursor.execute("""
            INSERT INTO spike_status (platform_game_id, carrier_id, status)
            VALUES (%s, %s, %s);
        """, (platform_game_id, carrier_id, status))
        
        connection.commit()
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error inserting spike status event: {e}")
    finally:
        cursor.close()

def insert_damage_event(connection, event_data):
    cursor = connection.cursor()
    try:
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
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error inserting damage event: {e}")
    finally:
        cursor.close()

def insert_player_revived(connection, event_data):
    cursor = connection.cursor()
    try:
        platform_game_id = event_data["platformGameId"]
        revived_by_id = event_data["playerRevived"]["revivedById"]["value"]
        revived_id = event_data["playerRevived"]["revivedId"]["value"]

        cursor.execute("""
            INSERT INTO player_revived (platform_game_id, revived_by_id, revived_id)
            VALUES (%s, %s, %s);
        """, (platform_game_id, revived_by_id, revived_id))
        
        connection.commit()
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error inserting player revived event: {e}")
    finally:
        cursor.close()

def insert_ability_used(connection, event_data):
    cursor = connection.cursor()
    try:
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
    except Exception as e:
        connection.rollback()
        error_logger.error(f"Error inserting ability used event: {e}")
    finally:
        cursor.close()

def populate_data(tournament_type, year, start_game=0):
    connection = create_connection()
    if connection is None:
        error_logger.error("Could not connect to the database.")
        return

    mapping_file = f"{BASE_DATA_DIR}/{tournament_type}/esports-data/mapping_data.json"
    
    if not os.path.isfile(mapping_file):
        error_logger.error(f"Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, "r") as json_file:
        mappings_data = json.load(json_file)

    total_event_counts = {
        'configuration': 0,
        'player_died': 0,
        'spike_status': 0,
        'damage_event': 0,
        'player_revived': 0,
        'ability_used': 0
    }

    for index, esports_game in enumerate(mappings_data[start_game:], start_game + 1):
        platform_game_id = esports_game["platformGameId"]
        info_logger.info(f"Processing game {index}/{len(mappings_data)}: {platform_game_id}")
        
        event_counts = download_and_process_game(tournament_type, year, platform_game_id, connection)
        
        if event_counts is not None:
            for event_type, count in event_counts.items():
                total_event_counts[event_type] += count

        if index % 10 == 0:
            info_logger.info(f"----- Processed {index} games")
            info_logger.info(f"Current total event counts: {total_event_counts}")

    info_logger.info("Data processing complete. Total event counts:")
    for event_type, count in total_event_counts.items():
        info_logger.info(f"{event_type}: {count}")

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
        start_game = int(input("Enter the game number to start from (0 to start from beginning): ").strip())

        if year.isdigit():
            info_logger.info(f"Starting data population for {tournament_type} {year} from game {start_game}")
            populate_data(tournament_type, year, start_game)
            info_logger.info(f"Completed data population for {tournament_type} {year}")
        else:
            print("Invalid year input.")
            error_logger.error(f"Invalid year input: {year}")
    else:
        print("Invalid selection.")
        error_logger.error(f"Invalid tournament selection: {tournament_choice}")