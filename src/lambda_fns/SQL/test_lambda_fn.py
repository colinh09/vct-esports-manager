import json
from main import lambda_handler
import base64
import os

def run_test(test_name, event):
    print(f"\n=== Running test: {test_name} ===")
    print(f"Input event: {json.dumps(event, indent=2)}")
    
    result = lambda_handler(event, None)
    
    print(f"Lambda function response: {json.dumps(result, indent=2)}")
    
    if 'response' in result and 'functionResponse' in result['response']:
        response_body = json.loads(result['response']['functionResponse']['responseBody']['TEXT']['body'])
        print(f"Parsed result: {json.dumps(response_body, indent=2)}")
        
        # If this is the map visualization test, save the image
        if test_name == "Get map visualization":
            save_map_image(response_body)
    else:
        print("Error: Unexpected response format")

def save_map_image(response_body):
    if 'maps' in response_body:
        for map_url, map_data in response_body['maps'].items():
            file_name = map_data['file_name']
            if os.path.exists(file_name):
                print(f"Map image saved as {file_name}")
            else:
                print(f"Error: Map image {file_name} was not saved")
    else:
        print("Error: No map data in response")

def test_all_functions():
    # Test get_tournament_map_visualizations
    # run_test("Get tournament map visualizations", {
    #     "actionGroup": "MapVisualizationGroup",
    #     "function": "get_tournament_map_visualizations",
    #     "parameters": [
    #         {
    #             "name": "player_id",
    #             "type": "string",
    #             "value": "106229920360816436"  # Replace with actual player ID if needed
    #         },
    #         {
    #             "name": "event_type",
    #             "type": "string",
    #             "value": "both"  # You can change this to "kills" or "deaths" if desired
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # Test get_player_info with handle
    # run_test("Get player info by handle", {
    #     "actionGroup": "PlayerInfoGroup",
    #     "function": "get_player_info",
    #     "parameters": [
    #         {
    #             "name": "handle",
    #             "type": "string",
    #             "value": "tezn"
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_player_info with first name and last name
    # run_test("Get player info by name", {
    #     "actionGroup": "PlayerInfoGroup",
    #     "function": "get_player_info",
    #     "parameters": [
    #         {
    #             "name": "first_name",
    #             "type": "string",
    #             "value": "tysno"
    #         },
    #         {
    #             "name": "last_name",
    #             "type": "string",
    #             "value": "ngooo"
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_top_agents_for_player
    # run_test("Get top agents for player", {
    #     "actionGroup": "PlayerStatsGroup",
    #     "function": "get_top_agents_for_player",
    #     "parameters": [
    #         {
    #             "name": "player_id",
    #             "type": "string",
    #             "value": "106229920360816436"
    #         },
    #         {
    #             "name": "limit",
    #             "type": "number",
    #             "value": 5
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    run_test("Get top players by role", {
        "actionGroup": "PlayerStatsGroup",
        "function": "get_top_players_by_role",
        "parameters": [
            {
                "name": "role",
                "type": "string",
                "value": "igl"
            },
            {
            "name": "game_changers",
            "type": "number",
            "value": 3
            }
        ],
        "messageVersion": "1.0"
    })

if __name__ == "__main__":
    test_all_functions()