import json
import logging
from get_last_game_map import get_map_visualization
from get_last_tour_map import get_tournament_map_visualizations
from get_player_info import get_player_info_wrapper
from get_top_agents_for_player import get_top_agents_for_player
from get_top_players_by_role import get_top_players_by_role

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info(f"Received event: {json.dumps(event)}")
    try:
        function = event['function']
        parameters = {param['name']: param['value'] for param in event.get('parameters', [])}
        
        if function == 'get_map_visualization':
            player_id = parameters.get('player_id')
            result = get_map_visualization(player_id)
        elif function == 'get_last_tournament_map':
            player_id = parameters.get('player_id')
            event_type = parameters.get('event_type', 'both')
            result = get_tournament_map_visualizations(player_id, event_type)
        elif function == 'get_player_info':
            handle = parameters.get('handle')
            first_name = parameters.get('first_name')
            last_name = parameters.get('last_name')
            logger.info(f"Calling get_player_info_wrapper with handle={handle}, first_name={first_name}, last_name={last_name}")
            result = get_player_info_wrapper(handle=handle, first_name=first_name, last_name=last_name)
        elif function == 'get_top_agents_for_player':
            player_id = parameters.get('player_id')
            limit = parameters.get('limit', 5)
            result = get_top_agents_for_player(player_id, limit)
        elif function == 'get_top_players_by_role':
            role = parameters.get('role')
            vct_international = int(parameters.get('vct_international', 0))
            vct_challenger = int(parameters.get('vct_challenger', 0))
            game_changers = int(parameters.get('game_changers', 0))
            result = get_top_players_by_role(role, vct_international, vct_challenger, game_changers)
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