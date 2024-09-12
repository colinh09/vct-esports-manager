import logging
from langchain.tools import tool
from backend.queries.player_info import PlayerInfoQueries
from backend.queries.player_games import PlayerGameStatsQueries
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

player_info_instance = PlayerInfoQueries()
player_stats_instance = PlayerGameStatsQueries()

# Player Info Tools

@tool
def get_player_info_by_handle(handle: str) -> Dict[str, Any]:
    """
    Fetches player information based on the player's handle.
    
    :param handle: The handle (nickname) of the player
    :return: A dictionary containing player information with team and league details, including the player's ID
    """
    logger.info(f"Tool called: get_player_info_by_handle with handle: {handle}")
    player_info = player_info_instance.get_player_info_by_handle(handle)
    if player_info:
        result = {
            'player_id': player_info['player_id'],
            'handle': player_info['handle'],
            'first_name': player_info['first_name'],
            'last_name': player_info['last_name'],
            'status': player_info['status'],
            'team': {
                'name': player_info['team_name'],
                'acronym': player_info['team_acronym'],
                'slug': player_info['team_slug'],
                'dark_logo_url': player_info['dark_logo_url'],
                'light_logo_url': player_info['light_logo_url']
            },
            'league': {
                'name': player_info['league_name'],
                'region': player_info['league_region']
            }
        }
        logger.info(f"Player info retrieved for handle {handle}: player_id = {result['player_id']}")
        return result
    logger.warning(f"No player found with handle: {handle}")
    return None

@tool
def get_player_info_by_name(first_name: str, last_name: str) -> Dict[str, Any]:
    """
    Fetches player information based on the player's first and last name.
    
    :param first_name: The player's first name
    :param last_name: The player's last name
    :return: A dictionary containing player information with team and league details
    """
    logger.info(f"Tool called: get_player_info_by_name with name: {first_name} {last_name}")
    player_info = player_info_instance.get_player_info_by_name(first_name, last_name)
    if player_info:
        return {
            'handle': player_info['handle'],
            'first_name': player_info['first_name'],
            'last_name': player_info['last_name'],
            'status': player_info['status'],
            'team': {
                'name': player_info['team_name'],
                'acronym': player_info['team_acronym'],
                'slug': player_info['team_slug'],
                'dark_logo_url': player_info['dark_logo_url'],
                'light_logo_url': player_info['light_logo_url']
            },
            'league': {
                'name': player_info['league_name'],
                'region': player_info['league_region']
            }
        }
    logger.warning(f"No player found with name: {first_name} {last_name}")
    return None

# Player Stats Tools

@tool
def get_player_game_stats(player_id: str) -> Dict[str, Any]:
    """
    Fetches and aggregates stats for a player across all their VCT International games.
    
    :param player_id: The player's unique ID
    :return: A dictionary containing aggregated stats for the player
    """
    logger.info(f"Tool called: get_player_game_stats with player_id: {player_id}")
    all_games = player_stats_instance.get_all_player_games(player_id, 'vct-international')
    
    total_damage = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    
    for game in all_games:
        platform_game_id = game['platform_game_id']
        internal_player_id = game['internal_player_id']
        
        damage_stats = player_stats_instance.get_damage_stats(platform_game_id, internal_player_id)
        assists = player_stats_instance.get_assists(platform_game_id, internal_player_id)
        deaths = player_stats_instance.get_deaths(platform_game_id, internal_player_id)
        
        total_damage += sum(stat['damage_amount'] for stat in damage_stats)
        total_kills += sum(1 for stat in damage_stats if stat['kill_event'])
        total_deaths += len(deaths)
        total_assists += len(assists)
    
    games_played = len(all_games)
    
    aggregated_stats = {
        'games_played': games_played,
        'total_damage': total_damage,
        'total_kills': total_kills,
        'total_deaths': total_deaths,
        'total_assists': total_assists,
        'average_damage_per_game': total_damage / games_played if games_played > 0 else 0,
        'average_kills_per_game': total_kills / games_played if games_played > 0 else 0,
        'average_deaths_per_game': total_deaths / games_played if games_played > 0 else 0,
        'average_assists_per_game': total_assists / games_played if games_played > 0 else 0,
        'kda_ratio': (total_kills + total_assists) / total_deaths if total_deaths > 0 else (total_kills + total_assists)
    }
    
    logger.info(f"Aggregated stats calculated for player {player_id} over {games_played} VCT International games")
    return aggregated_stats

@tool
def get_player_tournament_stats(player_id: str, tournament_id: str) -> Dict[str, Any]:
    """
    Fetches and aggregates stats for a player in a specific VCT International tournament.
    
    :param player_id: The player's unique ID
    :param tournament_id: The ID of the specific tournament
    :return: A dictionary containing aggregated stats for the player in the tournament
    """
    logger.info(f"Tool called: get_player_tournament_stats with player_id: {player_id}, tournament_id: {tournament_id}")
    tournament_games = player_stats_instance.get_all_player_games_from_tournament(player_id, 'vct-international', tournament_id)
    
    total_damage = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    
    for game in tournament_games:
        platform_game_id = game['platform_game_id']
        internal_player_id = game['internal_player_id']
        
        damage_stats = player_stats_instance.get_damage_stats(platform_game_id, internal_player_id)
        assists = player_stats_instance.get_assists(platform_game_id, internal_player_id)
        deaths = player_stats_instance.get_deaths(platform_game_id, internal_player_id)
        
        total_damage += sum(stat['damage_amount'] for stat in damage_stats)
        total_kills += sum(1 for stat in damage_stats if stat['kill_event'])
        total_deaths += len(deaths)
        total_assists += len(assists)
    
    games_played = len(tournament_games)
    
    aggregated_stats = {
        'tournament_id': tournament_id,
        'games_played': games_played,
        'total_damage': total_damage,
        'total_kills': total_kills,
        'total_deaths': total_deaths,
        'total_assists': total_assists,
        'average_damage_per_game': total_damage / games_played if games_played > 0 else 0,
        'average_kills_per_game': total_kills / games_played if games_played > 0 else 0,
        'average_deaths_per_game': total_deaths / games_played if games_played > 0 else 0,
        'average_assists_per_game': total_assists / games_played if games_played > 0 else 0,
        'kda_ratio': (total_kills + total_assists) / total_deaths if total_deaths > 0 else (total_kills + total_assists)
    }
    
    logger.info(f"Aggregated stats calculated for player {player_id} over {games_played} games in tournament {tournament_id}")
    return aggregated_stats


tools = [
    get_player_info_by_handle,
    get_player_info_by_name,
    get_player_game_stats,
    get_player_tournament_stats
]