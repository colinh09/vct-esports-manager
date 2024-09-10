import json
import os
import psycopg2
from psycopg2 import sql
from datetime import datetime

# Database connection string for local PostgreSQL
DATABASE_URL = "postgresql://postgres:password@localhost:5432/vct-manager"

# Connect to your PostgreSQL database using the connection string
def create_connection():
    try:
        connection = psycopg2.connect(DATABASE_URL)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

# Helper function to load JSON data
def load_json_data(filepath):
    with open(filepath, 'r') as file:
        data = json.load(file)
    return data

# Function to check if a record exists in a table
def record_exists(connection, table, id_column, id_value):
    cursor = connection.cursor()
    query = f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {id_column} = %s)"
    cursor.execute(query, (id_value,))
    exists = cursor.fetchone()[0]
    cursor.close()
    return exists

# Function to insert or update player data based on the most recent 'created_at'
def insert_player_data(connection, data, tournament_type):
    cursor = connection.cursor()

    for item in data:
        item['tournament_type'] = tournament_type

        # Convert created_at to proper datetime object
        created_at = datetime.fromisoformat(item['created_at'].replace("Z", "+00:00"))

        # Check if the player already exists in the database for this tournament_type
        cursor.execute("""
            SELECT created_at
            FROM players
            WHERE player_id = %s AND tournament_type = %s
        """, (item['player_id'], tournament_type))

        result = cursor.fetchone()

        # If the player exists, only update if the new entry's created_at is more recent
        if result:
            existing_created_at = result[0]
            if created_at > existing_created_at:
                # Update the player with the new data
                columns = ', '.join([f"{key} = %s" for key in item.keys()])
                query = f"""
                UPDATE players
                SET {columns}
                WHERE player_id = %s AND tournament_type = %s
                """
                cursor.execute(query, list(item.values()) + [item['player_id'], tournament_type])
                connection.commit()
                print(f"Updated player {item['handle']} with more recent data.")
        else:
            # Insert new player
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

# Function to handle insertion of mapping data into player_mapping and team_mapping
def insert_mapping_data(connection, data, tournament_type):
    for item in data:
        platform_game_id = item.get('platformGameId')
        esports_game_id = item.get('esportsGameId')
        tournament_id = item.get('tournamentId')

        # Step 1: Check and insert the game mapping (game_mapping)
        if not record_exists(connection, 'game_mapping', 'platform_game_id', platform_game_id):
            game_mapping_data = {
                'platform_game_id': platform_game_id,
                'esports_game_id': esports_game_id,
                'tournament_id': tournament_id,
                'tournament_type': tournament_type
            }
            insert_data_to_db(connection, 'game_mapping', [game_mapping_data], tournament_type)

        # Step 2: Insert the player mapping (participantMapping)
        player_mapping = item.get('participantMapping', {})

        for internal_player_id, player_id in player_mapping.items():
            # Skip if the player doesn't exist in the players table
            if not record_exists(connection, 'players', 'player_id', player_id):
                print(f"Skipping player mapping for internal_player_id {internal_player_id} as player {player_id} does not exist.")
                continue

            player_data = {
                'internal_player_id': internal_player_id,
                'player_id': player_id,
                'tournament_type': tournament_type,
                'platform_game_id': platform_game_id
            }
            # Insert the player mapping
            insert_data_to_db(connection, 'player_mapping', [player_data], tournament_type)

        # Step 3: Insert the team mapping (teamMapping)
        team_mapping = item.get('teamMapping', {})

        for internal_team_id, team_id in team_mapping.items():
            # Skip if the team doesn't exist in the teams table
            if not record_exists(connection, 'teams', 'team_id', team_id):
                print(f"Skipping team mapping for internal_team_id {internal_team_id} as team {team_id} does not exist.")
                continue

            team_data = {
                'internal_team_id': internal_team_id,
                'team_id': team_id,
                'tournament_type': tournament_type,
                'platform_game_id': platform_game_id
            }
            # Insert the team mapping
            insert_data_to_db(connection, 'team_mapping', [team_data], tournament_type)

# Function to insert data into the table using psycopg2 and handle upsert (insert or update)
def insert_data_to_db(connection, table, data, tournament_type):
    cursor = connection.cursor()

    # Loop over each item and insert or update in case of conflict
    for item in data:
        item['tournament_type'] = tournament_type

        columns = ', '.join(item.keys())
        values = ', '.join(['%s'] * len(item))
        updates = ', '.join([f"{key} = EXCLUDED.{key}" for key in item.keys()])

        query = f"""
        INSERT INTO {table} ({columns})
        VALUES ({values})
        ON CONFLICT ({', '.join(primary_key_columns(table))})
        DO UPDATE SET {updates};
        """
        
        try:
            cursor.execute(query, list(item.values()))
            connection.commit()
            print(f"Successfully upserted data into {table}")
        except Exception as e:
            connection.rollback()
            print(f"Error inserting data into {table}: {e}")

    cursor.close()

# Function to determine primary key columns based on table
def primary_key_columns(table):
    if table == 'players':
        return ['player_id', 'tournament_type']
    elif table == 'teams':
        return ['team_id', 'tournament_type']
    elif table == 'tournaments':
        return ['tournament_id', 'tournament_type']
    elif table == 'leagues':
        return ['league_id', 'tournament_type']
    elif table == 'team_mapping':
        return ['internal_team_id', 'platform_game_id']
    elif table == 'player_mapping':
        return ['internal_player_id', 'platform_game_id']
    elif table == 'game_mapping':
        return ['platform_game_id']
    else:
        return ['id']

# Main function to handle table population
def populate_table(table, tournament):
    connection = create_connection()
    if connection is None:
        return

    filepath = f"../data/{tournament}/esports-data/{table}.json"
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    data = load_json_data(filepath)

    if table == 'mapping_data':  # Special handling for mapping_data
        insert_mapping_data(connection, data, tournament)
    else:
        data = rename_id_field(data, table)
        insert_data_to_db(connection, table, data, tournament)

    connection.close()

# Helper function to rename 'id' field based on the table being populated
def rename_id_field(data, table):
    id_field_mapping = {
        'players': 'player_id',
        'teams': 'team_id',
        'tournaments': 'tournament_id',
    }

    if table in id_field_mapping:
        id_field = id_field_mapping[table]
        for item in data:
            if 'id' in item and id_field not in item:
                item[id_field] = item.pop('id')
    return data

if __name__ == "__main__":
    # Prompt for the tournament name
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

    # Prompt for the data type
    print("\nAvailable data types to populate:")
    print("1: Leagues")
    print("2: Tournaments")
    print("3: Players")
    print("4: Teams")
    print("5: Mapping")

    data_type_map = {
        '1': 'leagues',
        '2': 'tournaments',
        '3': 'players',
        '4': 'teams',
        '5': 'mapping_data'
    }

    data_type = input("\nEnter the number corresponding to the data type you want to populate: ").strip()
    if data_type in data_type_map:
        table = data_type_map[data_type]
        populate_table(table, tournament)
    else:
        print("Invalid choice.")
