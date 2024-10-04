import json
import logging
from player_queries import get_player_info_by_handle, get_player_info_by_name
from stat_queries import get_player_stats, get_player_best_agents, get_player_performance_trend, get_player_role_analysis
from position_queries import get_map_visualization

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    
    try:
        function = event['function']
        parameters = {param['name']: param['value'] for param in event.get('parameters', [])}
        
        if function == 'get_player_info_by_handle':
            handle = parameters.get('handle')
            result = get_player_info_by_handle(handle)
        elif function == 'get_player_info_by_name':
            first_name = parameters.get('first_name')
            last_name = parameters.get('last_name')
            result = get_player_info_by_name(first_name, last_name)
        elif function == 'get_player_stats':
            player_id = parameters.get('player_id')
            tournament_id = parameters.get('tournament_id')
            tournament_type = parameters.get('tournament_type', 'vct-international')
            start_date = parameters.get('start_date')
            end_date = parameters.get('end_date')
            result = get_player_stats(player_id, tournament_id, tournament_type, start_date, end_date)
        elif function == 'get_player_best_agents':
            player_id = parameters.get('player_id')
            tournament_id = parameters.get('tournament_id')
            tournament_type = parameters.get('tournament_type', 'vct-international')
            start_date = parameters.get('start_date')
            end_date = parameters.get('end_date')
            result = get_player_best_agents(player_id, tournament_id, tournament_type, start_date, end_date)
        elif function == 'get_player_performance_trend':
            player_id = parameters.get('player_id')
            start_date = parameters.get('start_date')
            end_date = parameters.get('end_date')
            tournament_id = parameters.get('tournament_id')
            tournament_type = parameters.get('tournament_type', 'vct-international')
            result = get_player_performance_trend(player_id, start_date, end_date, tournament_id, tournament_type)
        elif function == 'get_player_role_analysis':
            player_id = parameters.get('player_id')
            tournament_id = parameters.get('tournament_id')
            tournament_type = parameters.get('tournament_type', 'vct-international')
            start_date = parameters.get('start_date')
            end_date = parameters.get('end_date')
            result = get_player_role_analysis(player_id, tournament_id, tournament_type, start_date, end_date)
        elif function == 'get_map_visualization':
            player_id = parameters.get('player_id')
            result = get_map_visualization(player_id)
        else:
            raise ValueError(f"Unknown function: {function}")
        
        return {
            'response': {
                'actionGroup': event['actionGroup'],
                'function': event['function'],
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps(result, default=str)
                        }
                    }
                }
            },
            'messageVersion': event['messageVersion']
        }
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'response': {
                'actionGroup': event.get('actionGroup'),
                'function': event.get('function'),
                'functionResponse': {
                    'responseBody': {
                        'TEXT': {
                            'body': json.dumps({'error': str(e)})
                        }
                    }
                }
            },
            'messageVersion': event.get('messageVersion')
        }