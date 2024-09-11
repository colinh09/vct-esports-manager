import psycopg2
import os
from psycopg2 import sql

DATABASE_URL = "postgresql://postgres:password@localhost:5432/vct-manager"

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
        'events', 'player_mapping', 'team_mapping', 'game_mapping', 
        'players', 'teams', 'tournaments', 'leagues'
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

def create_tables():
    """
    Creates necessary tables in the PostgreSQL database if they do not exist.
    Optionally, it allows the user to drop specified tables before recreating them.
    Tables include leagues, tournaments, teams, players, game mapping, and various event-related tables.
    """
    connection = create_connection()
    if connection is None:
        return

    # Optionally drop existing tables
    drop_choice = input("Do you want to drop existing tables before recreating them? (yes/no): ").strip().lower()

    if drop_choice == "yes":
        tables_to_drop = input("Specify which tables to drop (comma separated, e.g., players,teams): ").strip()
        drop_tables(connection, tables_to_drop)

    # List of SQL queries to create the tables
    queries = [
        """
        CREATE TABLE IF NOT EXISTS leagues (
          league_id VARCHAR(255),
          tournament_type VARCHAR(255),
          region VARCHAR(10),
          dark_logo_url TEXT,
          light_logo_url TEXT,
          name VARCHAR(255),
          slug VARCHAR(255),
          PRIMARY KEY (league_id, tournament_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS tournaments (
          tournament_id VARCHAR(255),
          tournament_type VARCHAR(255),
          status VARCHAR(50),
          league_id VARCHAR(255),
          time_zone VARCHAR(50),
          name VARCHAR(255),
          PRIMARY KEY (tournament_id, tournament_type),
          FOREIGN KEY (league_id, tournament_type) REFERENCES leagues(league_id, tournament_type) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS teams (
          team_id VARCHAR(255),
          tournament_type VARCHAR(255),
          acronym VARCHAR(10),
          home_league_id VARCHAR(255),
          dark_logo_url TEXT,
          light_logo_url TEXT,
          slug VARCHAR(255),
          name VARCHAR(255),
          PRIMARY KEY (team_id, tournament_type),
          FOREIGN KEY (home_league_id, tournament_type) REFERENCES leagues(league_id, tournament_type) ON DELETE CASCADE,
          UNIQUE (team_id, tournament_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS players (
        player_id VARCHAR(255),
        tournament_type VARCHAR(255),
        handle VARCHAR(255),
        first_name VARCHAR(255),
        last_name VARCHAR(255),
        status VARCHAR(50),
        photo_url TEXT,
        home_team_id VARCHAR(255),
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        PRIMARY KEY (player_id, tournament_type)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS game_mapping (
          platform_game_id VARCHAR(255) PRIMARY KEY,
          esports_game_id VARCHAR(255),
          tournament_id VARCHAR(255),
          tournament_type VARCHAR(255),
          year INTEGER,
          FOREIGN KEY (tournament_id, tournament_type) REFERENCES tournaments(tournament_id, tournament_type) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS player_mapping (
          internal_player_id VARCHAR(255),
          player_id VARCHAR(255),
          tournament_type VARCHAR(255),
          platform_game_id VARCHAR(255),
          PRIMARY KEY (internal_player_id, platform_game_id),
          FOREIGN KEY (player_id, tournament_type) REFERENCES players(player_id, tournament_type) ON DELETE CASCADE,
          FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS team_mapping (
          internal_team_id VARCHAR(255),
          team_id VARCHAR(255),
          tournament_type VARCHAR(255),
          platform_game_id VARCHAR(255),
          PRIMARY KEY (internal_team_id, platform_game_id),
          FOREIGN KEY (team_id, tournament_type) REFERENCES teams(team_id, tournament_type) ON DELETE CASCADE,
          FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id BIGSERIAL PRIMARY KEY,
            platform_game_id VARCHAR(255),
            event_type VARCHAR(255),
            tournament_type VARCHAR(255),
            FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS event_players (
            event_player_id BIGSERIAL PRIMARY KEY,
            event_id BIGINT,
            internal_player_id VARCHAR(255),
            platform_game_id VARCHAR(255),
            
            kill_id VARCHAR(255) DEFAULT NULL,
            death_id VARCHAR(255) DEFAULT NULL,
            assist_id VARCHAR(255) DEFAULT NULL,
            
            damage_dealt FLOAT DEFAULT NULL,
            damage_location VARCHAR(50) DEFAULT NULL,
            
            spike_status VARCHAR(50) DEFAULT NULL,
            weapon_used VARCHAR(255) DEFAULT NULL,
            
            ability_used VARCHAR(255) DEFAULT NULL,
            
            revived_by_id VARCHAR(255) DEFAULT NULL,
            revived_player_id VARCHAR(255) DEFAULT NULL,
            
            FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE,
            FOREIGN KEY (internal_player_id, platform_game_id) REFERENCES player_mapping(internal_player_id, platform_game_id) ON DELETE CASCADE
        );
        """
    ]

    # Execute each table creation query
    for query in queries:
        execute_query(connection, query)

    connection.close()

if __name__ == "__main__":
    """
    Main entry point of the script. Prompts the user to drop and recreate tables.
    Calls the function to create or recreate tables as needed.
    """
    create_tables()
