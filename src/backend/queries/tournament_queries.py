import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

class TournamentQueries:
    def __init__(self):
        # Get the DATABASE_URL from the environment
        self.db_url = os.getenv("DATABASE_URL")
        
        # Initialize the database connection with RealDictCursor for better data handling
        self.connection = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
    
    def get_all_tournaments_for_player(self, player_id, tournament_type):
        """
        Get all tournaments a player has participated in.
        
        :param player_id: The player's unique ID
        :param tournament_type: The type of tournament (e.g., regular, playoffs)
        :return: List of tournaments the player has participated in
        """
        query = """
        SELECT DISTINCT gm.tournament_id, t.name, t.status, t.time_zone, t.league_id
        FROM player_mapping pm
        JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
        JOIN tournaments t ON gm.tournament_id = t.tournament_id
        WHERE pm.player_id = %s
          AND pm.tournament_type = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (player_id, tournament_type))
            return cursor.fetchall()

    def get_all_tournaments_for_team(self, team_id, tournament_type):
        """
        Get all tournaments a team has participated in.
        
        :param team_id: The team's unique ID
        :param tournament_type: The type of tournament (e.g., regular, playoffs)
        :return: List of tournaments the team has participated in
        """
        query = """
        SELECT DISTINCT gm.tournament_id, t.name, t.status, t.time_zone, t.league_id
        FROM team_mapping tm
        JOIN game_mapping gm ON tm.platform_game_id = gm.platform_game_id
        JOIN tournaments t ON gm.tournament_id = t.tournament_id
        WHERE tm.team_id = %s
          AND tm.tournament_type = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (team_id, tournament_type))
            return cursor.fetchall()

    def get_game_info_within_tournament(self, team1_id, team2_id, tournament_id):
        """
        Get information about a specific game (match) between two teams within a tournament.
        
        :param team1_id: The ID of the first team
        :param team2_id: The ID of the second team
        :param tournament_id: The ID of the tournament
        :return: Information about the specific game (platform_game_id, game details)
        """
        query = """
        SELECT gm.platform_game_id, gm.esports_game_id, tm1.team_id AS team1_id, tm2.team_id AS team2_id
        FROM game_mapping gm
        JOIN team_mapping tm1 ON gm.platform_game_id = tm1.platform_game_id
        JOIN team_mapping tm2 ON gm.platform_game_id = tm2.platform_game_id
        WHERE gm.tournament_id = %s
          AND tm1.team_id = %s
          AND tm2.team_id = %s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (tournament_id, team1_id, team2_id))
            return cursor.fetchone()

    def close(self):
        """Closes the database connection."""
        if self.connection:
            self.connection.close()

if __name__ == "__main__":
    # Initialize the TournamentQueries class
    tournament_queries = TournamentQueries()

    # Example: Get all tournaments a player has participated in
    player_id = "107769214873453994"
    tournament_type = "vct-international"
    player_tournaments = tournament_queries.get_all_tournaments_for_player(player_id, tournament_type)
    print("Player Tournaments:", player_tournaments)

    # Example: Get all tournaments a team has participated in
    team_id = "107761408072272990"
    team_tournaments = tournament_queries.get_all_tournaments_for_team(team_id, tournament_type)
    print("Team Tournaments:", team_tournaments)

    # Example: Get a specific game between two teams in a tournament
    # team1_id = "example_team1_id"
    # team2_id = "example_team2_id"
    # tournament_id = "example_tournament_id"
    # game_info = tournament_queries.get_game_info_within_tournament(team1_id, team2_id, tournament_id)
    # print("Game Info:", game_info)

    # Close the connection after use
    tournament_queries.close()
