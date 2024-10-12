import os
import logging
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

# Set up main logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up detailed logging
detailed_logger = logging.getLogger('detailed_logger')
detailed_logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('detailed_player_updates.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
detailed_logger.addHandler(fh)

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("RDS_DATABASE_URL")

def connect_to_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Successfully connected to the database")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        raise

def get_unique_roles(cursor):
    cursor.execute("SELECT DISTINCT agent_role FROM player_mapping WHERE agent_role IS NOT NULL")
    roles = [row['agent_role'] for row in cursor.fetchall()]
    logger.info(f"Found unique roles: {roles}")
    return roles

def add_role_columns(cursor, roles):
    for role in roles:
        column_name = f"{role.lower().replace(' ', '_')}_percentage"
        try:
            cursor.execute(
                sql.SQL("ALTER TABLE players ADD COLUMN IF NOT EXISTS {} NUMERIC(5,2)").format(
                    sql.Identifier(column_name)
                )
            )
            logger.info(f"Added column {column_name} to players table")
        except Exception as e:
            logger.error(f"Error adding column {column_name}: {e}")

def calculate_and_update_percentages(cursor, roles):
    cursor.execute("SELECT DISTINCT player_id, tournament_type FROM players")
    players = cursor.fetchall()

    for player in players:
        player_id = player['player_id']
        tournament_type = player['tournament_type']

        cursor.execute("""
            SELECT agent_role, COUNT(*) as role_count, 
                   (COUNT(*) * 100.0 / SUM(COUNT(*)) OVER()) as percentage
            FROM player_mapping
            WHERE player_id = %s AND tournament_type = %s AND agent_role IS NOT NULL
            GROUP BY agent_role
        """, (player_id, tournament_type))
        role_counts = cursor.fetchall()

        detailed_logger.debug(f"Player {player_id} in {tournament_type} - Raw counts and percentages:")
        for row in role_counts:
            detailed_logger.debug(f"  {row['agent_role']}: Count = {row['role_count']}, Percentage = {row['percentage']:.2f}%")

        role_percentages = {row['agent_role']: row['percentage'] for row in role_counts}

        update_query = sql.SQL("UPDATE players SET {} WHERE player_id = %s AND tournament_type = %s")
        set_items = []
        params = []

        for role in roles:
            column_name = f"{role.lower().replace(' ', '_')}_percentage"
            percentage = role_percentages.get(role, 0)  # Default to 0 if role not played
            set_items.append(sql.SQL("{} = %s").format(sql.Identifier(column_name)))
            params.append(round(percentage, 2))

        params.extend([player_id, tournament_type])  # Add these at the end of params list

        if set_items:
            update_query = update_query.format(sql.SQL(", ").join(set_items))
            try:
                cursor.execute(update_query, params)
                detailed_logger.debug(f"Updated percentages for player {player_id} in {tournament_type}")
                
                # Log the updated values
                cursor.execute(f"SELECT * FROM players WHERE player_id = %s AND tournament_type = %s", (player_id, tournament_type))
                updated_player = cursor.fetchone()
                detailed_logger.debug("Updated player data:")
                for key, value in updated_player.items():
                    if key.endswith('_percentage'):
                        detailed_logger.debug(f"  {key}: {value}")
                
            except Exception as e:
                detailed_logger.error(f"Error updating percentages for player {player_id} in {tournament_type}: {e}")

def check_column_types(cursor):
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'players'
    """)
    columns = cursor.fetchall()
    for column in columns:
        logger.info(f"Column {column['column_name']} is of type {column['data_type']}")

def main():
    conn = connect_to_db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            check_column_types(cursor)
            roles = get_unique_roles(cursor)
            add_role_columns(cursor, roles)
            calculate_and_update_percentages(cursor, roles)
        conn.commit()
        logger.info("Successfully updated player role percentages")
    except Exception as e:
        conn.rollback()
        logger.error(f"An error occurred: {e}")
    finally:
        conn.close()
        logger.info("Database connection closed")

if __name__ == "__main__":
    main()