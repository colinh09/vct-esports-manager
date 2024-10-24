import os
import json
import psycopg2
from datetime import datetime
import pytz
from dotenv import load_dotenv

load_dotenv()

# DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

def create_connection():
    """
    Establishes a connection to the PostgreSQL database using the provided connection string.
    Returns the connection object if successful, otherwise returns None.
    """
    try:
        connection = psycopg2.connect(DATABASE_URL)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def execute_schema(connection, schema_file):
    """
    Executes the SQL schema commands to create tables if they do not already exist.
    """
    with open(schema_file, 'r') as file:
        schema_sql = file.read()
    
    cursor = connection.cursor()
    try:
        cursor.execute(schema_sql)
        connection.commit()
        print("Schema successfully executed.")
    except Exception as e:
        connection.rollback()
        print(f"Error executing schema: {e}")
    finally:
        cursor.close()

def load_json_data(filepath):
    """
    Loads JSON data from a given file path.
    Returns the loaded JSON data as a dictionary or list.
    """
    with open(filepath, 'r') as file:
        data = json.load(file)
    return data

def record_exists(connection, table, id_columns, id_values):
    """
    Checks if a record with given ID values exists in the specified table.
    Returns True if the record exists, otherwise False.
    """
    cursor = connection.cursor()
    columns = ' AND '.join([f"{col} = %s" for col in id_columns])
    query = f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {columns})"
    cursor.execute(query, id_values)
    exists = cursor.fetchone()[0]
    cursor.close()
    return exists

def insert_player_data(connection, data, tournament_type):
    """
    Inserts or updates player data in the 'players' table based on the 'created_at' field.
    Updates if the new data has a more recent 'created_at' value for the same player_id, tournament_type, and handle.
    """
    cursor = connection.cursor()

    for item in data:
        item['tournament_type'] = tournament_type
        created_at = datetime.fromisoformat(item['created_at'].replace("Z", "+00:00")).replace(tzinfo=pytz.UTC)

        cursor.execute("""
            SELECT created_at
            FROM players
            WHERE player_id = %s AND tournament_type = %s AND handle = %s
        """, (item['player_id'], tournament_type, item['handle']))

        result = cursor.fetchone()

        if result:
            existing_created_at = result[0]
            if existing_created_at.tzinfo is None:
                existing_created_at = existing_created_at.replace(tzinfo=pytz.UTC)
            
            if created_at > existing_created_at:
                columns = ', '.join([f"{key} = %s" for key in item.keys()])
                query = f"""
                UPDATE players
                SET {columns}
                WHERE player_id = %s AND tournament_type = %s AND handle = %s
                """
                cursor.execute(query, list(item.values()) + [item['player_id'], tournament_type, item['handle']])
                connection.commit()
                print(f"Updated player {item['handle']} with more recent data.")
        else:
            columns = ', '.join(item.keys())
            values = ', '.join(['%s'] * len(item))
            query = f"""
            INSERT INTO players ({columns})
            VALUES ({values})
            """
            cursor.execute(query, list(item.values()))
            connection.commit()
            print(f"Inserted new player {item['handle']}.")

    cursor.close()

def insert_mapping_data(connection, data, tournament_type):
    """
    Inserts mapping data into 'game_mapping', 'player_mapping', and 'team_mapping' tables.
    Handles each mapping type separately, ensuring related records exist before insertion.
    """
    for item in data:
        platform_game_id = item.get('platformGameId')
        esports_game_id = item.get('esportsGameId')
        tournament_id = item.get('tournamentId')

        if not record_exists(connection, 'game_mapping', ['platform_game_id'], [platform_game_id]):
            game_mapping_data = {
                'platform_game_id': platform_game_id,
                'esports_game_id': esports_game_id,
                'tournament_id': tournament_id,
                'tournament_type': tournament_type
            }
            insert_data_to_db(connection, 'game_mapping', [game_mapping_data], tournament_type)

        player_mapping = item.get('participantMapping', {})
        for internal_player_id, player_id in player_mapping.items():
            if not record_exists(connection, 'players', ['player_id', 'tournament_type'], [player_id, tournament_type]):
                print(f"Skipping player mapping for internal_player_id {internal_player_id} as player {player_id} does not exist.")
                continue

            player_data = {
                'internal_player_id': internal_player_id,
                'player_id': player_id,
                'tournament_type': tournament_type,
                'platform_game_id': platform_game_id,
                'agent_guid': '' 
            }
            insert_data_to_db(connection, 'player_mapping', [player_data], tournament_type)

        team_mapping = item.get('teamMapping', {})
        for internal_team_id, team_id in team_mapping.items():
            if not record_exists(connection, 'teams', ['team_id', 'tournament_type'], [team_id, tournament_type]):
                print(f"Skipping team mapping for internal_team_id {internal_team_id} as team {team_id} does not exist.")
                continue

            team_data = {
                'internal_team_id': internal_team_id,
                'team_id': team_id,
                'tournament_type': tournament_type,
                'platform_game_id': platform_game_id
            }
            insert_data_to_db(connection, 'team_mapping', [team_data], tournament_type)

