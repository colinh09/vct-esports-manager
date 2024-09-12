import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

class PlayerInfoQueries:
    def __init__(self):
        # Get the DATABASE_URL from the environment
        self.db_url = os.getenv("DATABASE_URL")
        
        # Initialize the database connection with RealDictCursor for better data handling
        self.connection = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def get_player_info(self, player_id):
        """
        Fetches player information, including team and league details, using a JOIN query.
        
        :param player_id: The ID of the player
        :return: Dictionary containing player information with team and league details
        """
        query = """
        SELECT
            p.handle, p.first_name, p.last_name, p.status,
            t.name AS team_name, t.acronym AS team_acronym, t.slug AS team_slug, t.dark_logo_url, t.light_logo_url,
            l.name AS league_name, l.region AS league_region
        FROM players p
        JOIN teams t ON p.home_team_id = t.team_id
        JOIN leagues l ON t.home_league_id = l.league_id
        WHERE p.player_id = %s
        """
        
        with self.connection.cursor() as cursor:
            cursor.execute(query, (player_id,))
            player_info = cursor.fetchone()
        
        return player_info

    def get_player_info_by_handle(self, handle):
        """
        Fetches player information based on the player's handle, including team and league details.
        
        :param handle: The handle of the player
        :return: Dictionary containing player information with team and league details
        """
        query = """
        SELECT
            p.player_id, p.handle, p.first_name, p.last_name, p.status,
            t.name AS team_name, t.acronym AS team_acronym, t.slug AS team_slug, t.dark_logo_url, t.light_logo_url,
            l.name AS league_name, l.region AS league_region
        FROM players p
        JOIN teams t ON p.home_team_id = t.team_id
        JOIN leagues l ON t.home_league_id = l.league_id
        WHERE p.handle = %s
        """
        
        with self.connection.cursor() as cursor:
            cursor.execute(query, (handle,))
            player_info = cursor.fetchone()
        
        return player_info

    def get_player_info_by_name(self, first_name, last_name):
        """
        Fetches player information based on the player's first and last name, including team and league details.
        
        :param first_name: The player's first name
        :param last_name: The player's last name
        :return: Dictionary containing player information with team and league details
        """
        query = """
        SELECT
            p.handle, p.first_name, p.last_name, p.status,
            t.name AS team_name, t.acronym AS team_acronym, t.slug AS team_slug, t.dark_logo_url, t.light_logo_url,
            l.name AS league_name, l.region AS league_region
        FROM players p
        JOIN teams t ON p.home_team_id = t.team_id
        JOIN leagues l ON t.home_league_id = l.league_id
        WHERE p.first_name = %s AND p.last_name = %s
        """
        
        with self.connection.cursor() as cursor:
            cursor.execute(query, (first_name, last_name))
            player_info = cursor.fetchone()
        
        return player_info

    def close(self):
        """Closes the database connection."""
        if self.connection:
            self.connection.close()
