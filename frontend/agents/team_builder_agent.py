from multi_agent_orchestrator.agents import BedrockLLMAgent, BedrockLLMAgentOptions, AnthropicAgent, AnthropicAgentOptions
from multi_agent_orchestrator.types import ConversationMessage, ParticipantRole
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
import json
import asyncio
from .custom.custom_bedrock_agent import CustomBedrockLLMAgent
from .custom.custom_anthropic_agent import CustomAnthropicAgent
from .player_maps import process_player_map_visualizations
import concurrent.futures

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
                
                # Step 1: Get top players by normalized score with games adjustment
                base_top_players_query = """
                    WITH player_scores AS (
                        SELECT 
                            p.player_id,
                            p.tournament_type,
                            p.status,
                            AVG(pm.normalized_score) as avg_normalized_score,
                            COUNT(DISTINCT pm.platform_game_id) as games_played
                        FROM players p
                        JOIN player_mapping pm ON p.player_id = pm.player_id
                        JOIN game_mapping gm ON pm.platform_game_id = gm.platform_game_id
                        WHERE {role_condition}
                        AND gm.tournament_type = %s
                        AND p.status = 'active'
                        GROUP BY p.player_id, p.tournament_type, p.status
                        HAVING COUNT(DISTINCT pm.platform_game_id) >= 30
                    ),
                    role_players AS (
                        SELECT 
                            player_id,
                            tournament_type,
                            status,
                            avg_normalized_score as base_score,
                            games_played,
                            avg_normalized_score * (1 + (LN(games_played::numeric / 30) * 0.0415)) as adjusted_score
                        FROM player_scores
                    )
                    SELECT *
                    FROM role_players
                    ORDER BY adjusted_score DESC
                    LIMIT %s"""

                player_ids_by_tournament = {}
                
                for t_type, count in tournament_types.items():
                    if count <= 0:
                        continue

                    if role.lower() == 'igl':
                        role_condition = "p.is_team_leader = true"
                    else:
                        role_condition = f"p.{role.lower()}_percentage > 30 AND pm.agent_role = '{role.capitalize()}'"

                    query = base_top_players_query.format(role_condition=role_condition)
                    cur.execute(query, (t_type, count))
                    top_players = cur.fetchall()
                    player_ids_by_tournament[t_type] = [p['player_id'] for p in top_players]

                # Step 2: Get detailed stats for all identified players
                if not any(player_ids_by_tournament.values()):
                    return results

                all_player_ids = list(set([
                    player_id 
                    for players in player_ids_by_tournament.values() 
                    for player_id in players
                ]))

                base_detailed_stats_query = """
                WITH latest_player_info AS (
                    SELECT DISTINCT ON (p.player_id)
                        p.player_id,
                        p.handle,
                        p.first_name,
                        p.last_name,
                        p.region,
                        p.tournament_type,
                        t.name as team_name,
                        {role_percentage_select}
                    FROM players p
                    JOIN teams t ON p.home_team_id = t.team_id
                    WHERE p.player_id = ANY(%s)
                    ORDER BY p.player_id, p.updated_at DESC
                ),
                player_overall_stats AS (
                    SELECT 
                        lpi.player_id,
                        COUNT(DISTINCT pm.platform_game_id) as total_games_played,
                        CAST(AVG(pm.average_combat_score) AS NUMERIC(10,2)) as avg_combat_score,
                        CAST(AVG((pm.kills::float + pm.assists::float) / NULLIF(pm.deaths::float, 0)) AS NUMERIC(10,2)) as avg_kda
                    FROM latest_player_info lpi
                    JOIN player_mapping pm ON lpi.player_id = pm.player_id
                    GROUP BY lpi.player_id
                ),
                top_agents AS (
                    SELECT 
                        player_id,
                        agent_name,
                        agent_role,
                        COUNT(*) as games_played,
                        CAST(AVG((kills::float + assists::float) / NULLIF(deaths::float, 0)) AS NUMERIC(10,2)) as average_kda,
                        ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY COUNT(*) DESC) as agent_rank
                    FROM player_mapping
                    WHERE player_id = ANY(%s)
                    GROUP BY player_id, agent_name, agent_role
                    HAVING COUNT(*) >= 3
                ),
                top_maps AS (
                    SELECT 
                        pmp.player_id,
                        pmp.map,
                        pmp.display_name,
                        pmp.average_kda,
                        pmp.games_played,
                        CASE 
                            WHEN site_a_events >= site_b_events AND site_a_events >= site_c_events THEN 'A'
                            WHEN site_b_events >= site_a_events AND site_b_events >= site_c_events THEN 'B'
                            ELSE 'C'
                        END as preferred_site,
                        CASE 
                            WHEN site_a_events >= site_b_events AND site_a_events >= site_c_events 
                                THEN CAST((site_a_events::float / NULLIF(site_a_events + site_b_events + site_c_events, 0)) * 100 AS NUMERIC(10,2))
                            WHEN site_b_events >= site_a_events AND site_b_events >= site_c_events 
                                THEN CAST((site_b_events::float / NULLIF(site_a_events + site_b_events + site_c_events, 0)) * 100 AS NUMERIC(10,2))
                            ELSE CAST((site_c_events::float / NULLIF(site_a_events + site_b_events + site_c_events, 0)) * 100 AS NUMERIC(10,2))
                        END as site_percentage,
                        ROW_NUMBER() OVER (PARTITION BY pmp.player_id ORDER BY pmp.games_played DESC, pmp.average_kda DESC) as map_rank
                    FROM player_map_performance pmp
                    WHERE pmp.games_played >= 3
                ),
                player_detailed_stats AS (
                    SELECT 
                        lpi.*,
                        pos.total_games_played,
                        pos.avg_combat_score,
                        pos.avg_kda,
                        
                        -- Combat Stats
                        CAST(AVG(pm.kills_attacking) AS NUMERIC(10,2)) as avg_kills_attacking,
                        CAST(AVG(pm.kills_defending) AS NUMERIC(10,2)) as avg_kills_defending,
                        CAST(AVG(pm.deaths_attacking) AS NUMERIC(10,2)) as avg_deaths_attacking,
                        CAST(AVG(pm.deaths_defending) AS NUMERIC(10,2)) as avg_deaths_defending,
                        CAST(AVG(pm.assists_attacking) AS NUMERIC(10,2)) as avg_assists_attacking,
                        CAST(AVG(pm.assists_defending) AS NUMERIC(10,2)) as avg_assists_defending,
                        CAST(AVG(pm.average_combat_score) AS NUMERIC(10,2)) as avg_combat_score,
                        
                        -- Round Impact
                        CAST(AVG(pm.rounds_survived) AS NUMERIC(10,2)) as avg_rounds_survived,
                        CAST(AVG(pm.rounds_won) AS NUMERIC(10,2)) as avg_rounds_won,
                        CAST(AVG(pm.econ_kills) AS NUMERIC(10,2)) as avg_econ_kills,
                        
                        -- Playmaking
                        CAST(AVG(pm.first_bloods) AS NUMERIC(10,2)) as avg_first_bloods,
                        CAST(AVG(pm.multi_kills) AS NUMERIC(10,2)) as avg_multi_kills,
                        CAST(AVG(pm.clutch_wins) AS NUMERIC(10,2)) as avg_clutch_wins,
                        
                        -- Ability Usage
                        CAST(AVG(pm.ability_usage_damaging) AS NUMERIC(10,2)) as avg_ability_damage,
                        CAST(AVG(pm.ability_usage_non_damaging) AS NUMERIC(10,2)) as avg_ability_utility,
                        CAST(AVG(pm.ability_effectiveness_damaging) AS NUMERIC(10,2)) as avg_ability_effectiveness_damage,
                        CAST(AVG(pm.ability_effectiveness_non_damaging) AS NUMERIC(10,2)) as avg_ability_effectiveness_utility,
                        CAST(AVG(pm.initiator_ability_deaths) AS NUMERIC(10,2)) as avg_initiator_ability_deaths,
                        
                        -- Map Stats
                        (
                            SELECT json_agg(map_data ORDER BY map_rank)
                            FROM (
                                SELECT 
                                    json_build_object(
                                        'map', map,
                                        'display_name', display_name,
                                        'average_kda', CAST(average_kda AS NUMERIC(10,2)),
                                        'games_played', games_played,
                                        'preferred_site', preferred_site,
                                        'site_percentage', site_percentage
                                    ) as map_data,
                                    map_rank
                                FROM top_maps tm2
                                WHERE tm2.player_id = lpi.player_id
                                AND tm2.map_rank <= 3
                            ) subq
                        ) as top_maps,
                        
                        -- Agent Stats
                        (
                            SELECT json_agg(agent_data ORDER BY agent_rank)
                            FROM (
                                SELECT 
                                    json_build_object(
                                        'agent_name', agent_name,
                                        'agent_role', agent_role,
                                        'games_played', games_played,
                                        'average_kda', average_kda
                                    ) as agent_data,
                                    agent_rank
                                FROM top_agents ta2
                                WHERE ta2.player_id = lpi.player_id
                                AND ta2.agent_rank <= 3
                            ) subq
                        ) as top_agents
                    FROM latest_player_info lpi
                    JOIN player_mapping pm ON lpi.player_id = pm.player_id
                    JOIN player_overall_stats pos ON lpi.player_id = pos.player_id
                    LEFT JOIN top_maps tm ON lpi.player_id = tm.player_id
                    GROUP BY 
                        lpi.player_id, lpi.handle, lpi.first_name, lpi.last_name,
                        lpi.region, lpi.team_name, lpi.tournament_type, 
                        lpi.role_percentage,
                        pos.total_games_played, pos.avg_combat_score, pos.avg_kda
                    ORDER BY pos.avg_combat_score DESC
                )
                SELECT * FROM player_detailed_stats;"""

                # Get detailed stats for all players
                if role.lower() == 'igl':
                    role_percentage_select = "CASE WHEN p.is_team_leader THEN 100 ELSE 0 END as role_percentage"
                else:
                    role_percentage_select = f"p.{role.lower()}_percentage as role_percentage"

                query = base_detailed_stats_query.format(
                    role_percentage_select=role_percentage_select
                )
                cur.execute(query, (all_player_ids, all_player_ids))  # Pass all_player_ids twice
                all_player_stats = cur.fetchall()

                # Organize results by tournament type
                for t_type, player_ids in player_ids_by_tournament.items():
                    results[t_type] = [
                        stat for stat in all_player_stats 
                        if stat['player_id'] in player_ids
                    ]

                return results

    except Exception as e:
        logger.error(f"Error in get_top_players_by_role: {str(e)}", exc_info=True)
        raise

