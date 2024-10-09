import json
import psycopg2
import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(filename='update_team_leaders.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("RDS_DATABASE_URL")

def connect_to_db():
    return psycopg2.connect(DATABASE_URL)

def add_team_leader_column(cursor):
    cursor.execute("""
    ALTER TABLE players
    ADD COLUMN IF NOT EXISTS is_team_leader BOOLEAN DEFAULT FALSE
    """)

def update_team_leaders(cursor, team_leaders):
    for team_name, team_data in team_leaders.items():
        for found_team, captain in team_data:
            if captain:
                cursor.execute("""
                UPDATE players
                SET is_team_leader = TRUE
                WHERE handle = %s
                RETURNING player_id
                """, (captain,))
                
                result = cursor.fetchone()
                if result:
                    logging.info(f"Successfully updated {captain} as team leader for {found_team}")
                else:
                    logging.warning(f"Player {captain} not found in database for team {found_team}")

def main():
    # Load team captains data
    with open("team_captains_v2.json", "r") as f:
        team_leaders = json.load(f)

    conn = connect_to_db()
    cursor = conn.cursor()

    try:
        # Add the new column
        add_team_leader_column(cursor)
        conn.commit()
        logging.info("Added 'is_team_leader' column to players table")

        # Update team leaders
        update_team_leaders(cursor, team_leaders)
        conn.commit()
        logging.info("Finished updating team leaders")

    except Exception as e:
        conn.rollback()
        logging.error(f"An error occurred: {str(e)}")

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()