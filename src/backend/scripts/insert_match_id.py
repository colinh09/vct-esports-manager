import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

def create_connection():
    try:
        connection = psycopg2.connect(DATABASE_URL)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def add_match_id_column(connection):
    cursor = connection.cursor()
    try:
        cursor.execute("""
        ALTER TABLE game_mapping
        ADD COLUMN IF NOT EXISTS match_id VARCHAR(255);
        """)
        connection.commit()
        print("Successfully added match_id column to game_mapping table.")
    except Exception as e:
        connection.rollback()
        print(f"Error adding match_id column: {e}")
    finally:
        cursor.close()

def load_mapping_data_v2(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)

def update_game_mapping_with_match_id(connection, mapping_data):
    cursor = connection.cursor()
    for item in mapping_data:
        platform_game_id = item['platformGameId']
        match_id = item['matchId']
        
        try:
            cursor.execute("""
            UPDATE game_mapping
            SET match_id = %s
            WHERE platform_game_id = %s;
            """, (match_id, platform_game_id))
            connection.commit()
            print(f"Updated match_id for platform_game_id: {platform_game_id}")
        except Exception as e:
            connection.rollback()
            print(f"Error updating match_id for platform_game_id {platform_game_id}: {e}")
    
    cursor.close()

def main():
    connection = create_connection()
    if connection is None:
        return

    add_match_id_column(connection)

    tournaments = ['vct-international', 'vct-challengers', 'game-changers']
    
    for tournament in tournaments:
        filepath = os.path.join(BASE_DATA_DIR, tournament, 'esports-data', "mapping_data_v2.json")
        if os.path.exists(filepath):
            print(f"Processing {tournament} mapping data...")
            mapping_data = load_mapping_data_v2(filepath)
            update_game_mapping_with_match_id(connection, mapping_data)
        else:
            print(f"File not found: {filepath}")

    connection.close()
    print("Script execution completed.")

if __name__ == "__main__":
    main()