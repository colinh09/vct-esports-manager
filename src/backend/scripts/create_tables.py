import psycopg2
import os
from psycopg2 import sql
from dotenv import load_dotenv

load_dotenv()
# DATABASE_URL = os.getenv("DATABASE_URL")
DATABASE_URL = os.getenv("RDS_DATABASE_URL")

def create_connection():
    """
    Establishes a connection to the PostgreSQL database using the connection string.
    Returns the connection object if successful, otherwise returns None.
    Prints and logs an error if the connection fails.
    """
    try:
        connection = psycopg2.connect(DATABASE_URL)
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def execute_query(connection, query):
    """
    Executes a given SQL query on the provided connection.
    Commits the transaction if successful, otherwise rolls back and logs the error.
    Closes the cursor after execution.
    
    Args:
        connection: The active database connection.
        query: The SQL query to be executed.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(query)
        connection.commit()
        print("Query executed successfully")
    except Exception as e:
        print(f"Error executing query: {e}")
    finally:
        cursor.close()

def drop_tables(connection, tables_to_drop):
    """
    Drops the specified tables if they exist in the database. The tables to drop are provided as a 
    comma-separated string, and only valid table names are allowed.
    
    Args:
        connection: The active database connection.
        tables_to_drop: A comma-separated string of table names to drop.
    """
    valid_tables = {
        'player_mapping', 'team_mapping', 'game_mapping', 
        'players', 'teams', 'tournaments', 'leagues',
        'spike_status', 'ability_used', 'damage_event',
        'player_assists', 'player_died', 'player_revived'
    }

    # Filter out invalid table names
    tables_to_drop = [table.strip() for table in tables_to_drop.split(',') if table.strip() in valid_tables]

    if not tables_to_drop:
        print("No valid tables specified to drop.")
        return

    for table in tables_to_drop:
        drop_query = f"DROP TABLE IF EXISTS {table} CASCADE;"
        execute_query(connection, drop_query)
        print(f"Dropped table: {table}")
    
def read_sql_file(file_path):
    """
    Reads the SQL commands from the given file and returns them as a string.
    
    Args:
        file_path: Path to the SQL file to read from.
    
    Returns:
        A string containing all the SQL commands from the file.
    """
    with open(file_path, 'r') as file:
        sql_commands = file.read()
    return sql_commands

def create_tables():
    """
    Creates necessary tables in the PostgreSQL database if they do not exist.
    Reads the table creation SQL from an external file (schema.sql).
    Optionally, it allows the user to drop specified tables before recreating them.
    """
    connection = create_connection()
    if connection is None:
        return

    drop_choice = input("Do you want to drop existing tables before recreating them? (yes/no): ").strip().lower()

    if drop_choice == "yes":
        tables_to_drop = input("Specify which tables to drop (comma separated, e.g., players,teams): ").strip()
        drop_tables(connection, tables_to_drop)

    schema_file_path = "backend/db/schema.sql"


    sql_commands = read_sql_file(schema_file_path)

    try:
        execute_query(connection, sql_commands)
    except Exception as e:
        print(f"Error executing SQL commands from file: {e}")

    connection.close()

if __name__ == "__main__":
    """
    Main entry point of the script. Prompts the user to drop and recreate tables.
    Calls the function to create or recreate tables as needed.
    """
    create_tables()
