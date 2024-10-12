from psycopg2.extras import RealDictCursor
import logging
from db_connection import get_db_connection

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_player_info(handle=None, first_name=None, last_name=None):
    if handle is None and first_name is None and last_name is None:
        raise ValueError("At least one of handle, first_name, or last_name must be provided")

    try:
        with get_db_connection() as conn:
            logger.info("Database connection established")
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if handle:
                    query = """
                    SELECT p.*, t.name AS team_name, l.name AS league_name,
                           similarity(LOWER(p.handle), LOWER(%s)) AS sim
                    FROM players p
                    LEFT JOIN teams t ON p.home_team_id = t.team_id
                    LEFT JOIN leagues l ON t.home_league_id = l.league_id
                    WHERE similarity(LOWER(p.handle), LOWER(%s)) > 0.3
                    ORDER BY sim DESC
                    LIMIT 1
                    """
                    cur.execute(query, (handle, handle))
                else:
                    query = """
                    SELECT p.*, t.name AS team_name, l.name AS league_name,
                           greatest(
                               similarity(LOWER(p.first_name), LOWER(%s)),
                               similarity(LOWER(p.last_name), LOWER(%s))
                           ) AS sim
                    FROM players p
                    LEFT JOIN teams t ON p.home_team_id = t.team_id
                    LEFT JOIN leagues l ON t.home_league_id = l.league_id
                    WHERE similarity(LOWER(p.first_name), LOWER(%s)) > 0.3
                       OR similarity(LOWER(p.last_name), LOWER(%s)) > 0.3
                    ORDER BY sim DESC
                    LIMIT 1
                    """
                    params = [first_name or '', last_name or '', first_name or '', last_name or '']
                    logger.info(f"Executing query with params: {params}")
                    cur.execute(query, params)

                logger.info("Query executed, fetching result")
                result = cur.fetchone()
                
                if result:
                    logger.info("Result found")
                    return dict(result)
                else:
                    logger.info("No result found")
                    return None

    except Exception as e:
        logger.error(f"Error in get_player_info: {str(e)}", exc_info=True)
        raise

def get_player_info_wrapper(handle=None, first_name=None, last_name=None):
    logger.info(f"get_player_info_wrapper called with handle={handle}, first_name={first_name}, last_name={last_name}")
    try:
        result = get_player_info(handle, first_name, last_name)
        if result:
            logger.info("Player info found")
            return {"status": "success", "data": result}
        else:
            logger.info("Player not found")
            return {"status": "not_found", "message": "Player not found"}
    except ValueError as ve:
        logger.error(f"ValueError in get_player_info_wrapper: {str(ve)}")
        return {"status": "error", "message": str(ve)}
    except Exception as e:
        logger.error(f"Unexpected error in get_player_info_wrapper: {str(e)}", exc_info=True)
        return {"status": "error", "message": "An unexpected error occurred"}