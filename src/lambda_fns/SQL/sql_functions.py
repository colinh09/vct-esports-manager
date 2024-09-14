import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Database connection
def get_db_connection():
    db_url = os.environ['DATABASE_URL']
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# Player Info Queries
def get_player_info_by_handle(handle):
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
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (handle,))
                return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error in get_player_info_by_handle: {str(e)}")
        raise

def get_player_info_by_name(first_name, last_name):
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
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (first_name, last_name))
                return cursor.fetchone()
    except Exception as e:
        logger.error(f"Error in get_player_info_by_name: {str(e)}")
        raise

# Player Game Stats Queries
def get_all_player_games(player_id, tournament_type):
    query = """
    SELECT pm.internal_player_id, pm.platform_game_id
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    WHERE pm.player_id = %s
      AND pm.tournament_type = %s;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (player_id, tournament_type))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error in get_all_player_games: {str(e)}")
        raise

def get_all_player_games_from_tournament(player_id, tournament_type, tournament_id):
    query = """
    SELECT pm.internal_player_id, pm.platform_game_id
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    WHERE pm.player_id = %s
      AND pm.tournament_type = %s
      AND gm.tournament_id = %s;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (player_id, tournament_type, tournament_id))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error in get_all_player_games_from_tournament: {str(e)}")
        raise

def get_damage_stats(platform_game_id, internal_player_id):
    query = """
    SELECT de.platform_game_id, de.causer_id, de.victim_id, de.damage_amount, de.location, de.kill_event
    FROM damage_event de
    WHERE de.platform_game_id = %s
      AND de.causer_id = %s;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (platform_game_id, internal_player_id))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error in get_damage_stats: {str(e)}")
        raise

def get_assists(platform_game_id, internal_player_id):
    query = """
    SELECT pa.platform_game_id, pa.assister_id
    FROM player_assists pa
    WHERE pa.platform_game_id = %s
      AND pa.assister_id = %s;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (platform_game_id, internal_player_id))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error in get_assists: {str(e)}")
        raise

def get_deaths(platform_game_id, internal_player_id):
    query = """
    SELECT pd.platform_game_id, pd.deceased_id, pd.killer_id, pd.weapon_guid
    FROM player_died pd
    WHERE pd.platform_game_id = %s
      AND pd.deceased_id = %s;
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (platform_game_id, internal_player_id))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error in get_deaths: {str(e)}")
        raise

# Additional functions for stats calculations
def get_player_game_stats(player_id):
    try:
        all_games = get_all_player_games(player_id, 'vct-international')
        return calculate_aggregated_stats(all_games)
    except Exception as e:
        logger.error(f"Error in get_player_game_stats: {str(e)}")
        raise

def get_player_tournament_stats(player_id, tournament_id):
    try:
        tournament_games = get_all_player_games_from_tournament(player_id, 'vct-international', tournament_id)
        stats = calculate_aggregated_stats(tournament_games)
        stats['tournament_id'] = tournament_id
        return stats
    except Exception as e:
        logger.error(f"Error in get_player_tournament_stats: {str(e)}")
        raise

def calculate_aggregated_stats(games):
    total_damage = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    
    for game in games:
        platform_game_id = game['platform_game_id']
        internal_player_id = game['internal_player_id']
        
        damage_stats = get_damage_stats(platform_game_id, internal_player_id)
        assists = get_assists(platform_game_id, internal_player_id)
        deaths = get_deaths(platform_game_id, internal_player_id)
        
        total_damage += sum(stat['damage_amount'] for stat in damage_stats)
        total_kills += sum(1 for stat in damage_stats if stat['kill_event'])
        total_deaths += len(deaths)
        total_assists += len(assists)
    
    games_played = len(games)
    
    return {
        'games_played': games_played,
        'total_damage': total_damage,
        'total_kills': total_kills,
        'total_deaths': total_deaths,
        'total_assists': total_assists,
        'average_damage_per_game': total_damage / games_played if games_played > 0 else 0,
        'average_kills_per_game': total_kills / games_played if games_played > 0 else 0,
        'average_deaths_per_game': total_deaths / games_played if games_played > 0 else 0,
        'average_assists_per_game': total_assists / games_played if games_played > 0 else 0,
        'kda_ratio': (total_kills + total_assists) / total_deaths if total_deaths > 0 else (total_kills + total_assists)
    }

# Lambda handler
def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        function = event['function']
        parameters = event.get('parameters', [{}])[0]

        if function == 'get_player_info_by_handle':
            handle = parameters.get('handle')
            result = get_player_info_by_handle(handle)
        elif function == 'get_player_info_by_name':
            first_name = parameters.get('first_name')
            last_name = parameters.get('last_name')
            result = get_player_info_by_name(first_name, last_name)
        elif function == 'get_player_game_stats':
            player_id = parameters.get('player_id')
            result = get_player_game_stats(player_id)
        elif function == 'get_player_tournament_stats':
            player_id = parameters.get('player_id')
            tournament_id = parameters.get('tournament_id')
            result = get_player_tournament_stats(player_id, tournament_id)
        else:
            raise ValueError(f"Unknown function: {function}")

        return {
            'response': {
                'actionGroup': event['actionGroup'],
                'function': event['function'],
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps(result, default=str)
                        }
                    }
                }
            },
            'messageVersion': event['messageVersion']
        }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'response': {
                'actionGroup': event.get('actionGroup'),
                'function': event.get('function'),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps({'error': str(e)})
                        }
                    }
                }
            },
            'messageVersion': event.get('messageVersion')
        }