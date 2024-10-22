import os
import psycopg2
from dotenv import load_dotenv
import logging
from psycopg2.extras import execute_batch
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

def get_db_connection_string(url):
    """Convert URL to PostgreSQL connection string"""
    parsed = urlparse(url)
    username = parsed.username
    password = parsed.password
    database = parsed.path[1:]  # Remove leading slash
    hostname = parsed.hostname
    port = parsed.port or 5432  # Default PostgreSQL port
    
    return f"postgresql://{username}:{password}@{hostname}:{port}/{database}"

def create_games_played_column():
    """Add games_played column to players table if it doesn't exist"""
    try:
        cursor.execute("""
        ALTER TABLE players
        ADD COLUMN IF NOT EXISTS games_played INTEGER DEFAULT 0;
        """)
        conn.commit()
        logging.info("Added games_played column to players table")
    except Exception as e:
        conn.rollback()
        logging.error(f"Error adding column: {e}")

def count_games_played():
    """Count games played for each player and tournament type combination"""
    try:
        # Get the count of games for each player_id and tournament_type
        cursor.execute("""
        WITH game_counts AS (
            SELECT 
                player_id,
                tournament_type,
                COUNT(DISTINCT platform_game_id) as games_count
            FROM player_mapping
            GROUP BY player_id, tournament_type
        )
        SELECT 
            p.player_id,
            p.tournament_type,
            COALESCE(gc.games_count, 0) as games_count
        FROM players p
        LEFT JOIN game_counts gc 
            ON p.player_id = gc.player_id 
            AND p.tournament_type = gc.tournament_type
        """)
        
        player_games = cursor.fetchall()
        logging.info(f"Found game counts for {len(player_games)} player records")

        # Update the players table with the games played count
        update_query = """
        UPDATE players 
        SET games_played = %s
        WHERE player_id = %s AND tournament_type = %s
        """
        
        # Prepare the data for batch update
        update_data = [(count, player_id, tournament_type) 
                      for player_id, tournament_type, count in player_games]
        
        # Execute batch update
        execute_batch(cursor, update_query, update_data, page_size=1000)
        conn.commit()
        
        logging.info(f"Successfully updated games_played for {len(update_data)} players")
        
        # Log some statistics
        cursor.execute("""
        SELECT 
            MIN(games_played) as min_games,
            MAX(games_played) as max_games,
            AVG(games_played)::numeric(10,2) as avg_games
        FROM players
        WHERE games_played > 0
        """)
        stats = cursor.fetchone()
        logging.info(f"Statistics - Min games: {stats[0]}, Max games: {stats[1]}, Avg games: {stats[2]}")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"Error counting games played: {e}")

# Main execution
try:
    # Get the database URL and convert it to a connection string
    db_url = os.getenv('RDS_DATABASE_URL')
    if not db_url:
        raise ValueError("RDS_DATABASE_URL environment variable not set")
        
    connection_string = get_db_connection_string(db_url)
    
    # Connect to the database
    conn = psycopg2.connect(connection_string)
    cursor = conn.cursor()
    
    # Add the games_played column
    create_games_played_column()
    
    # Count and update games played
    count_games_played()
    
    logging.info("Script completed successfully")

except Exception as e:
    logging.error(f"An error occurred: {e}")

finally:
    if 'cursor' in locals() and cursor:
        cursor.close()
    if 'conn' in locals() and conn:
        conn.close()
    logging.info("Database connection closed")