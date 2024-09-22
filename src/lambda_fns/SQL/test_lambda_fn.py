import json
from main import lambda_handler

def test_get_player_by_handle():
    event = {
        "actionGroup": "PlayerInfoGroup",
        "function": "get_player_info_by_handle",
        "parameters": [
            {
                "name": "handle",
                "type": "string",
                "value": "TenZ"
            }
        ],
        "messageVersion": "1.0"
    }
    run_test("Get player by handle", event)

def run_test(test_name, event):
    print(f"\nRunning test: {test_name}")
    print(f"Input event: {json.dumps(event, indent=2)}")
    
    result = lambda_handler(event, None)
    
    print(f"Lambda function response: {json.dumps(result, indent=2)}")
    
    if 'response' in result and 'functionResponse' in result['response']:
        response_body = json.loads(result['response']['functionResponse']['responseBody']['TEXT']['body'])
        print(f"Parsed player info: {json.dumps(response_body, indent=2)}")
    else:
        print("Error: Unexpected response format")

if __name__ == "__main__":
    test_get_player_by_handle()