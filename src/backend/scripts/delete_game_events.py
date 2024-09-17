import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("RDS_DATABASE_URL")

def create_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def delete_game_data(platform_game_id):
    connection = create_connection()
    if connection is None:
        print("Could not connect to the database.")
        return

    cursor = connection.cursor()
    total_deleted = 0
    try:
        # List of tables to delete from
        tables = [
            "player_died",
            "spike_status",
            "damage_event",
            "player_revived",
            "ability_used",
            "player_assists"
        ]

        for table in tables:
            cursor.execute(f"DELETE FROM {table} WHERE platform_game_id = %s", (platform_game_id,))
            rows_deleted = cursor.rowcount
            total_deleted += rows_deleted
            print(f"Deleted {rows_deleted} rows from {table}")

        connection.commit()
        print(f"Successfully deleted all events for game ID: {platform_game_id}")
        print(f"Total events deleted: {total_deleted}")

    except Exception as e:
        connection.rollback()
        print(f"Error deleting game data: {e}")
    finally:
        cursor.close()
        connection.close()

def main():
    print("Available tournaments:")
    print("1: vct-international")
    print("2: vct-challengers")
    print("3: game-changers")

    tournament_choice = input("Select the tournament by number: ").strip()

    tournament_map = {
        "1": "vct-international",
        "2": "vct-challengers",
        "3": "game-changers"
    }

    tournament_type = tournament_map.get(tournament_choice)

    if tournament_type:
        year = input("Enter the year of the tournament: ").strip()
        platform_game_id = input("Enter the platform game ID to delete: ").strip()

        if year.isdigit():
            print(f"You are about to delete data for game ID {platform_game_id} from {tournament_type} {year}")
            confirmation = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
            
            if confirmation == 'yes':
                print(f"Deleting data for game ID {platform_game_id} from {tournament_type} {year}")
                delete_game_data(platform_game_id)
            else:
                print("Operation cancelled.")
        else:
            print("Invalid year input.")
    else:
        print("Invalid selection.")

if __name__ == "__main__":
    main()