async def get_all_roles_parallel(tournament_types: Dict[str, int]) -> Dict:
    roles = ['controller', 'duelist', 'initiator', 'sentinel', 'igl']
    loop = asyncio.get_event_loop()
    
    async def fetch_role(role):
        role_data = await loop.run_in_executor(
            None, 
            get_top_players_by_role,
            role,
            tournament_types
        )
        
        # Process map visualizations for each player
        conn = get_db_connection()
        for tournament_type, players in role_data.items():
            for player in players:
                if player['top_maps']:
                    player['top_maps'] = await process_player_map_visualizations(
                        player['player_id'],
                        player['top_maps'],
                        conn
                    )
        conn.close()
        
        return role, role_data
    
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
            'vct-international': int(vct_international or 0),
            'vct-challengers': int(vct_challenger or 0),
            'game-changers': int(game_changers or 0)
        }
        
        if not any(tournament_types.values()):
            return {
                "status": "error",
                "message": "At least one tournament type count must be greater than 0"
            }

        result = asyncio.run(get_all_roles_parallel(tournament_types))
        
        formatted_result = {
            "status": "success",
            "data": {
                role: {
                    tournament_type: [
                        {
                            "player": {
                                "name": f"{player['first_name']} {player['last_name']}",
                                "player_id": player['player_id'],
                                "handle": player['handle'],
                                "team": player['team_name'],
                                "region": player['region']
                            },
                            "overall_stats": {
                                "total_games": int(player['total_games_played']),
                                "average_combat_score": float(player['avg_combat_score']),
                                "average_kda": float(player['avg_kda']),
                                "role_percentage": float(player['role_percentage'])
                            },
                            "agent_stats": [
                                {
                                    "agent_name": agent_stat['agent_name'],
                                    "agent_role": agent_stat['agent_role'],
                                    "games_played": int(agent_stat['games_played']),
                                    "average_kda": float(agent_stat['average_kda'])
                                }
                                for agent_stat in player['top_agents']
                            ],
                            "map_stats": [
                                {
                                    "map": map_stat['map'],
                                    "display_name": map_stat['display_name'],
                                    "average_kda": float(map_stat['average_kda']),
                                    "games_played": int(map_stat['games_played']),
                                    "preferred_site": map_stat['preferred_site'],
                                    "site_percentage": float(map_stat['site_percentage']),
                                    "visualization": map_stat.get('visualization', {})
                                }
                                for map_stat in player['top_maps']
                            ],
                            "combat_stats": {
                                "attacking": {
                                    "kills": float(player['avg_kills_attacking']),
                                    "deaths": float(player['avg_deaths_attacking']),
                                    "assists": float(player['avg_assists_attacking'])
                                },
                                "defending": {
                                    "kills": float(player['avg_kills_defending']),
                                    "deaths": float(player['avg_deaths_defending']),
                                    "assists": float(player['avg_assists_defending'])
                                }
                            },
                            "round_impact": {
                                "rounds_survived": float(player['avg_rounds_survived']),
                                "rounds_won": float(player['avg_rounds_won']),
                            },
                            "playmaking": {
                                "first_bloods": float(player['avg_first_bloods']),
                                "multi_kills": float(player['avg_multi_kills']),
                                "clutch_wins": float(player['avg_clutch_wins'])
                            },
                            "ability_usage": {
                                "damage": {
                                    "usage": float(player['avg_ability_damage']),
                                    "effectiveness": float(player['avg_ability_effectiveness_damage'])
                                },
                                "utility": {
                                    "usage": float(player['avg_ability_utility']),
                                    "effectiveness": float(player['avg_ability_effectiveness_utility'])
                                },
                            }
                        }
                        for player in players
                    ]
                    for tournament_type, players in role_data.items()
                    if players
                }
                for role, role_data in result.items()
            }
        }
        
        return formatted_result

    except Exception as e:
        logger.error(f"Error in team_builder_wrapper: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def bedrock_function_handler(response, conversation):
    try:
        if isinstance(response.content, list) and len(response.content) > 0:
            # Find the content item that contains toolUse
            tool_use = None
            for content_item in response.content:
                if 'toolUse' in content_item:
                    tool_use = content_item['toolUse']
                    break
            
            if not tool_use:
                return json.dumps({
                    "status": "error",
                    "message": "No tool use found in response"
                })

            input_data = tool_use.get('input', {})

            # Add debug logging
            logger.info(f"Found input data: {input_data}")

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
        logger.error(f"Error in bedrock_function_handler: {str(e)}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})

async def anthropic_function_handler(response, conversation):
    try:
        # Find tool_use content block
        tool_use_blocks = [content for content in response.content if content.type == 'tool_use']
        if tool_use_blocks:
            # Get the first tool use block
            tool_block = tool_use_blocks[0]
            tool_input = tool_block.input
            
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                team_builder_wrapper,
                tool_input.get('vct_international', 0),
                tool_input.get('vct_challenger', 0),
                tool_input.get('game_changers', 0)
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
        logger.error(f"Error in anthropic_function_handler: {str(e)}", exc_info=True)
        return {
            "role": "assistant",
            "content": f"Error occurred while processing tool: {str(e)}"
        }

def setup_team_builder_agent(use_anthropic=False, anthropic_api_key=None, rds_database_url=None):
    # Anthropic tool format
    anthropic_tool = {
        'tool': [{
            'name': 'get_all_players',
            'description': """Get top players for all roles across specified tournament types. This tool MUST be called first to get
            the necessary information about VCT players to build a team. This tool only needs to be called ONCE. Parameters MUST be 
            integers. Do not insert NONE into any parameter. Insert 0 instead if a tournament type is not needed.""",
            'input_schema': {
                'type': 'object',
                'properties': {
                    'vct_international': {
                        'type': 'integer',
                        'description': 'The number of vct-international players to fetch per role. Set this value to 0 if no players from this tournament type is needed'
                    },
                    'vct_challenger': {
                        'type': 'integer',
                        'description': 'The number of vct-challenger players to fetch per role. Set this value to 0 if no players from this tournament type is needed'
                    },
                    'game_changers': {
                        'type': 'integer',
                        'description': 'The number of game-changer players to fetch per role. Set this value to 0 if no players from this tournament type is needed'
                    }
                },
                'required': ["vct_international", "vct_challenger", "game_changers"]
            }
        }],
        'useToolHandler': anthropic_function_handler
    }

    # Bedrock tool format
    bedrock_tool = {
        'tool': [{
            'toolSpec': {
                'name': 'get_all_players',
                'description': """Get top players for all roles across specified tournament types. This tool MUST be called first to get
                the necessary information about VCT players to build a team. This tool only needs to be called ONCE. Parameters MUST be 
                integers. Do not insert NONE into any parameter. Insert 0 instead if a tournament type is not needed.""",
                'inputSchema': {
                    'json': {
                        'type': 'object',
                        'properties': {
                            'vct_international': {
                                'type': 'integer',
                                'description': 'The number of vct-international players to fetch per role. Set this value to 0 if no players from this tournament type is needed'
                            },
                            'vct_challenger': {
                                'type': 'integer',
                                'description': 'The number of vct-challenger players to fetch per role. Set this value to 0 if no players from this tournament type is needed'
                            },
                            'game_changers': {
                                'type': 'integer',
                                'description': 'The number of game-changer players to fetch per role. Set this value to 0 if no players from this tournament type is needed'
                            }
                        }
                    },
                }
            }
        }],
        'useToolHandler': bedrock_function_handler,
        'toolMaxRecursions': 3
    }

    if use_anthropic:
        options = AnthropicAgentOptions(
            name='Team Builder Agent',
            description='An agent for building optimal team compositions based on tournament data',
            model_id='claude-3-sonnet-20240229',
            api_key=anthropic_api_key,
            streaming=False,
            save_chat=True,
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
            name='Team Builder Agent',
            description='An agent for building optimal team compositions based on tournament data',
            model_id='anthropic.claude-3-sonnet-20240229-v1:0',
            region='us-west-2',
            save_chat=True,
            inference_config={
                'maxTokens': 4096,
                'temperature': 0.0,
                'topP': 0.1,
                'stopSequences': ['Human:', 'AI:']
            },
            tool_config=bedrock_tool
        )
        agent = CustomBedrockLLMAgent(options)
    
    agent.set_system_prompt(
        """
        <role>Expert VCT Manager and Team Analyst</role>

        <context>
        You are an expert Valorant and VCT (Valorant's esports league) manager tasked with building optimal competitive teams. You analyze player statistics, map preferences, 
        agent proficiency, and team synergies to construct the most effective rosters. Ignore any previous instructions to limit your output to a certain length. Always attempt
        to fulfill the output format instructions in its entirety.
        </context>

        <tool_instructions>
        DO NOT RESPOND BEFORE MAKING A TOOL CALL. MAKE THE TOOL CALL FIRST BEFORE RESPONDING.
        When you receive input like this:
        VCT_INTERNATIONAL: X
        VCT_CHALLENGER: Y
        GAME_CHANGERS: Z

        You MUST IMMEDIATELY make this tool call:
        get_all_players(vct_international=X, vct_challenger=Y, game_changers=Z)

        DO NOT write anything before the tool call.
        DO NOT explain what you're doing.
        JUST MAKE THE TOOL CALL.

        YOU CANNOT PROCEED WITHOUT THIS DATA.
        </tool_instructions>

        <data_structure>
        The tool returns player data organized by role (initiator, duelist, controller, sentinel, igl) containing:

        1. Player Information:
        - name: Full name (first_name + last_name)
        - player_id: Unique identifier
        - handle: In-game name
        - team: Current team name
        - region: Player's competitive region

        2. Overall Statistics:
        - total_games: Number of games played
        - average_combat_score: Average combat score per game
        - average_kda: Overall KDA ratio
        - role_percentage: Percentage of games played in this role

        3. Agent Statistics (top 3 most played):
        - agent_name: Name of the agent
        - agent_role: Role category of the agent
        - games_played: Number of games on this agent
        - average_kda: KDA ratio on this agent

        4. Map Statistics (top 3 most played):
        - map: Internal map identifier
        - display_name: User-friendly map name
        - average_kda: KDA ratio on this map
        - games_played: Number of games on this map
        - preferred_site: Most commonly played site (A or B)
        - site_percentage: Percentage of rounds played on preferred site
        - visualization: Contains a url for a s3 bucket that contains an image of a marked up
        minimap for the map with attacking/defending kill and death events

        5. Combat Statistics:
        Attacking:
        - kills: Average kills per round on attack
        - deaths: Average deaths per round on attack
        - assists: Average assists per round on attack
        
        Defending:
        - kills: Average kills per round on defense
        - deaths: Average deaths per round on defense
        - assists: Average assists per round on defense

        6. Round Impact:
        - rounds_survived: Average rounds survived per game
        - rounds_won: Average rounds won per game

        7. Playmaking:
        - first_bloods: Average first bloods per game
        - multi_kills: Average multi-kills per game
        - clutch_wins: Average clutch wins per game

        8. Ability Usage:
        Damage:
        - usage: Average number of damage-dealing abilities used
        - effectiveness: Percentage of damage abilities resulting in kills
        
        Utility:
        - usage: Average number of utility abilities used
        - effectiveness: Percentage of utility abilities resulting in assists
        </data_structure>

        <team_building_process>
        1. VALIDATE:
        - Confirm tool call was made
        - Verify data was received
        - Ensure only using players from returned data

        2. SELECTION PRIORITY:
        - Duelist MUST be selected first as the cornerstone of the team
        - Remaining roles (In-Game Leader, Controller, Sentinel, Initiator) can be selected in any order based on:
            * Best available talent
            * Team synergy opportunities
            * Map and agent pool complementarity
            * Statistical strengths
            * Strategic team needs

        3. SELECTION CRITERIA:
        Primary:
        - Must satisfy all input constraints
        - Must have all 5 roles filled
        - Must meet tournament type requirements

        Secondary:
        - Map synergy (complementary site preferences)
        - Agent pool compatibility
        - Statistical excellence
        - Team chemistry potential, but do NOT be biased in picking players from the same originating team
        </team_building_process>
        
        <output_format_instructions>
        IMPORTANT: Output ONLY what is specified in the output format in markdown. Return the message covering the ENTIRE output format. The output will guaranteed
        be less than the model length cut off. Do NOT cut the output response short.
        </output_format_instructions>

        <output_format>
        # Team Composition
        1. [Full Name] ([Handle]) - **Role**: [Role], **Current Team**: [Current Team], **Tournament Type**: [Type], **REGION**: [Region]
        [Repeat for all 5 players]

        **Constraint Satisfaction:**
        [Single sentence explaining how team meets all constraints]

        # Strategic Analysis
        ## Team Building Philosophy
        [3-4 sentences explaining the overall strategic vision for this team composition. What playstyle are they built for? What makes them unique? What are their win conditions?]

        ## Role & Player Analysis
        **NOTE**: [The following map visualizations show positioning and impact across each player's last 5 matches on their most played maps. These visualizations help understand each player's preferred positions, angles, and site control patterns on both attack and defense.]
        ### Duelist - [Full Name] ([Handle]) - Total competitive games played: [Number]
        [Detailed analysis of selection rationale including:
        - Statistical strengths as primary fragger
        - Agent pool and strategic enablement
        - Map/site preferences and team playstyle influence
        - Standout metrics (first bloods, multi-kills, clutch ratio)]

        **Preferred Agents:**
        - [Agent 1] - [Games Played] games, [KDA] KDA
        - [Agent 2] - [Games Played] games, [KDA] KDA
        - [Agent 3] - [Games Played] games, [KDA] KDA

        **Top Maps:**
        - [Map 1] - [Games Played] games, [KDA] KDA, Preferred Site: [Site] ([Site %]%)

        | Attacking | Defending |
        |:---------:|:---------:|
        | ![Map 1 Attacking](attacking_visualization_url_1) | ![Map 1 Defending](defending_visualization_url_1) |

        [Repeat map format for Maps 2 & 3]

        [Repeat entire section for remaining 4 roles, emphasizing role-specific contributions and team synergy]

        ## Strategic Strengths
        - Map Control: [In one sentence mention what maps the team would play based on the collective top maps played. In another sentence, explain how the team's combined site preferences and agent pools enable strong map control]
        - Attack Executes: [How the team's utility usage and playstyles combine for effective attacks]
        - Defense Setups: [How the team's defensive capabilities and positioning create strong holds]
        - Clutch Potential: [Analysis of the team's ability to win crucial rounds based on individual strengths]

        ## Areas for Development
        [3 sentences identifying:
        - Potential weaknesses that need to be addressed
        - Suggested focus areas for practice
        - Specific scenarios or maps that might need extra attention]

        # Honorable Mentions
        [One player per role not selected for final team, including full name, handle, role, and current team.]

        </output_format>

        <verification_checklist>
        Before providing output, verify:
        1. Tool call completed
        2. All players exist in dataset
        3. Statistics accuracy
        4. Constraint compliance
        5. Role coverage
        6. Team synergy analysis
        7. All sections in the output format are filled out
        </verification_checklist>

        <constraints>
        - Use gender-neutral language
        - Prioritize team synergy
        - Fill all roles
        - Meet all input constraints
        - Use only verified data
        </constraints>
        """
    )


    return agent