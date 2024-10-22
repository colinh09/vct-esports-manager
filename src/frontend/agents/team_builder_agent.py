from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from dotenv import load_dotenv
import json
import asyncio
from .custom.custom_bedrock_agent import CustomBedrockLLMAgent
import concurrent.futures

load_dotenv()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_db_connection():
    db_url = os.getenv('RDS_DATABASE_URL')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def get_top_players_by_role(role: str, tournament_types: Dict[str, int]) -> Dict:
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                results = {}
                base_query = """
                WITH player_stats AS (
                    SELECT p.player_id, p.handle, p.first_name, p.last_name, 
                           t.name as team_name, l.region, p.{role}_percentage as role_percentage,
                           COUNT(DISTINCT pm.platform_game_id) as role_games,
                           SUM(pm.kills) as total_kills, SUM(pm.deaths) as total_deaths, 
                           SUM(pm.assists) as total_assists
                    FROM players p
                    JOIN player_mapping pm ON p.player_id = pm.player_id
                    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
                    JOIN teams t ON p.home_team_id = t.team_id
                    JOIN leagues l ON t.home_league_id = l.league_id
                    WHERE p.{role}_percentage > 30
                    AND gm.tournament_type = %s
                    {additional_where}
                    GROUP BY p.player_id, p.handle, p.first_name, p.last_name, 
                             t.name, l.region, p.{role}_percentage
                )
                SELECT *, 
                       CASE 
                           WHEN total_kills + total_assists > 0 AND total_deaths > 0
                           THEN CAST(
                                (CAST(total_kills + total_assists AS NUMERIC) / 
                                 CAST(total_deaths AS NUMERIC)) * 100 AS NUMERIC(10,2)
                               ) / 100.0
                           ELSE NULL 
                       END as kda_ratio
                FROM player_stats
                WHERE role_games > 0
                ORDER BY kda_ratio DESC NULLS LAST
                LIMIT %s"""

                for t_type, count in tournament_types.items():
                    if count <= 0:
                        continue

                    if role.lower() == 'igl':
                        query = base_query.format(
                            role='duelist',  # Placeholder, not used for IGL
                            additional_where="AND p.is_team_leader = true"
                        )
                    else:
                        query = base_query.format(
                            role=role.lower(),
                            additional_where=f"AND pm.agent_role = '{role.capitalize()}'"
                        )

                    cur.execute(query, (t_type, count))
                    results[t_type] = [dict(row) for row in cur.fetchall()]

                return results

    except Exception as e:
        logger.error(f"Error in get_top_players_by_role: {str(e)}", exc_info=True)
        raise

async def get_all_roles_parallel(tournament_types: Dict[str, int]) -> Dict:
    roles = ['controller', 'duelist', 'initiator', 'sentinel', 'igl']
    loop = asyncio.get_event_loop()
    
    async def fetch_role(role):
        return role, await loop.run_in_executor(
            None, 
            get_top_players_by_role,
            role,
            tournament_types
        )
    
    tasks = [fetch_role(role) for role in roles]
    results = await asyncio.gather(*tasks)
    
    return {role: data for role, data in results}

def team_builder_wrapper(vct_international: int = 0, 
                        vct_challenger: int = 0, 
                        game_changers: int = 0) -> Dict:
    logger.info(f"team_builder_wrapper called with "
                f"vct_international={vct_international}, "
                f"vct_challenger={vct_challenger}, "
                f"game_changers={game_changers}")
    try:
        tournament_types = {
            'vct-international': vct_international,
            'vct-challengers': vct_challenger,
            'game-changers': game_changers
        }
        
        if not any(tournament_types.values()):
            return {
                "status": "error",
                "message": "At least one tournament type count must be greater than 0"
            }

        # Run the async function to get all roles in parallel
        result = asyncio.run(get_all_roles_parallel(tournament_types))
        
        # Format the results nicely
        formatted_result = {
            "status": "success",
            "data": {
                role: {
                    tournament_type: [
                        {
                            "player": {
                                "name": f"{player['first_name']} {player['last_name']}",
                                "handle": player['handle'],
                                "team": player['team_name'],
                                "region": player['region']
                            },
                            "stats": {
                                "role_percentage": float(player['role_percentage']),
                                "games_played": int(player['role_games']),
                                "kills": int(player['total_kills']),
                                "deaths": int(player['total_deaths']),
                                "assists": int(player['total_assists']),
                                "kda_ratio": float(player['kda_ratio']) if player['kda_ratio'] is not None else None
                            }
                        }
                        for player in players
                    ]
                    for tournament_type, players in role_data.items()
                    if players  # Only include tournament types with players
                }
                for role, role_data in result.items()
            }
        }
        
        return formatted_result

    except Exception as e:
        logger.error(f"Error in team_builder_wrapper: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def custom_function_handler(response, conversation):
    try:
        if isinstance(response.content, list) and len(response.content) > 0:
            tool_use = response.content[0].get('toolUse', {})
            input_data = tool_use.get('input', {})

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                team_builder_wrapper,
                input_data.get('vct_international', 0),
                input_data.get('vct_challenger', 0),
                input_data.get('game_changers', 0)
            )

            return json.dumps(result, default=str)
        else:
            return json.dumps({
                "status": "error",
                "message": "Unexpected response format"
            })

    except Exception as e:
        logger.error(f"Error in custom_function_handler: {str(e)}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})

def setup_team_builder_agent(
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
        name='Team Builder Agent',
        description='An agent for building optimal team compositions based on tournament data',
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
                        'name': 'get_all_players',
                        'description': 'Get top players for all roles across specified tournament types.',
                        'inputSchema': {
                            'json': {
                                'type': 'object',
                                'properties': {
                                    'vct_international': {
                                        'type': 'integer',
                                        'description': 'The number of vct-international players to fetch per role. Default value is 0.'
                                    },
                                    'vct_challenger': {
                                        'type': 'integer',
                                        'description': 'The number of vct-challenger players to fetch per role. Default value is 0.'
                                    },
                                    'game_changers': {
                                        'type': 'integer',
                                        'description': 'The number of game-changer players to fetch per role. Default value is 0.'
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
    agent = CustomBedrockLLMAgent(options)

    agent.set_system_prompt(
        """Your main goal is to call the get_all_players action with the tournament type counts provided to you. The number of players for each tournament type
        will be given as VCT_INTERNATIONAL: [number], VCT_CHALLENGER: [number], and GAME_CHANGERS: [number]. The function will automatically fetch players for all roles
        (controller, duelist, initiator, sentinel, and igl) in parallel. Format the response in a clean JSON structure with player statistics and team information."""
    )

    return agent