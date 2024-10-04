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
    if 'map_image' in response_body:
        image_data = base64.b64decode(response_body['map_image'])
        file_name = f"test_map_{response_body['platform_game_id']}.png"
        with open(file_name, "wb") as f:
            f.write(image_data)
        print(f"Test image saved as {file_name}")
    else:
        print("Error: No map image in response")

def test_all_functions():
    # Test get_player_info_by_handle
    # run_test("Get player by handle", {
    #     "actionGroup": "PlayerInfoGroup",
    #     "function": "get_player_info_by_handle",
    #     "parameters": [
    #         {
    #             "name": "handle",
    #             "type": "string",
    #             "value": "TenZ"
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_player_info_by_name
    # run_test("Get player by name", {
    #     "actionGroup": "PlayerInfoGroup",
    #     "function": "get_player_info_by_name",
    #     "parameters": [
    #         {
    #             "name": "first_name",
    #             "type": "string",
    #             "value": "Tyson"
    #         },
    #         {
    #             "name": "last_name",
    #             "type": "string",
    #             "value": "Ngo"
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_player_stats
    # run_test("Get player stats", {
    #     "actionGroup": "PlayerStatsGroup",
    #     "function": "get_player_stats",
    #     "parameters": [
    #         {
    #             "name": "player_id",
    #             "type": "string",
    #             "value": "106229920360816436"  # Replace with actual ID if known
    #         },
    #         {
    #             "name": "tournament_id",
    #             "type": "string",
    #             "value": "111811151250338218"  # Replace with actual tournament ID if known
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_player_best_agents
    # run_test("Get player best agents", {
    #     "actionGroup": "PlayerStatsGroup",
    #     "function": "get_player_best_agents",
    #     "parameters": [
    #         {
    #             "name": "player_id",
    #             "type": "string",
    #             "value": "106229920360816436"  # Replace with actual ID if known
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_player_performance_trend
    # run_test("Get player performance trend", {
    #     "actionGroup": "PlayerStatsGroup",
    #     "function": "get_player_performance_trend",
    #     "parameters": [
    #         {
    #             "name": "player_id",
    #             "type": "string",
    #             "value": "106229920360816436"  # Replace with actual ID if known
    #         },
    #         {
    #             "name": "start_date",
    #             "type": "string",
    #             "value": "2023-01-01"
    #         },
    #         {
    #             "name": "end_date",
    #             "type": "string",
    #             "value": "2023-12-31"
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # # Test get_player_role_analysis
    # run_test("Get player role analysis", {
    #     "actionGroup": "PlayerStatsGroup",
    #     "function": "get_player_role_analysis",
    #     "parameters": [
    #         {
    #             "name": "player_id",
    #             "type": "string",
    #             "value": "106229920360816436"  # Replace with actual ID if known
    #         }
    #     ],
    #     "messageVersion": "1.0"
    # })

    # Test get_map_visualization
    run_test("Get map visualization", {
        "actionGroup": "MapVisualizationGroup",
        "function": "get_map_visualization",
        "parameters": [
            {
                "name": "player_id",
                "type": "string",
                "value": "106229920360816436"
            }
        ],
        "messageVersion": "1.0"
    })

if __name__ == "__main__":
    test_all_functions()