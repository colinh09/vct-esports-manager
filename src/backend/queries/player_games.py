import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

class PlayerGameStatsQueries:
    def __init__(self):
        # Get the DATABASE_URL from the environment
        self.db_url = os.getenv("DATABASE_URL")
        
        # Initialize the database connection with RealDictCursor for better data handling
        self.connection = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)

    def get_all_player_games(self, player_id, tournament_type):
        """
        Base query to find all games a player participated in (without filtering by tournament).
        :param player_id: The player's unique ID
        :param tournament_type: The type of tournament (e.g., regular, playoffs)
        :return: List of all games the player has participated in
        """
        query = """
        SELECT pm.internal_player_id, pm.platform_game_id
        FROM player_mapping pm
        JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
        WHERE pm.player_id = %s
          AND pm.tournament_type = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (player_id, tournament_type))
            return cursor.fetchall()

    def get_all_player_games_from_tournament(self, player_id, tournament_type, tournament_id):
        """
        Base query to find all games a player participated in within a specific tournament.
        :param player_id: The player's unique ID
        :param tournament_type: The type of tournament (e.g., regular, playoffs)
        :param tournament_id: The ID of the tournament to filter by
        :return: List of games the player has participated in within the specified tournament
        """
        query = """
        SELECT pm.internal_player_id, pm.platform_game_id
        FROM player_mapping pm
        JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
        WHERE pm.player_id = %s
          AND pm.tournament_type = %s
          AND gm.tournament_id = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (player_id, tournament_type, tournament_id))
            return cursor.fetchall()

    def get_damage_stats(self, platform_game_id, internal_player_id):
        """
        Query to fetch all damage stats for a player in a specific game.
        :param platform_game_id: The platform game ID
        :param internal_player_id: The internal player ID
        :return: Damage statistics for the player in the game
        """
        query = """
        SELECT de.platform_game_id, de.causer_id, de.victim_id, de.damage_amount, de.location, de.kill_event
        FROM damage_event de
        WHERE de.platform_game_id = %s
          AND de.causer_id = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (platform_game_id, internal_player_id))
            return cursor.fetchall()

    def get_assists(self, platform_game_id, internal_player_id):
        """
        Query to fetch all assist stats for a player in a specific game.
        :param platform_game_id: The platform game ID
        :param internal_player_id: The internal player ID
        :return: Assist statistics for the player in the game
        """
        query = """
        SELECT pa.platform_game_id, pa.assister_id
        FROM player_assists pa
        WHERE pa.platform_game_id = %s
          AND pa.assister_id = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (platform_game_id, internal_player_id))
            return cursor.fetchall()

    def get_deaths(self, platform_game_id, internal_player_id):
        """
        Query to fetch all death events for a player in a specific game.
        :param platform_game_id: The platform game ID
        :param internal_player_id: The internal player ID
        :return: Death statistics for the player in the game
        """
        query = """
        SELECT pd.platform_game_id, pd.deceased_id, pd.killer_id, pd.weapon_guid
        FROM player_died pd
        WHERE pd.platform_game_id = %s
          AND pd.deceased_id = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (platform_game_id, internal_player_id))
            return cursor.fetchall()

# Example usage:
if __name__ == "__main__":
    # Establish a connection to the database (replace with your actual connection setup)
    connection = psycopg2.connect("your_database_url_here")

    # Initialize the queries class
    player_stats = PlayerGameStatsQueries(connection)

    # Get all player games
    player_id = "example_player_id"
    tournament_type = "example_tournament_type"
    all_games = player_stats.get_all_player_games(player_id, tournament_type)
    print("All Player Games:", all_games)

    # Get all player games from a specific tournament
    tournament_id = "example_tournament_id"
    games_in_tournament = player_stats.get_all_player_games_from_tournament(player_id, tournament_type, tournament_id)
    print("Games in Tournament:", games_in_tournament)

    # Close the connection after use
    connection.close()
