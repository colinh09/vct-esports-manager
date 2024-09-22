import logging
from db_connection import get_db_connection

logger = logging.getLogger()

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