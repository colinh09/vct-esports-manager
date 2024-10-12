from db_connection import get_db_connection

def get_top_agents_for_player(player_id, limit=5):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
        SELECT agent_name, COUNT(*) as play_count
        FROM player_mapping
        WHERE player_id = %s
        GROUP BY agent_name
        ORDER BY play_count DESC
        LIMIT %s
        """

        cursor.execute(query, (player_id, limit))
        results = cursor.fetchall()

        cursor.close()
        conn.close()

        top_agents = [{"agent": row['agent_name'], "play_count": int(row['play_count'])} for row in results]
        
        return top_agents
    except Exception as e:
        raise  # Re-raise the exception to be caught by the lambda handler