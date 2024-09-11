import os
import logging
from dotenv import load_dotenv
from langchain_community.utilities import SQLDatabase
from backend.db.queries import get_player_stats

load_dotenv()

logging.basicConfig(
    filename="errorlogs.txt",
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

DATABASE_URL = os.getenv("DATABASE_URL")
db = SQLDatabase.from_uri(DATABASE_URL)

def execute_query(query_func, **kwargs):
    """
    Fetches a predefined query by name from queries.py and executes it on the database.
    
    Args:
        query_func (function): The query function to call.
        **kwargs: Arguments to be passed into the query.
    
    Returns:
        result: Result of the query execution or None in case of errors.
    """
    try:
        query, query_args = query_func(**kwargs)
        result = db.run(query, parameters=query_args)
        logging.info(f"Successfully executed query: {query_func.__name__}")
        return result

    except Exception as e:
        # Log the error and return None
        logging.error(f"Error executing query '{query_func.__name__}': {e}")
        print(f"Error executing query '{query_func.__name__}': {e}")
        return None

# if __name__ == "__main__":
#     # Example: Get player stats for a specific player in a tournament
#     player_id = "107723774839335242"
#     tournament_type = "vct-international"

#     # Execute the predefined query function
#     result = execute_query(get_player_stats, player_id=player_id, tournament_type=tournament_type)
    
#     # Print the result
#     if result:
#         print(result)
#     else:
#         print(f"Failed to execute query 'get_player_stats'")
