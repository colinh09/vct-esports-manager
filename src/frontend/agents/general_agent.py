from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions
from multi_agent_orchestrator.retrievers import Retriever
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from typing import List, Dict, Union, Optional, AsyncIterable, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from dotenv import load_dotenv
import json
import asyncio
from custom_bedrock_agent import CustomBedrockLLMAgent 

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_db_connection():
    db_url = os.getenv('RDS_DATABASE_URL')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

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

async def custom_function_handler(response, conversation):
    try:
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response content: {response.content}")

        if isinstance(response.content, list) and len(response.content) > 0:
            tool_use = response.content[0].get('toolUse', {})
            input_data = tool_use.get('input', {})

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                get_player_info_wrapper,
                input_data.get('handle'),
                input_data.get('first_name'),
                input_data.get('last_name')
            )

            # Just JSON dump the result
            json_result = json.dumps(result, default=str)

            # Create a user message with the JSON result
            user_message = ConversationMessage(
                role=ParticipantRole.USER.value,
                content=[{'text': json_result}]
            )

            return False, (json_result, user_message)
        else:
            error_result = json.dumps({"status": "error", "message": "Unexpected response format"})
            logger.error("Unexpected response format")
            return False, (error_result, None)
    except Exception as e:
        logger.error(f"Error in custom_function_handler: {str(e)}", exc_info=True)
        error_result = json.dumps({"status": "error", "message": str(e)})
        return False, (error_result, None)

def setup_player_info_agent(
    model_id='ai21.jamba-1-5-mini-v1:0',
    region='us-east-1',
    max_tokens=1000,
    temperature=0.7,
    top_p=0.9,
    stop_sequences=None
):
    if stop_sequences is None:
        stop_sequences = ['Human:', 'AI:']

    options = BedrockLLMAgentOptions(
        name='Player Info Agent',
        description='An agent for retrieving player information',
        model_id=model_id,
        region=region,
        streaming=False,
        inference_config={
            'maxTokens': max_tokens,
            'temperature': temperature,
            'topP': top_p,
            'stopSequences': stop_sequences
        },
        tool_config={
            'tool': [
                {
                    'toolSpec': {
                        'name': 'get_player_info',
                        'description': 'Get information about a player',
                        'inputSchema': {
                            'json': {
                                'type': 'object',
                                'properties': {
                                    'handle': {
                                        'type': 'string',
                                        'description': 'The player\'s handle. This is the most common way to identify a player.'
                                    },
                                    'first_name': {
                                        'type': 'string',
                                        'description': 'The player\'s first name'
                                    },
                                    'last_name': {
                                        'type': 'string',
                                        'description': 'The player\'s last name'
                                    }
                                }
                            }
                        }
                    }
                }
            ],
            'useToolHandler': custom_function_handler
        }
    )

    return CustomBedrockLLMAgent(options)