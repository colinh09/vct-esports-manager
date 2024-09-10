import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from ../.env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Retrieve Supabase credentials from the environment
url = os.getenv("SUPA_URL")
api_key = os.getenv("SUPA_API_KEY")

# Initialize the Supabase client
supabase: Client = create_client(url, api_key)

# Helper function to load JSON data
def load_json_data(filepath):
    with open(filepath, 'r') as file:
        data = json.load(file)
    return data

# Function to rename 'id' field based on the table being populated
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

# Function to insert or update data for players/teams with composite keys
def upsert_data_with_composite_key(table, data, tournament_type):
    for item in data:
        if table == 'players':
            item['tournament_type'] = tournament_type
            primary_keys = {
                'player_id': item['player_id'],
                'tournament_type': tournament_type,
                'home_team_id': item['home_team_id']
            }
        elif table == 'teams':
            item['tournament_type'] = tournament_type
            primary_keys = {
                'team_id': item['team_id'],
                'tournament_type': tournament_type,
                'home_league_id': item['home_league_id']
            }
        else:
            # Add handling for other tables like 'tournaments', etc.
            continue
        
        # Perform the upsert using the correct composite keys
        response = supabase.table(table).upsert(item, on_conflict=list(primary_keys.keys())).execute()
        
        if response.status_code != 201:
            print(f"Error upserting data into {table}: {response}")
        else:
            print(f"Successfully upserted data into {table}")

# Main function to handle table population
def populate_table(table, tournament):
    filepath = f"../data/{tournament}/esports-data/{table}.json"
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    
    data = load_json_data(filepath)
    data = rename_id_field(data, table)
    upsert_data_with_composite_key(table, data, tournament)

if __name__ == "__main__":
    # Prompt for the tournament name
    print("Available tournaments:")
    print("1: vct-international")
    print("2: vct-challengers")
    print("3: game-changers")
    
    tournament = input("\nEnter the tournament name (vct-international, vct-challengers, game-changers): ").strip()
    
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
        '5': 'mapping'
    }
    
    data_type = input("\nEnter the number corresponding to the data type you want to populate: ").strip()
    if data_type in data_type_map:
        table = data_type_map[data_type]
        populate_table(table, tournament)
    else:
        print("Invalid choice.")
