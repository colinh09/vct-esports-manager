import logging
from game_queries import get_all_player_games, get_all_player_games_from_tournament, get_damage_stats, get_assists, get_deaths

logger = logging.getLogger()

def get_player_game_stats(player_id):
    try:
        all_games = get_all_player_games(player_id, 'vct-international')
        return calculate_aggregated_stats(all_games)
    except Exception as e:
        logger.error(f"Error in get_player_game_stats: {str(e)}")
        raise

def get_player_tournament_stats(player_id, tournament_id):
    try:
        tournament_games = get_all_player_games_from_tournament(player_id, 'vct-international', tournament_id)
        stats = calculate_aggregated_stats(tournament_games)
        stats['tournament_id'] = tournament_id
        return stats
    except Exception as e:
        logger.error(f"Error in get_player_tournament_stats: {str(e)}")
        raise

def calculate_aggregated_stats(games):
    total_damage = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    
    for game in games:
        platform_game_id = game['platform_game_id']
        internal_player_id = game['internal_player_id']
        
        damage_stats = get_damage_stats(platform_game_id, internal_player_id)
        assists = get_assists(platform_game_id, internal_player_id)
        deaths = get_deaths(platform_game_id, internal_player_id)
        
        total_damage += sum(stat['damage_amount'] for stat in damage_stats)
        total_kills += sum(1 for stat in damage_stats if stat['kill_event'])
        total_deaths += len(deaths)
        total_assists += len(assists)
    
    games_played = len(games)
    
    return {
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