import logging
from db_connection import get_db_connection

logger = logging.getLogger()

import logging
from db_connection import get_db_connection
from psycopg2.extras import RealDictCursor

logger = logging.getLogger()

def get_all_player_games(player_id, tournament_type, start_date=None, end_date=None):
    query = """
    SELECT 
        pm.internal_player_id, 
        pm.platform_game_id, 
        pm.handle, 
        pm.agent_guid, 
        pm.kills, 
        pm.deaths, 
        pm.assists, 
        pm.combat_score, 
        pm.agent_name, 
        pm.agent_role, 
        pm.average_combat_score,
        gm.game_date,
        gm.esports_game_id,
        gm.tournament_id,
        gm.total_rounds,
        gm.winning_team
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    WHERE pm.player_id = %s
      AND pm.tournament_type = %s
    """
    params = [player_id, tournament_type]

    if start_date:
        query += " AND gm.game_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND gm.game_date <= %s"
        params.append(end_date)

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error in get_all_player_games: {str(e)}")
        raise

def get_all_player_games_from_tournament(player_id, tournament_type, tournament_id, start_date=None, end_date=None):
    query = """
    SELECT 
        pm.internal_player_id, 
        pm.platform_game_id, 
        pm.handle, 
        pm.agent_guid, 
        pm.kills, 
        pm.deaths, 
        pm.assists, 
        pm.combat_score, 
        pm.agent_name, 
        pm.agent_role, 
        pm.average_combat_score,
        gm.game_date,
        gm.esports_game_id,
        gm.tournament_id,
        gm.total_rounds,
        gm.winning_team
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    WHERE pm.player_id = %s
      AND pm.tournament_type = %s
      AND gm.tournament_id = %s
    """
    params = [player_id, tournament_type, tournament_id]

    if start_date:
        query += " AND gm.game_date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND gm.game_date <= %s"
        params.append(end_date)

    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, tuple(params))
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