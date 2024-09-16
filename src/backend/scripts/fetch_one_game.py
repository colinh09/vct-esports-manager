import os
import ijson
import psycopg2
import logging
import requests
import json
import gzip
import shutil
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DATA_DIR = "/home/colin/vct-esports-manager/data"
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

logging.basicConfig(
    filename="single_game_processor.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        return None

def download_and_process_game(tournament, year, platform_game_id, connection):
    directory = f"{BASE_DATA_DIR}/{tournament}/games/{year}"
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_path = f"{directory}/{platform_game_id}.json"
    full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{platform_game_id}.json.gz"

    try:
        response = requests.get(full_url)
        if response.status_code == 200:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                with open(file_path, 'wb') as output_file:
                    shutil.copyfileobj(gzipped_file, output_file)
            logging.info(f"Downloaded: {platform_game_id}.json")

            event_counts = process_json_file(file_path, connection)
            if event_counts is None:
                logging.info(f"Skipped processing for game {platform_game_id} due to foreign key constraint.")
            else:
                logging.info(f"Processed: {platform_game_id}.json")
                logging.info(f"Event counts: {event_counts}")

            os.remove(file_path)
            logging.info(f"Deleted: {platform_game_id}.json")

            return event_counts
        else:
            logging.error(f"Failed to download {platform_game_id}.json")
            return {}
    except Exception as e:
        logging.error(f"Error processing game {platform_game_id}: {e}")
        return {}

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

            logging.info("Processing JSON file...")
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
                    logging.error(f"Foreign key violation for game {platform_game_id}: {fk_error}")
                    connection.rollback()
                    return None

            logging.info("Finished processing events, updating player stats...")
            if final_snapshot and 'players' in final_snapshot:
                update_player_stats(connection, platform_game_id, final_snapshot['players'])
            else:
                logging.warning(f"No valid final snapshot found in file {filepath}")

            return event_counts

    except Exception as e:
        logging.error(f"Error processing file {filepath}: {e}")
        return None

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
        logging.info("Processed configuration event and updated agent GUIDs")
    except Exception as e:
        connection.rollback()
        logging.error(f"Error processing configuration event: {e}")
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
        logging.error(f"Error inserting player died event: {e}")
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
        logging.error(f"Error inserting spike status event: {e}")
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
        logging.error(f"Error inserting damage event: {e}")
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
        logging.error(f"Error inserting player revived event: {e}")
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
        logging.error(f"Error inserting ability used event: {e}")
    finally:
        cursor.close()

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
        logging.info("Updated player stats successfully")
    except Exception as e:
        connection.rollback()
        logging.error(f"Error updating player stats: {e}")
    finally:
        cursor.close()

def process_single_game(tournament_type, year, platform_game_id):
    connection = create_connection()
    if connection is None:
        logging.error("Could not connect to the database.")
        return

    logging.info(f"Processing game: {platform_game_id}")
    event_counts = download_and_process_game(tournament_type, year, platform_game_id, connection)
    
    if event_counts is not None:
        logging.info(f"Successfully processed game {platform_game_id}")
        logging.info(f"Event counts: {event_counts}")
    else:
        logging.error(f"Failed to process game {platform_game_id}")

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
        platform_game_id = input("Enter the platform game ID to process: ").strip()

        if year.isdigit():
            logging.info(f"Starting processing for game {platform_game_id} in {tournament_type} {year}")
            process_single_game(tournament_type, year, platform_game_id)
            logging.info(f"Completed processing for game {platform_game_id}")
        else:
            print("Invalid year input.")
            logging.error(f"Invalid year input: {year}")
    else:
        print("Invalid selection.")
        logging.error(f"Invalid tournament selection: {tournament_choice}")