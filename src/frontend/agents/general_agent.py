from typing import Dict, Optional, Union
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from dotenv import load_dotenv
import json
import asyncio
from .custom.custom_bedrock_agent import CustomBedrockLLMAgent
from .custom.custom_anthropic_agent import CustomAnthropicAgent
from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions, AnthropicAgentOptions

load_dotenv()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_db_connection():
    db_url = os.getenv('RDS_DATABASE_URL')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def get_player_comprehensive_stats(player_identifier: str = None, is_handle: bool = True) -> Dict:
    """
    Get comprehensive player statistics using either player handle or ID.
    Uses fuzzy matching for handles.
    
    Args:
        player_identifier (str): Either player handle or ID
        is_handle (bool): True if player_identifier is a handle, False if it's an ID
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # First, get the correct player_id using fuzzy matching if needed
                if is_handle:
                    player_query = """
                    SELECT player_id, handle, similarity(LOWER(handle), LOWER(%s)) AS sim
                    FROM players
                    WHERE similarity(LOWER(handle), LOWER(%s)) > 0.3
                    ORDER BY sim DESC
                    LIMIT 1
                    """
                    cur.execute(player_query, (player_identifier, player_identifier))
                    player_result = cur.fetchone()
                    if not player_result:
                        return {"status": "error", "message": "Player not found"}
                    player_id = player_result['player_id']
                else:
                    player_id = player_identifier

                # Now execute our comprehensive stats query
                stats_query = """
WITH player_base AS (
    SELECT 
        p.player_id,
        p.tournament_type,
        p.handle,
        p.first_name,
        p.last_name,
        p.status,
        p.photo_url,
        t.name as team_name,
        l.region,
        p.initiator_percentage,
        p.sentinel_percentage,
        p.duelist_percentage,
        p.controller_percentage,
        p.games_played as total_games_played
    FROM players p
    LEFT JOIN teams t ON p.home_team_id = t.team_id
    LEFT JOIN leagues l ON t.home_league_id = l.league_id
    WHERE p.player_id = %s
),

agent_stats AS (
    SELECT 
        player_id,
        agent_name,
        agent_role,
        COUNT(*) as games_played,
        AVG(kills::float) as avg_kills,
        AVG(deaths::float) as avg_deaths,
        AVG(assists::float) as avg_assists,
        AVG(combat_score::float) as avg_combat_score,
        AVG((kills::float + assists::float) / NULLIF(deaths::float, 0)) as kda
    FROM player_mapping
    WHERE player_id = %s
    GROUP BY player_id, agent_name, agent_role
),

map_stats AS (
    SELECT 
        pmp.player_id,
        pmp.map,
        pmp.games_played,
        pmp.total_kills,
        pmp.total_deaths,
        pmp.total_assists,
        pmp.average_kda,
        COUNT(DISTINCT pd.platform_game_id) as matches_with_first_blood,
        COUNT(pd.event_id) FILTER (WHERE pd.killer_id = pmp.player_id) as total_kills_on_map,
        COUNT(pd.event_id) FILTER (WHERE pd.deceased_id = pmp.player_id) as total_deaths_on_map
    FROM player_map_performance pmp
    LEFT JOIN player_died pd ON pmp.player_id = pd.killer_id OR pmp.player_id = pd.deceased_id
    WHERE pmp.player_id = %s
    GROUP BY pmp.player_id, pmp.map, pmp.games_played, pmp.total_kills, 
             pmp.total_deaths, pmp.total_assists, pmp.average_kda
),

tournament_stats AS (
    SELECT 
        pm.player_id,
        t.tournament_id,
        t.name as tournament_name,
        t.year,
        t.tournament_type,
        COUNT(DISTINCT pm.platform_game_id) as games_played,
        AVG(pm.kills::float) as avg_kills,
        AVG(pm.deaths::float) as avg_deaths,
        AVG(pm.assists::float) as avg_assists,
        AVG(pm.combat_score::float) as avg_combat_score
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    JOIN tournaments t ON gm.tournament_id = t.tournament_id
    WHERE pm.player_id = %s
    GROUP BY pm.player_id, t.tournament_id, t.name, t.year, t.tournament_type
),

tournament_agents AS (
    SELECT 
        pm.player_id,
        t.tournament_id,
        pm.agent_name,
        COUNT(*) as agent_games_played,
        AVG(pm.combat_score::float) as agent_avg_combat_score
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    JOIN tournaments t ON gm.tournament_id = t.tournament_id
    WHERE pm.player_id = %s
    GROUP BY pm.player_id, t.tournament_id, pm.agent_name
),

