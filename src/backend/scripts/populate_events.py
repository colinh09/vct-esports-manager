import os
import ijson
import psycopg2
import logging
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

logging.basicConfig(
    filename="errorlogs_combined.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
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
                DROP COLUMN IF EXISTS combat_score,
                DROP COLUMN IF EXISTS agent_guid;
            """)
            print("Dropped existing stat columns.")

        cursor.execute("""
            ALTER TABLE player_mapping
            ADD COLUMN IF NOT EXISTS kills INTEGER,
            ADD COLUMN IF NOT EXISTS deaths INTEGER,
            ADD COLUMN IF NOT EXISTS assists INTEGER,
            ADD COLUMN IF NOT EXISTS combat_score INTEGER,
            ADD COLUMN IF NOT EXISTS agent_guid TEXT;
        """)
        connection.commit()
        print("Ensured necessary columns exist in player_mapping table.")
    except Exception as e:
        connection.rollback()
        print(f"Error ensuring columns: {e}")
        logging.error(f"Error ensuring columns: {e}")
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

            for event in events:
                if 'snapshot' in event:
                    final_snapshot = event['snapshot']
                    platform_game_id = event.get('platformGameId')

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

            if final_snapshot and 'players' in final_snapshot:
                update_player_stats(connection, platform_game_id, final_snapshot['players'])
            else:
                print(f"No valid final snapshot found in file {filepath}")

            return event_counts

    except Exception as e:
        print(f"Error processing file {filepath}: {e}")
        logging.error(f"Error processing file {filepath}: {e}")
        return {}

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
    except Exception as e:
        connection.rollback()
        print(f"Error updating player stats: {e}")
        logging.error(f"Error updating player stats: {e}")
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
    except Exception as e:
        connection.rollback()
        print(f"Error processing configuration event: {e}")
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

def populate_data(tournament_type, year, reset_columns):
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

    total_event_counts = {
        'configuration': 0,
        'player_died': 0,
        'spike_status': 0,
        'damage_event': 0,
        'player_revived': 0,
        'ability_used': 0
    }

    for game_file in os.listdir(games_dir):
        if game_file.endswith(".json"):
            file_path = os.path.join(games_dir, game_file)
            print(f"Processing file: {file_path}")
            event_counts = process_json_file(file_path, connection)
            for event_type, count in event_counts.items():
                total_event_counts[event_type] += count

    print("Data processing complete. Total event counts:")
    for event_type, count in total_event_counts.items():
        print(f"{event_type}: {count}")

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
            populate_data(tournament_type, year, reset_columns)
        else:
            print("Invalid year input.")
            logging.error(f"Invalid year input: {year}")
    else:
        print("Invalid selection.")
        logging.error(f"Invalid tournament selection: {tournament_choice}")