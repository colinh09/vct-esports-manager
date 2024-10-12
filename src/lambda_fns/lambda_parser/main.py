import json
import re

def lambda_handler(event, context):
    # Extract the raw response from the event
    raw_response = event['invokeModelRawResponse']
    
    # Parse the raw response
    parsed_data = parse_response(raw_response)
    
    # Structure the response for the agent
    response = {
        "messageVersion": "1.0",
        "promptType": "ORCHESTRATION",
        "orchestrationParsedResponse": {
            "responseDetails": {
                "invocationType": "FINISH",
                "agentFinalResponse": {
                    "responseText": json.dumps(parsed_data),
                    "citations": {"generatedResponseParts": []}
                }
            }
        }
    }
    
    return response

def parse_response(raw_response):
    # Initialize the result dictionary
    result = {
        "entities": {},
        "tasks": [],
        "constraints": []
    }
    
    # Try to parse the response as JSON
    try:
        json_data = json.loads(raw_response)
        if isinstance(json_data, dict):
            # Check if the model has already structured the output
            if all(key in json_data for key in ["entities", "tasks", "constraints"]):
                return json_data
            else:
                result["entities"] = json_data
    except json.JSONDecodeError:
        # If it's not JSON, we'll parse it as text
        pass

    # If entities weren't extracted as JSON, try to extract them from text
    if not result["entities"]:
        result["entities"] = extract_entities(raw_response)
    
    # Extract tasks and constraints if they weren't in the JSON
    if not result["tasks"] or not result["constraints"]:
        tasks_constraints = extract_tasks_and_constraints(raw_response)
        result["tasks"] = tasks_constraints["tasks"]
        result["constraints"] = tasks_constraints["constraints"]
    
    return result
def extract_entities(text):
    entities = {}
    entity_patterns = {
        "player_handle": r"player_handle\"?\s*:?\s*\"?([^\"]+)\"?",
        "player_name": r"player_name\"?\s*:?\s*\"?([^\"]+)\"?",
        "team": r"team\"?\s*:?\s*\"?([^\"]+)\"?",
        "league": r"league\"?\s*:?\s*\"?([^\"]+)\"?",
        "region": r"region\"?\s*:?\s*\"?([^\"]+)\"?",
        "tournament_type": r"tournament_type\"?\s*:?\s*\"?(vct-challengers|vct-international|game-changers)\"?"
    }
    
    for entity, pattern in entity_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            entities[entity] = match.group(1)
    
    return entities

def extract_tasks_and_constraints(text):
    tasks = []
    constraints = []
    
    # Common tasks in the context of Valorant
    task_patterns = [
        r"build\s+(?:a)?\s*team",
        r"find\s+(?:a)?\s*player",
        r"get\s+information",
        r"compare\s+players",
        r"analyze\s+team\s+composition"
    ]
    
    for pattern in task_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            tasks.append(re.search(pattern, text, re.IGNORECASE).group())
    
    # Extract constraints
    constraint_patterns = [
        r"using\s+(?:the\s+)?player\s+(\w+)",
        r"players\s+from\s+([\w\s]+)",
        r"from\s+(?:the\s+)?([\w\s]+)\s+region",
        r"in\s+(?:the\s+)?([\w\s]+)\s+league",
        r"for\s+(?:the\s+)?([\w\s]+)\s+tournament"
    ]
    
    for pattern in constraint_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        constraints.extend(matches)
    
    return {"tasks": tasks, "constraints": constraints}