advanced_stats AS (
    SELECT 
        pm.player_id,
        COUNT(DISTINCT CASE WHEN pm.first_bloods > 0 THEN pm.platform_game_id END) as games_with_first_blood,
        SUM(pm.first_bloods) as total_first_bloods,
        SUM(pm.clutch_wins) as total_clutch_wins,
        COUNT(DISTINCT CASE WHEN pm.clutch_wins > 0 THEN pm.platform_game_id END) as games_with_clutch,
        SUM(pm.multi_kills) as total_multi_kills,
        AVG(pm.ability_usage_damaging::float) as avg_damage_ability_usage,
        AVG(pm.ability_usage_non_damaging::float) as avg_utility_ability_usage,
        AVG(pm.ability_effectiveness_damaging::float) as avg_damage_effectiveness,
        AVG(pm.ability_effectiveness_non_damaging::float) as avg_utility_effectiveness
    FROM player_mapping pm
    WHERE pm.player_id = %s
    GROUP BY pm.player_id
),

recent_games AS (
    SELECT 
        pm.player_id,
        pm.platform_game_id,
        gm.game_date,
        gm.map,
        pm.agent_name,
        pm.combat_score,
        pm.kills,
        pm.deaths,
        pm.assists,
        t.tournament_id,
        t.name as tournament_name,
        t.tournament_type,
        ROW_NUMBER() OVER (PARTITION BY pm.player_id ORDER BY gm.game_date DESC) as game_number
    FROM player_mapping pm
    JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
    JOIN tournaments t ON gm.tournament_id = t.tournament_id
    WHERE pm.player_id = %s
),

recent_form AS (
    SELECT 
        player_id,
        COUNT(*) as recent_matches,
        AVG(kills::float) as recent_avg_kills,
        AVG(deaths::float) as recent_avg_deaths,
        AVG(assists::float) as recent_avg_assists,
        AVG(combat_score::float) as recent_avg_combat_score,
        json_agg(
            jsonb_build_object(
                'game_id', platform_game_id,
                'date', game_date,
                'map', map,
                'agent', agent_name,
                'combat_score', combat_score,
                'kda', jsonb_build_object(
                    'kills', kills,
                    'deaths', deaths,
                    'assists', assists
                ),
                'tournament_info', jsonb_build_object(
                    'tournament_id', tournament_id,
                    'tournament_name', tournament_name,
                    'tournament_type', tournament_type
                )
            )
            ORDER BY game_date DESC
        ) as recent_games
    FROM recent_games
    WHERE game_number <= 5
    GROUP BY player_id
),

-- Final aggregation to ensure single row
final_stats AS (
    SELECT 
        pb.*,
        COALESCE(
            (SELECT json_agg(row_to_json(a)) FROM agent_stats a WHERE a.player_id = pb.player_id),
            '[]'::json
        ) as agent_statistics,
        COALESCE(
            (SELECT json_agg(row_to_json(m)) FROM map_stats m WHERE m.player_id = pb.player_id),
            '[]'::json
        ) as map_statistics,
        COALESCE(
            (SELECT json_agg(
                jsonb_build_object(
                    'tournament_id', t.tournament_id,
                    'tournament_name', t.tournament_name,
                    'year', t.year,
                    'tournament_type', t.tournament_type,
                    'games_played', t.games_played,
                    'avg_kills', t.avg_kills,
                    'avg_deaths', t.avg_deaths,
                    'avg_assists', t.avg_assists,
                    'avg_combat_score', t.avg_combat_score,
                    'agent_usage', (
                        SELECT json_agg(
                            jsonb_build_object(
                                'agent_name', ta.agent_name,
                                'games_played', ta.agent_games_played,
                                'avg_combat_score', ta.agent_avg_combat_score
                            )
                        )
                        FROM tournament_agents ta 
                        WHERE ta.tournament_id = t.tournament_id 
                        AND ta.player_id = pb.player_id
                    )
                )
            )
            FROM tournament_stats t 
            WHERE t.player_id = pb.player_id),
            '[]'::json
        ) as tournament_history,
        COALESCE(
            (SELECT row_to_json(a) FROM advanced_stats a WHERE a.player_id = pb.player_id),
            '{}'::json
        ) as advanced_metrics,
        COALESCE(
            (SELECT row_to_json(r) FROM recent_form r WHERE r.player_id = pb.player_id),
            '{}'::json
        ) as recent_performance
    FROM player_base pb
)

