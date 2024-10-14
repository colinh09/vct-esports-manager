from db_connection import get_db_connection
from psycopg2.extras import RealDictCursor

ROLE_PERCENTAGE_THRESHOLD = 30

def get_top_players(cur, role, tournament_type, count):
    query = """
    WITH player_stats AS (
        SELECT 
            p.player_id,
            p.handle,
            p.first_name,
            p.last_name,
            p.{role}_percentage as role_percentage,
            t.name as team_name,
            l.region,
            COUNT(DISTINCT pm.platform_game_id) as role_games,
            SUM(pm.kills) as total_kills, 
            SUM(pm.deaths) as total_deaths, 
            SUM(pm.assists) as total_assists
        FROM players p
        JOIN player_mapping pm ON p.player_id = pm.player_id
        JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
        JOIN teams t ON p.home_team_id = t.team_id
        JOIN leagues l ON t.home_league_id = l.league_id
        WHERE p.{role}_percentage > %s
        AND gm.tournament_type = %s
        AND pm.agent_role = %s
        GROUP BY p.player_id, p.handle, p.first_name, p.last_name, p.{role}_percentage, t.name, l.region
    )
    SELECT 
        player_id,
        handle,
        first_name,
        last_name,
        role_percentage,
        team_name,
        region,
        role_games,
        total_kills, 
        total_deaths, 
        total_assists,
        CASE 
            WHEN total_kills + total_assists > 0 AND total_deaths > 0
            THEN CAST((CAST(total_kills + total_assists AS FLOAT) / total_deaths) * 100 AS INTEGER) / 100.0
            ELSE NULL
        END as kda_ratio
    FROM player_stats
    WHERE role_games > 0
    ORDER BY kda_ratio DESC NULLS LAST
    LIMIT %s
    """
    print(f"Executing query for role: {role}, tournament_type: {tournament_type}, count: {count}")
    cur.execute(query.format(role=role), (role.capitalize(), ROLE_PERCENTAGE_THRESHOLD, tournament_type, count))
    players = cur.fetchall()
    print(f"Query returned {len(players)} players")
    for player in players:
        print(f"Player data: {player}")
    return players

def get_top_igls(cur, tournament_type, count):
    query = """
    WITH igl_stats AS (
        SELECT 
            p.player_id,
            p.handle,
            p.first_name,
            p.last_name,
            t.name as team_name,
            l.region,
            COUNT(DISTINCT pm.platform_game_id) as total_games,
            SUM(pm.kills) as total_kills, 
            SUM(pm.deaths) as total_deaths, 
            SUM(pm.assists) as total_assists
        FROM players p
        JOIN player_mapping pm ON p.player_id = pm.player_id
        JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
        JOIN teams t ON p.home_team_id = t.team_id
        JOIN leagues l ON t.home_league_id = l.league_id
        WHERE p.is_team_leader = true
        AND gm.tournament_type = %s
        GROUP BY p.player_id, p.handle, p.first_name, p.last_name, t.name, l.region
    )
    SELECT 
        player_id,
        handle,
        first_name,
        last_name,
        team_name,
        region,
        total_games,
        total_kills, 
        total_deaths, 
        total_assists,
        CASE 
            WHEN total_kills + total_assists > 0 AND total_deaths > 0
            THEN CAST((CAST(total_kills + total_assists AS FLOAT) / total_deaths) * 100 AS INTEGER) / 100.0
            ELSE NULL
        END as kda_ratio
    FROM igl_stats
    WHERE total_games > 0
    ORDER BY kda_ratio DESC NULLS LAST
    LIMIT %s
    """
    print(f"Executing query for IGLs, tournament_type: {tournament_type}, count: {count}")
    cur.execute(query, (tournament_type, count))
    players = cur.fetchall()
    print(f"Query returned {len(players)} IGLs")
    for player in players:
        print(f"IGL data: {player}")
    return players

def evaluate_duelist(cur, tournament_type, count):
    return get_top_players(cur, 'duelist', tournament_type, count)

def evaluate_initiator(cur, tournament_type, count):
    return get_top_players(cur, 'initiator', tournament_type, count)

def evaluate_sentinel(cur, tournament_type, count):
    return get_top_players(cur, 'sentinel', tournament_type, count)

def evaluate_controller(cur, tournament_type, count):
    return get_top_players(cur, 'controller', tournament_type, count)

def evaluate_igl(cur, tournament_type, count):
    return get_top_igls(cur, tournament_type, count)

def get_top_players_by_role(role, vct_international, vct_challenger, game_changers):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    results = {}
    evaluation_functions = {
        'duelist': evaluate_duelist,
        'initiator': evaluate_initiator,
        'sentinel': evaluate_sentinel,
        'controller': evaluate_controller,
        'igl': evaluate_igl
    }
    
    try:
        print(f"Processing role: {role}")
        tournament_types = {
            'vct-international': vct_international,
            'vct-challengers': vct_challenger,
            'game-changers': game_changers
        }
        print(f"Tournament types: {tournament_types}")
        for tournament_type, count in tournament_types.items():
            if count > 0:
                print(f"Evaluating tournament type: {tournament_type}, count: {count}")
                results[tournament_type] = evaluation_functions[role.lower()](cur, tournament_type, count)
                print(f"Results for {tournament_type}: {results[tournament_type]}")
    finally:
        cur.close()
        conn.close()
    
    return results