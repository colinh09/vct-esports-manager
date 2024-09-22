import json
import logging
from player_queries import get_player_info_by_handle, get_player_info_by_name
from calculations import get_player_game_stats, get_player_tournament_stats

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
        elif function == 'get_player_game_stats':
            player_id = parameters.get('player_id')
            result = get_player_game_stats(player_id)
        elif function == 'get_player_tournament_stats':
            player_id = parameters.get('player_id')
            tournament_id = parameters.get('tournament_id')
            result = get_player_tournament_stats(player_id, tournament_id)
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