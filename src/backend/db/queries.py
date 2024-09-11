# Predefined Queries and Query Functions
# 1. get_player_stats(player_id, tournament_type)
# 2. get_team_stats(team_id, tournament_type)
# 3. get_game_events(platform_game_id)
# 4. get_player_kills(player_id, tournament_type)
# 5. get_player_assists(player_id, tournament_type)
# 6. get_team_wins(team_id, tournament_type)

def get_player_stats(player_id, tournament_type):
    query = """
        SELECT * FROM players
        WHERE player_id = :player_id
        AND tournament_type = :tournament_type;
    """
    return query, {"player_id": player_id, "tournament_type": tournament_type}

def get_team_stats(team_id, tournament_type):
    query = """
        SELECT * FROM teams
        WHERE team_id = :team_id
        AND tournament_type = :tournament_type;
    """
    return query, {"team_id": team_id, "tournament_type": tournament_type}

def get_game_events(platform_game_id):
    query = """
        SELECT * FROM events
        WHERE platform_game_id = :platform_game_id;
    """
    return query, {"platform_game_id": platform_game_id}

def get_player_kills(player_id, tournament_type):
    query = """
        SELECT * FROM event_players
        WHERE kill_id = :player_id
        AND platform_game_id IN (
            SELECT platform_game_id FROM player_mapping
            WHERE player_id = :player_id
            AND tournament_type = :tournament_type
        );
    """
    return query, {"player_id": player_id, "tournament_type": tournament_type}

def get_player_assists(player_id, tournament_type):
    query = """
        SELECT * FROM event_players
        WHERE assist_id = :player_id
        AND platform_game_id IN (
            SELECT platform_game_id FROM player_mapping
            WHERE player_id = :player_id
            AND tournament_type = :tournament_type
        );
    """
    return query, {"player_id": player_id, "tournament_type": tournament_type}

def get_team_wins(team_id, tournament_type):
    query = """
        SELECT COUNT(*)
        FROM game_mapping gm
        JOIN team_mapping tm ON gm.platform_game_id = tm.platform_game_id
        JOIN events e ON e.platform_game_id = gm.platform_game_id
        WHERE tm.team_id = :team_id
        AND e.event_type = 'game_won'
        AND tm.tournament_type = :tournament_type;
    """
    return query, {"team_id": team_id, "tournament_type": tournament_type}