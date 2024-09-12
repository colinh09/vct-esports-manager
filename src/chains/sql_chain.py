import os
from dotenv import load_dotenv
from langchain_aws import ChatBedrock
from langchain.chains.sql_database.query import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import PromptTemplate
from sqlalchemy import text 
import re

# Load environment variables
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def run_sql_chain(user_question, top_k=1000):
    """
    This function initializes an LLM using Anthropic Claude v2, connects to a PostgreSQL database,
    retrieves the table schema, and generates a SQL query using a custom prompt. It passes the 
    table information as context to improve the accuracy of SQL query generation. The generated 
    query is then executed, and the result is returned.
    """
    
    llm = ChatBedrock(
        model_id="anthropic.claude-v2",  
        model_kwargs=dict(temperature=0)
    )
    
    db = SQLDatabase.from_uri(DATABASE_URL)
    
    table_info = db.get_table_info()  
    
    custom_prompt_template = '''
    You are a SQL expert. Given the following tables and columns, please generate a syntactically correct SQL query to answer the question provided.
    
    This is data taken from various tournaments within the VCT (Valorant Champions Tour). The data includes tables that contain basic information about the players, teams, leagues and 
    tournaments from the tournament type (vct-international). Players belong to a team, teams belong to a league, leagues belong to tournaments, and the tournaments belong to the tournament
    type (vct-international). The tables game_mapping, player_mapping, and team_mapping map players to the games played within the tournaments. Teams and players are assigned internal
    player and team ids within each game. Therefore, in order to search for information about a player within the games they have played, you must search for the player id within the
    player mapping table, obtain the internal player id, and search for that internal player id within the events and event_players table. Within the event and event_players table, 
    important user-centric events about players within a game are stored. The list of events include: "player died", "spike status", "damage event", "player revived" and "ability used".
    The events table store all events that occur in all games in all tournaments conducted within a tournament type. The player_events table map players that were involved in all events
    within the events table. 
    
    For example: to obtain the events that a player has participated in within a specific tournament, you must search for the tournament id and player id within the game mapping table. 
    This will give you a list of all platform_game_ids. Then you must search for all platform_game_ids (all games) that the player has participated in and also obtain the player's 
    internal player id within those games. Then you must search through the event_players table for all desired events that the player had participated in.

    The number of results to return: {top_k}.

    Here are the available tables and columns:
    {table_info}
    
    Question: {input}
    
    SQLQuery:
    '''
    prompt = PromptTemplate.from_template(custom_prompt_template)
    
    sql_chain = create_sql_query_chain(llm=llm, db=db, prompt=prompt)
    
    response = sql_chain.invoke({
        "question": user_question,
        "table_info": table_info  
    })
    
    # Use regex to extract the SQL query from the response
    match = re.search(r"```sql\n(.*?)```", response, re.DOTALL)
    
    if match:
        sql_query = match.group(1).strip()  # Extract SQL query inside the backticks
        sql_query = sql_query.replace("\n", " ")  # Replace newline characters with spaces
    else:
        raise ValueError("No SQL query found in the response")
    
    # Use `text` to make the SQL query executable
    executable_query = text(sql_query)
    
    # Execute the SQL query against the database
    with db._engine.connect() as connection:
        result = connection.execute(executable_query)
        fetched_results = result.fetchall()
    
    return fetched_results

if __name__ == "__main__":
    test_query = "Who are the top players in the last tournament?"
    result = run_sql_chain(test_query)
    
    for row in result:
        print(row)
