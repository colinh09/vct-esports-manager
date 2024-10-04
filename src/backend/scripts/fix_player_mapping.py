import os
import json
import psycopg2
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(filename='valorant_db_fixer.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Database connection
DATABASE_URL = os.getenv("RDS_DATABASE_URL")
BASE_DATA_DIR = os.getenv("BASE_DATA_DIR")

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        logging.error(f"Error connecting to database: {e}")
        return None

def load_json_data(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)

def get_tournament_type(platform_game_id):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tournament_type FROM game_mapping WHERE platform_game_id = %s", (platform_game_id,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

def check_and_update_player_mapping(conn, internal_player_id, platform_game_id):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM player_mapping 
        WHERE internal_player_id = %s AND platform_game_id = %s
    """, (internal_player_id, platform_game_id))
    
    if cursor.fetchone() is None:
        logging.info(f"Player mapping not found for internal_player_id: {internal_player_id}, platform_game_id: {platform_game_id}")
        
        tournament_type = get_tournament_type(platform_game_id)
        if not tournament_type:
            logging.warning(f"Tournament type not found for platform_game_id: {platform_game_id}")
            return None

        # Check mapping.json
        mapping_file = os.path.join(BASE_DATA_DIR, tournament_type, 'esports-data', 'mapping_data.json')
        mapping_data = load_json_data(mapping_file)
        
        for game in mapping_data:
            if game['platformGameId'] == platform_game_id:
                for internal_id, player_id in game['participantMapping'].items():
                    if internal_id == internal_player_id:
                        # Insert into player_mapping
                        cursor.execute("""
                            INSERT INTO player_mapping (internal_player_id, player_id, tournament_type, platform_game_id)
                            VALUES (%s, %s, %s, %s)
                        """, (internal_player_id, player_id, tournament_type, platform_game_id))
                        conn.commit()
                        logging.info(f"Added player mapping for internal_player_id: {internal_player_id}, player_id: {player_id}")
                        return player_id
        
        logging.warning(f"Player mapping not found in JSON for internal_player_id: {internal_player_id}")
    else:
        logging.info(f"Player mapping found for internal_player_id: {internal_player_id}")
    
    cursor.close()
    return None

def check_and_update_player(conn, player_id, tournament_type):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players WHERE player_id = %s AND tournament_type = %s", (player_id, tournament_type))
    
    if cursor.fetchone() is None:
        logging.info(f"Player not found in players table for player_id: {player_id}")
        
        # Check players.json
        players_file = os.path.join(BASE_DATA_DIR, tournament_type, 'esports-data', 'players.json')
        players_data = load_json_data(players_file)
        
        for player in players_data:
            if player['id'] == player_id:
                # Insert into players table
                cursor.execute("""
                    INSERT INTO players (player_id, tournament_type, handle, first_name, last_name, status, photo_url, home_team_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (player['id'], tournament_type, player['handle'], player['first_name'], player['last_name'], 
                      player['status'], player['photo_url'], player['home_team_id'], player['created_at'], player['updated_at']))
                conn.commit()
                logging.info(f"Added player to players table: {player['id']}")
                return
        
        logging.warning(f"Player not found in JSON for player_id: {player_id}")
    else:
        logging.info(f"Player found in players table for player_id: {player_id}")
    
    cursor.close()

def fix_player_died_table():
    conn = create_connection()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    # Find entries with null true_deceased_id or true_killer_id
    cursor.execute("""
        SELECT platform_game_id, deceased_id, killer_id, true_deceased_id, true_killer_id 
        FROM player_died 
        WHERE true_deceased_id IS NULL OR true_killer_id IS NULL
    """)
    
    for row in cursor.fetchall():
        platform_game_id, deceased_id, killer_id, true_deceased_id, true_killer_id = row
        
        if true_deceased_id is None:
            player_id = check_and_update_player_mapping(conn, deceased_id, platform_game_id)
            if player_id:
                tournament_type = get_tournament_type(platform_game_id)
                check_and_update_player(conn, player_id, tournament_type)
                cursor.execute("""
                    UPDATE player_died 
                    SET true_deceased_id = %s 
                    WHERE platform_game_id = %s AND deceased_id = %s
                """, (player_id, platform_game_id, deceased_id))
                conn.commit()
        
        if true_killer_id is None:
            player_id = check_and_update_player_mapping(conn, killer_id, platform_game_id)
            if player_id:
                tournament_type = get_tournament_type(platform_game_id)
                check_and_update_player(conn, player_id, tournament_type)
                cursor.execute("""
                    UPDATE player_died 
                    SET true_killer_id = %s 
                    WHERE platform_game_id = %s AND killer_id = %s
                """, (player_id, platform_game_id, killer_id))
                conn.commit()
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    logging.info("Starting database fixing process")
    fix_player_died_table()
    logging.info("Database fixing process completed")