SELECT json_build_object(
    'player_info', row_to_json(fs.*),
    'agent_statistics', fs.agent_statistics,
    'map_statistics', fs.map_statistics,
    'tournament_history', fs.tournament_history,
    'advanced_metrics', fs.advanced_metrics,
    'recent_performance', fs.recent_performance
) as player_complete_stats
FROM final_stats fs;
                """
                
                cur.execute(stats_query, (player_id,) * 7)
                result = cur.fetchone()
                
                if result and result['player_complete_stats']:
                    return {
                        "status": "success",
                        "data": result['player_complete_stats']
                    }
                else:
                    return {
                        "status": "error",
                        "message": "No statistics found for player"
                    }

    except Exception as e:
        logger.error(f"Error in get_player_comprehensive_stats: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def bedrock_stats_handler(response, conversation):
    """Handler for Bedrock LLM responses"""
    try:
        if isinstance(response.content, list) and len(response.content) > 0:
            tool_use = response.content[0].get('toolUse', {})
            input_data = tool_use.get('input', {})

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                get_player_comprehensive_stats,
                input_data.get('player_identifier'),
                input_data.get('is_handle', True)
            )

            return json.dumps(result, default=str)
        else:
            return json.dumps({
                "status": "error",
                "message": "Unexpected response format"
            })

    except Exception as e:
        logger.error(f"Error in bedrock_stats_handler: {str(e)}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})

async def anthropic_stats_handler(response, conversation):
    """Handler for Anthropic responses"""
    try:
        # Find tool_use content block
        tool_use_blocks = [content for content in response.content if content.type == 'tool_use']
        if tool_use_blocks:
            # Get the first tool use block
            tool_block = tool_use_blocks[0]
            tool_input = tool_block.input
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                get_player_comprehensive_stats,
                tool_input.get('player_identifier'),
                tool_input.get('is_handle', True)
            )

            # Return in the correct format matching the documentation
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,  # This is the correct field name
                        "content": json.dumps(result, default=str)  # Direct content string
                    }
                ]
            }
        else:
            return {
                "role": "assistant",
                "content": "No tool use block found in the response"
            }
    except Exception as e:
        logger.error(f"Error in anthropic_stats_handler: {str(e)}", exc_info=True)
        return {
            "role": "assistant",
            "content": f"Error occurred while processing tool: {str(e)}"
        }

def setup_player_analyst_agent(use_anthropic=False, 
                             anthropic_api_key=None):
    """
    Set up the player analyst agent with either Bedrock or Anthropic backend
    """
    
    # Anthropic tool format
    anthropic_tool = {
        'tool': [{
            'name': 'get_player_stats',
            'description': """Get comprehensive statistics and information about a player. This includes:
            - Basic information (name, team, region, etc.)
            - Agent statistics and preferences
            - Map performance statistics
            - Tournament history and performance
            - Advanced metrics (first bloods, clutches, etc.)
            - Recent form (last 5 games)""",
            'input_schema': {
                'type': 'object',
                'properties': {
                    'player_identifier': {
                        'type': 'string',
                        'description': 'Player handle or ID to look up. Can be partial handle for fuzzy matching.'
                    },
                    'is_handle': {
                        'type': 'boolean',
                        'description': 'True if player_identifier is a handle, False if it\'s an ID. Defaults to True.'
                    }
                },
                'required': ['player_identifier']
            }
        }],
        'useToolHandler': anthropic_stats_handler
    }

    # Bedrock tool format
    bedrock_tool = {
        'tool': [{
            'toolSpec': {
                'name': 'get_player_stats',
                'description': """Get comprehensive statistics and information about a player. This includes:
                - Basic information (name, team, region, etc.)
                - Agent statistics and preferences
                - Map performance statistics
                - Tournament history and performance
                - Advanced metrics (first bloods, clutches, etc.)
                - Recent form (last 5 games)""",
                'inputSchema': {
                    'json': {
                        'type': 'object',
                        'properties': {
                            'player_identifier': {
                                'type': 'string',
                                'description': 'Player handle or ID to look up. Can be partial handle for fuzzy matching.'
                            },
                            'is_handle': {
                                'type': 'boolean',
                                'description': 'True if player_identifier is a handle, False if it\'s an ID. Defaults to True.'
                            }
                        }
                    }
                }
            }
        }],
        'useToolHandler': bedrock_stats_handler,
        'toolMaxRecursions': 3
    }

    if use_anthropic:
        options = AnthropicAgentOptions(
            name='Player Analysis Agent',
            description='An agent for comprehensive player analysis and statistics. Use this agent when the user asks about specific players or asks follow up questions to a team building prompt.',
            model_id='claude-3-5-sonnet-20241022',
            api_key=anthropic_api_key,
            streaming=False,
            inference_config={
                'maxTokens': 4096,
                'temperature': 0.0,
                'topP': 0.0,
                'stopSequences': ['Human:', 'AI:']
            },
            tool_config=anthropic_tool
        )
        agent = CustomAnthropicAgent(options)
    else:
        options = BedrockLLMAgentOptions(
            name='Player Analysis Agent',
            description='An agent for comprehensive player analysis and statistics. Use this agent when the user asks about specific players or asks follow up questions to a team building prompt.',
            model_id='anthropic.claude-3-sonnet-20240229-v1:0',
            region='us-east-1',
            streaming=True,
            inference_config={
                'maxTokens': 4096,
                'temperature': 0.0,
                'topP': 0.1,
                'stopSequences': ['Human:', 'AI:']
            },
            tool_config=bedrock_tool
        )
        agent = CustomBedrockLLMAgent(options)
    
    agent.set_system_prompt= """ You are an expert VALORANT Champions Tour (VCT) analyst specializing in player statistics and performance metrics. You have deep knowledge of:
            - VCT International, Challengers, and Game Changers circuits
            - Individual player performance metrics and their significance
            - Role specialization and statistical expectations
            - Competition levels across different tournament tiers
            </context>

            <role_behavior>
            As a VCT analyst, you:
            - Provide data-driven analysis using only the statistics available
            - Adapt your analysis based on the tournament type being discussed
            - Compare statistics in the context of player roles (e.g., Controllers vs. Duelists)
            - Focus on measurable performance metrics rather than speculation
            - Adapt your response format and detail level based on what the user is asking
            </role_behavior>

            <tool_usage>
            To analyze players, you must first fetch their data using the get_player_stats tool:
            - Always call this tool when a player is mentioned or analysis is needed
            - Use player's handle as the identifier when possible
            - If no handle is provided or no valid data is returned from the tool call, try searching for the player's handle
            or player id within the chat history. If you are still unable to retrieve any data, ask the user to double check
            the handle being provided
            - Set is_handle to true when searching by handle, false when using player_id
            - Wait for the tool response before providing analysis
            - Check the status of the response before proceeding
            - If the data fetch fails, inform the user and explain the issue
            - Only analyze the data that's actually returned in the response
            - Perform multiple tool calls if multiple players need to be analyzed.

            The tool returns comprehensive statistics including:
            - Player info (name, team, region, roles)
            - Recent games (last 5 matches)
            - Agent statistics
            - Map performance
            - Tournament history
            - Advanced metrics (first bloods, clutches, etc)
            </tool_usage>

            <data_handling>
            You work with statistics including:
            - Player information (name, team, region)
            - Recent match performance (last 5 games)
            - Agent-specific statistics and playtime
            - Map performance metrics
            - Tournament performance history
            - Advanced combat metrics
            - Role distribution percentages

            When analyzing data, consider:
            - Number of games played (statistical significance)
            - Recency of performance
            - Tournament tier context
            - Role-appropriate statistical expectations
            </data_handling>

            <formatting_guidelines>
            - Use clear, consistent Markdown formatting
            - Bold (**) for key statistics
            - Round all numbers to 2 decimal places
            - Include % symbol for percentages
            - Use tables when comparing multiple metrics would be helpful
            - Adapt your response length and format to match the query's needs
            </formatting_guidelines>

            <response_guidelines>
            For each request:
            1. Identify the key information needed
            2. Pull only relevant statistics from the data provided
            3. Present most important metrics first
            4. Provide tournament tier context when relevant
            5. NEVER ask which team is being referenced or request team context
            6. ALWAYS use "the team" when referring to any unspecified team
            7. Only reference a specific team if it is the player's current team as shown in the provided data

            For player analysis:
            - Focus purely on the player's statistical performance
            - Analyze the data without speculation about team fit
            - Make general statements about value to "the team" without asking for more context
            - Never request clarification about which team is being discussed

            When analyzing:
            - Roles: Focus on play time percentages and performance
            - Agents: Examine games played and success metrics
            - Maps: Look at win rates and individual performance
            - Combat: Compare based on role expectations
            </response_guidelines>


            <error_handling>
            When you encounter:
            - Missing data: Acknowledge what's missing
            - Small sample sizes: Note limited data
            - No data: Clearly state inability to analyze

            Never speculate beyond available data. State clearly when you don't have enough information to make an assessment.
            </error_handling>

            <data_priority>
            Prioritize information in this order:
            1. Basic player information
            2. Recent performance metrics
            3. Role-specific statistics
            4. Map performance data
            5. Overall career statistics

            Exclude information when:
            - Data is not relevant to the query
            - Statistics don't help answer the question
            </data_priority>"""

    return agent