def insert_data_to_db(connection, table, data, tournament_type):
    """
    Inserts data into the specified table.
    If a conflict occurs, performs an update based on the primary key columns of the table.
    Ignores 'start_time' and 'end_time' fields.
    """
    cursor = connection.cursor()

    for item in data:
        item['tournament_type'] = tournament_type
        
        item.pop('start_time', None)
        item.pop('end_time', None)

        columns = ', '.join(item.keys())
        values = ', '.join(['%s'] * len(item))
        updates = ', '.join([f"{key} = EXCLUDED.{key}" for key in item.keys()])

        primary_keys = primary_key_columns(table)
        on_conflict = f"ON CONFLICT ({', '.join(primary_keys)}) DO UPDATE SET {updates}"

        query = f"""
        INSERT INTO {table} ({columns})
        VALUES ({values})
        {on_conflict};
        """
        
        try:
            cursor.execute(query, list(item.values()))
            connection.commit()
            print(f"Successfully upserted data into {table}")
        except Exception as e:
            connection.rollback()
            print(f"Error inserting data into {table}: {e}")

    cursor.close()

def primary_key_columns(table):
    """
    Returns the primary key columns for the specified table.
    Different tables have different primary key configurations.
    """
    pk_map = {
        'leagues': ['league_id', 'tournament_type'],
        'tournaments': ['tournament_id', 'tournament_type'],
        'teams': ['team_id', 'tournament_type'],
        'players': ['player_id', 'tournament_type', 'handle'],
        'game_mapping': ['platform_game_id'],
        'player_mapping': ['internal_player_id', 'platform_game_id'],
        'team_mapping': ['internal_team_id', 'platform_game_id']
    }
    return pk_map.get(table, ['id'])

def populate_table(table, tournament, year):
    """
    Main function to handle the population of data into the specified table.
    Loads data from a JSON file and either inserts or updates it in the corresponding database table.
    Special handling is applied for 'mapping_data' and 'players' tables.
    """
    connection = create_connection()
    if connection is None:
        return

    filepath = os.path.join(BASE_DATA_DIR, tournament, 'esports-data', f"{table}.json")
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    data = load_json_data(filepath)

    if table == 'mapping_data':
        insert_mapping_data(connection, data, tournament)
    elif table == 'players':
        data = rename_id_field(data, table)
        insert_player_data(connection, data, tournament)
    else:
        data = rename_id_field(data, table)
        insert_data_to_db(connection, table, data, tournament)

    connection.close()

def rename_id_field(data, table):
    """
    Renames the 'id' field in the data to match the expected primary key column for the given table.
    For example, 'id' in the 'players' table is renamed to 'player_id'.
    """
    id_field_mapping = {
        'players': 'player_id',
        'teams': 'team_id',
        'tournaments': 'tournament_id',
        'leagues': 'league_id'
    }

    if table in id_field_mapping:
        id_field = id_field_mapping[table]
        for item in data:
            if 'id' in item and id_field not in item:
                item[id_field] = item.pop('id')
    return data

def populate_all_tables(tournament, year):
    """
    Populates all tables in the correct order.
    """
    tables = ['leagues', 'tournaments', 'teams', 'players', 'mapping_data']
    for table in tables:
        print(f"\nPopulating {table} table...")
        populate_table(table, tournament, year)

if __name__ == "__main__":
    """
    The main entry point for the script. Prompts the user for inputs such as tournament type, year, 
    and data type to populate, and calls the appropriate functions to handle the data insertion.
    """
    print("Available tournaments:")
    print("1: vct-international")
    print("2: vct-challengers")
    print("3: game-changers")

    tournament_map = {
        '1': 'vct-international',
        '2': 'vct-challengers',
        '3': 'game-changers'
    }

    tournament_choice = input("\nEnter the number corresponding to the tournament: ").strip()
    tournament = tournament_map.get(tournament_choice)

    if not tournament:
        print("Invalid tournament choice.")
        exit()

    year = input("Enter the tournament year (YYYY): ").strip()

    print("\nAvailable data types to populate:")
    print("1: Leagues")
    print("2: Tournaments")
    print("3: Players")
    print("4: Teams")
    print("5: Mapping")
    print("6: All")

    data_type_map = {
        '1': 'leagues',
        '2': 'tournaments',
        '3': 'players',
        '4': 'teams',
        '5': 'mapping_data',
        '6': 'all'
    }

    data_type = input("\nEnter the number corresponding to the data type you want to populate: ").strip()
    if data_type in data_type_map:
        table = data_type_map[data_type]

        # Establish connection and execute schema commands
        connection = create_connection()
        # if connection is not None:
        #     execute_schema(connection, '../db/schema.sql')
        #     connection.close()

        # Populate the selected table or all tables
        if table == 'all':
            populate_all_tables(tournament, year)
        else:
            populate_table(table, tournament, year)
    else:
        print("Invalid choice.")