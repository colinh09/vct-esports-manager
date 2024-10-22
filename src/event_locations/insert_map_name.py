import json
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment variable
database_url = os.getenv('RDS_DATABASE_URL')
if not database_url:
    raise ValueError("RDS_DATABASE_URL environment variable is not set")

def load_map_data():
    """Load and parse maps.json file, returning a mapping of map URLs to display names."""
    with open('maps.json', 'r') as f:
        maps_data = json.load(f)
    
    # Create a mapping of map URLs to display names
    map_url_to_name = {
        map_data['mapUrl']: map_data['displayName']
        for map_data in maps_data
    }
    return map_url_to_name

def main():
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        # Add display_name column if it doesn't exist
        cur.execute("""
            ALTER TABLE player_map_performance 
            ADD COLUMN IF NOT EXISTS display_name varchar;
        """)
        
        # Load map data
        map_url_to_name = load_map_data()
        
        # Update each row with the corresponding display name
        for map_url, display_name in map_url_to_name.items():
            cur.execute("""
                UPDATE player_map_performance 
                SET display_name = %s 
                WHERE map = %s;
            """, (display_name, map_url))
        
        # Commit changes and close connection
        conn.commit()
        cur.close()
        conn.close()
        
        print("Successfully updated map display names in the database")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()