import os
import json
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up error logging
error_logger = logging.getLogger('error_logger')
error_logger.setLevel(logging.ERROR)
error_handler = logging.FileHandler('errors.txt')
error_handler.setLevel(logging.ERROR)
error_logger.addHandler(error_handler)

def load_agent_mappings():
    with open('agents.mapping', 'r') as f:
        return json.load(f)

def check_and_create_columns(cursor):
    try:
        # Check if columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='player_mapping' AND column_name IN ('agent_name', 'agent_role')
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]

        # Add columns if they don't exist
        if 'agent_name' not in existing_columns:
            cursor.execute("ALTER TABLE player_mapping ADD COLUMN agent_name VARCHAR")
            logger.info("Added agent_name column to player_mapping table")

        if 'agent_role' not in existing_columns:
            cursor.execute("ALTER TABLE player_mapping ADD COLUMN agent_role VARCHAR")
            logger.info("Added agent_role column to player_mapping table")

    except Exception as e:
        error_logger.error(f"Error checking or creating columns: {str(e)}")
        raise

def update_player_mapping(conn, cursor, agent_mappings):
    try:
        # First, check and create columns if necessary
        check_and_create_columns(cursor)

        # Fetch all rows from player_mapping table
        cursor.execute("SELECT internal_player_id, agent_guid FROM player_mapping")
        rows = cursor.fetchall()

        for row in rows:
            internal_player_id, agent_guid = row
            if agent_guid:
                # Convert to lowercase for mapping lookup, but keep original for update
                agent_guid_lower = agent_guid.lower()
                if agent_guid_lower in agent_mappings:
                    agent_name = agent_mappings[agent_guid_lower]['name']
                    agent_role = agent_mappings[agent_guid_lower]['role']

                    # Update the row (use original agent_guid which is uppercase)
                    update_query = sql.SQL("""
                        UPDATE player_mapping 
                        SET agent_name = %s, agent_role = %s 
                        WHERE internal_player_id = %s AND agent_guid = %s
                    """)
                    cursor.execute(update_query, (agent_name, agent_role, internal_player_id, agent_guid))
                    conn.commit()

                    logger.info(f"Updated player {internal_player_id} with agent {agent_name} ({agent_role})")
                else:
                    error_logger.error(f"Agent GUID {agent_guid} not found in mappings for player {internal_player_id}")
            else:
                error_logger.error(f"No agent GUID for player {internal_player_id}")

    except Exception as e:
        error_logger.error(f"Error updating player_mapping: {str(e)}")
        conn.rollback()

def main():
    load_dotenv()
    database_url = os.getenv('RDS_DATABASE_URL')

    if not database_url:
        error_logger.error("Database URL not found in .env file")
        return

    agent_mappings = load_agent_mappings()

    try:
        with psycopg2.connect(database_url) as conn:
            with conn.cursor() as cursor:
                update_player_mapping(conn, cursor, agent_mappings)
    except Exception as e:
        error_logger.error(f"Error connecting to database: {str(e)}")

if __name__ == "__main__":
    main()