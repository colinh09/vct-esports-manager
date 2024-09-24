import logging
from game_queries import get_all_player_games, get_all_player_games_from_tournament, get_damage_stats, get_assists, get_deaths
from datetime import datetime

logger = logging.getLogger()

def get_player_stats(player_id, tournament_id=None, tournament_type='vct-international', start_date=None, end_date=None):
    try:
        if tournament_id:
            games = get_all_player_games_from_tournament(player_id, tournament_type, tournament_id, start_date, end_date)
        else:
            games = get_all_player_games(player_id, tournament_type, start_date, end_date)
        
        stats = calculate_aggregated_stats(games)
        if tournament_id:
            stats['tournament_id'] = tournament_id
        return stats
    except Exception as e:
        logger.error(f"Error in get_player_stats: {str(e)}")
        raise

def calculate_aggregated_stats(games):
    total_damage = 0
    total_kills = 0
    total_deaths = 0
    total_assists = 0
    valid_games = 0
    
    for game in games:
        platform_game_id = game['platform_game_id']
        internal_player_id = game['internal_player_id']
        
        damage_stats = get_damage_stats(platform_game_id, internal_player_id)
        assists = get_assists(platform_game_id, internal_player_id)
        deaths = get_deaths(platform_game_id, internal_player_id)
        
        game_damage = sum(stat['damage_amount'] for stat in damage_stats if stat['damage_amount'])
        game_kills = sum(1 for stat in damage_stats if stat['kill_event'])
        game_deaths = len([d for d in deaths if d])
        game_assists = len([a for a in assists if a])
        
        if game_damage or game_kills or game_deaths or game_assists:
            total_damage += game_damage
            total_kills += game_kills
            total_deaths += game_deaths
            total_assists += game_assists
            valid_games += 1
    
    stats = {
        'games_played': valid_games,
        'total_damage': total_damage,
        'total_kills': total_kills,
        'total_deaths': total_deaths,
        'total_assists': total_assists,
    }
    
    if valid_games > 0:
        stats.update({
            'average_damage_per_game': total_damage / valid_games,
            'average_kills_per_game': total_kills / valid_games,
            'average_deaths_per_game': total_deaths / valid_games,
            'average_assists_per_game': total_assists / valid_games,
        })
    
    if total_deaths > 0:
        stats['kda_ratio'] = (total_kills + total_assists) / total_deaths
    elif total_kills + total_assists > 0:
        stats['kda_ratio'] = float('inf')
    
    return stats

def get_player_best_agents(player_id, tournament_id=None, tournament_type='vct-international', start_date=None, end_date=None):
    try:
        if tournament_id:
            games = get_all_player_games_from_tournament(player_id, tournament_type, tournament_id, start_date, end_date)
        else:
            games = get_all_player_games(player_id, tournament_type, start_date, end_date)
        
        agent_stats = {}
        for game in games:
            agent_name = game['agent_name']
            
            if not agent_name:
                continue
            
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {'games': 0, 'kills': 0, 'deaths': 0, 'assists': 0, 'average_combat_score': 0}
            
            agent_stats[agent_name]['games'] += 1
            
            if game['kills']:
                agent_stats[agent_name]['kills'] += game['kills']
            if game['deaths']:
                agent_stats[agent_name]['deaths'] += game['deaths']
            if game['assists']:
                agent_stats[agent_name]['assists'] += game['assists']
            if game['average_combat_score']:
                agent_stats[agent_name]['average_combat_score'] += game['average_combat_score']
        
        for agent, stats in agent_stats.items():
            if stats['deaths'] > 0:
                stats['kda'] = (stats['kills'] + stats['assists']) / stats['deaths']
            elif stats['kills'] + stats['assists'] > 0:
                stats['kda'] = float('inf')
            else:
                stats['kda'] = 0
            stats['avg_average_combat_score'] = stats['average_combat_score'] / agent_stats[agent]['games'] if agent_stats[agent]['games'] > 0 else 0
        
        return sorted(agent_stats.items(), key=lambda x: (x[1]['kda'], x[1]['avg_average_combat_score']), reverse=True)
    
    except Exception as e:
        logger.error(f"Error in get_player_best_agents: {str(e)}")
        raise

def get_player_performance_trend(player_id, start_date, end_date, tournament_id=None, tournament_type='vct-international'):
    try:
        if tournament_id:
            games = get_all_player_games_from_tournament(player_id, tournament_type, tournament_id, start_date, end_date)
        else:
            games = get_all_player_games(player_id, tournament_type, start_date, end_date)
        
        games.sort(key=lambda x: x['game_date'])
        
        trend = []
        for game in games:
            game_stats = {}
            
            if game['kills'] or game['deaths'] or game['assists']:
                if game['deaths'] > 0:
                    game_stats['kda'] = (game['kills'] + game['assists']) / game['deaths']
                elif game['kills'] + game['assists'] > 0:
                    game_stats['kda'] = float('inf')
            
            if game['average_combat_score']:
                game_stats['avg_average_combat_score'] = game['average_combat_score']

            if game_stats:
                game_stats['date'] = game['game_date']
                trend.append(game_stats)
        
        return trend
    
    except Exception as e:
        logger.error(f"Error in get_player_performance_trend: {str(e)}")
        raise

def get_player_role_analysis(player_id, tournament_id=None, tournament_type='vct-international', start_date=None, end_date=None):
    try:
        if tournament_id:
            games = get_all_player_games_from_tournament(player_id, tournament_type, tournament_id, start_date, end_date)
        else:
            games = get_all_player_games(player_id, tournament_type, start_date, end_date)
        
        role_stats = {}
        for game in games:
            role = game['agent_role']
            if not role:
                continue
            
            if role not in role_stats:
                role_stats[role] = {'games': 0, 'kills': 0, 'deaths': 0, 'assists': 0, 'average_combat_score': 0}
            
            role_stats[role]['games'] += 1
            if game['kills']:
                role_stats[role]['kills'] += game['kills']
            if game['deaths']:
                role_stats[role]['deaths'] += game['deaths']
            if game['assists']:
                role_stats[role]['assists'] += game['assists']
            if game['average_combat_score']:
                role_stats[role]['average_combat_score'] += game['average_combat_score']
        
        for role, stats in role_stats.items():
            if stats['games'] > 0:
                stats['avg_kills'] = stats['kills'] / stats['games']
                stats['avg_deaths'] = stats['deaths'] / stats['games']
                stats['avg_assists'] = stats['assists'] / stats['games']
                stats['avg_average_combat_score'] = stats['average_combat_score'] / stats['games']
            if stats['deaths'] > 0:
                stats['kda'] = (stats['kills'] + stats['assists']) / stats['deaths']
            elif stats['kills'] + stats['assists'] > 0:
                stats['kda'] = float('inf')
            else:
                stats['kda'] = 0
        
        return role_stats
    
    except Exception as e:
        logger.error(f"Error in get_player_role_analysis: {str(e)}")
        raise