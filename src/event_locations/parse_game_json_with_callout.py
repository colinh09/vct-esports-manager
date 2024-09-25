import json
import os
import math
import logging
from typing import Dict, List, Any

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_mappings(file_path):
    with open(file_path, 'r') as f:
        mappings = json.load(f)
    
    mappings['weapons'] = {k.lower(): v for k, v in mappings['weapons'].items()}
    mappings['agents'] = {k.lower(): v for k, v in mappings['agents'].items()}
    mappings['abilities'] = {k.lower(): v for k, v in mappings['abilities'].items()}
    
    return mappings

def load_map_callouts(file_path):
    with open(file_path, 'r') as f:
        maps_data = json.load(f)
    
    for map_data in maps_data:
        if map_data['displayName'] == 'Sunset':  # Assuming the map is always Sunset (Jam)
            return map_data['callouts']
    
    raise ValueError("Map 'Sunset' not found in the JSON file.")

def safe_get(data: Dict[str, Any], *keys, default="[unknown]"):
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, {})
        else:
            return default
    return data if data != {} else default

def parse_configuration(config: Dict[str, Any], mappings: Dict[str, Dict[str, str]]) -> tuple:
    players = config['players']
    map_info = safe_get(config, 'selectedMap', 'fallback', 'guid')
    
    result = f"Map: {map_info}\n\nPlayers:\n"
    player_map = {}
    for player in players:
        player_id = safe_get(player, 'playerId', 'value')
        display_name = safe_get(player, 'displayName')
        agent_guid = safe_get(player, 'selectedAgent', 'fallback', 'guid').lower()
        agent_name = mappings['agents'].get(agent_guid, agent_guid)
        result += f"ID: {player_id}, Name: {display_name}, Agent: {agent_name}\n"
        player_map[player_id] = {
            'displayName': display_name,
            'agentGuid': agent_guid
        }
    
    return result, player_map

def get_ability_name(agent_guid: str, ability_slot: str, mappings: Dict[str, Dict[str, str]]) -> str:
    slot_to_ability = {
        "ability_1": "ability1",
        "ability_2": "ability2",
        "grenade_ability": "grenade",
        "ultimate": "ultimate"
    }
    ability_type = slot_to_ability.get(ability_slot.lower(), ability_slot.lower())
    ability_key = f"{agent_guid}_{ability_type}".lower()
    return mappings['abilities'].get(ability_key, ability_slot)

def find_nearest_callout(x: float, y: float, callouts: List[Dict[str, Any]]) -> str:
    min_distance = float('inf')
    nearest_callout = None
    
    logger.debug(f"Finding nearest callout for position: ({x}, {y})")
    
    for callout in callouts:
        callout_x = callout['location']['x']
        callout_y = callout['location']['y']
        
        distance = math.sqrt((x - callout_x)**2 + (y - callout_y)**2)
        
        logger.debug(f"Callout: {callout['superRegionName']} {callout['regionName']}, "
                     f"Coords: ({callout_x}, {callout_y}), "
                     f"Distance: {distance}")
        
        if distance < min_distance:
            min_distance = distance
            nearest_callout = callout
    
    result = f"{nearest_callout['superRegionName']} {nearest_callout['regionName']}"
    logger.debug(f"Nearest callout: {result}, Distance: {min_distance}")
    return result

def parse_event(event_type: str, event_data: Dict[str, Any], player_map: Dict[str, Dict[str, str]], include_snapshots: bool, mappings: Dict[str, Dict[str, str]], callouts: List[Dict[str, Any]], last_snapshot: Dict[str, Dict[str, Any]]) -> str:
    if event_type == 'playerDied':
        killer_id = safe_get(event_data, 'killerId', 'value')
        victim_id = safe_get(event_data, 'deceasedId', 'value')
        killer = player_map.get(killer_id, {}).get('displayName', '[unknown]')
        victim = player_map.get(victim_id, {}).get('displayName', '[unknown]')
        
        weapon_guid = safe_get(event_data, 'weapon', 'fallback', 'guid').lower()
        weapon_name = mappings['weapons'].get(weapon_guid, weapon_guid)
        
        ability_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot')
        ability_name = '[unknown ability]'
        if ability_slot != '[unknown]':
            killer_agent_guid = player_map.get(killer_id, {}).get('agentGuid', '')
            ability_name = get_ability_name(killer_agent_guid, ability_slot, mappings)
        
        hazard_guid = safe_get(event_data, 'hazard', 'fallback', 'guid')
        
        cause_of_death = []
        if weapon_name != '[unknown]':
            cause_of_death.append(f"weapon {weapon_name}")
        if ability_name != '[unknown ability]':
            cause_of_death.append(f"ability {ability_name}")
        if hazard_guid != '[unknown]':
            cause_of_death.append(f"hazard {hazard_guid}")
        
        if not cause_of_death:
            cause_of_death = ["unknown cause"]
        
        assists = [player_map.get(safe_get(assist, 'assistantId', 'value'), {}).get('displayName', '[unknown]') for assist in event_data.get('assistants', [])]
        assist_str = f" assisted by {', '.join(assists)}" if assists else ""
        
        victim_pos = last_snapshot.get(victim_id, {}).get('position', {})
        if victim_pos:
            callout = find_nearest_callout(victim_pos['x'], victim_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{killer} killed {victim} using {' and '.join(cause_of_death)}{assist_str}{location_str}."
    
    elif event_type == 'damageEvent':
        causer_id = safe_get(event_data, 'causerId', 'value')
        victim_id = safe_get(event_data, 'victimId', 'value')
        causer = player_map.get(causer_id, {}).get('displayName', '[unknown]')
        victim = player_map.get(victim_id, {}).get('displayName', '[unknown]')
        damage = safe_get(event_data, 'damageAmount')
        weapon_guid = safe_get(event_data, 'weapon', 'fallback', 'guid').lower()
        weapon_name = mappings['weapons'].get(weapon_guid, weapon_guid)
        
        victim_pos = last_snapshot.get(victim_id, {}).get('position', {})
        if victim_pos:
            callout = find_nearest_callout(victim_pos['x'], victim_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{causer} dealt {damage} damage to {victim} using {weapon_name}{location_str}."
    
    elif event_type == 'abilityUsed':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        inventory_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot')
        charges_consumed = safe_get(event_data, 'chargesConsumed')
        
        player_agent_guid = player_map.get(player_id, {}).get('agentGuid', '')
        ability_name = get_ability_name(player_agent_guid, inventory_slot, mappings)
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} used ability {ability_name} from {inventory_slot} slot, consuming {charges_consumed} charges{location_str}."
    
    elif event_type == 'spikePlantCompleted':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        location = safe_get(event_data, 'plantLocation', default={'x': '[unknown]', 'y': '[unknown]', 'z': '[unknown]'})
        
        if location['x'] != '[unknown]' and location['y'] != '[unknown]':
            callout = find_nearest_callout(location['x'], location['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} planted the spike at location (x: {location['x']}, y: {location['y']}, z: {location['z']}){location_str}."
    
    elif event_type == 'spikeDefuseCheckpointReached':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        progress = safe_get(event_data, 'progress')
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} reached defuse checkpoint: {progress}{location_str}."
    
    elif event_type == 'inventoryTransaction':
        player_id = safe_get(event_data, 'player', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        transaction_type = safe_get(event_data, 'transactionType')
        
        if 'weapon' in event_data:
            item_type = "weapon"
            item_guid = safe_get(event_data, 'weapon', 'fallback', 'guid').lower()
            item_name = mappings['weapons'].get(item_guid, item_guid)
        elif 'armor' in event_data:
            item_type = "armor"
            item_guid = safe_get(event_data, 'armor', 'fallback', 'guid')
            item_name = item_guid
        elif 'ability' in event_data:
            item_type = "ability"
            inventory_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot')
            player_agent_guid = player_map.get(player_id, {}).get('agentGuid', '')
            item_name = get_ability_name(player_agent_guid, inventory_slot, mappings)
        else:
            item_type = "unknown"
            item_name = "[unknown]"
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} {transaction_type} {item_type}: {item_name}{location_str}."
    
    elif event_type == 'snapshot' and include_snapshots:
        result = "SNAPSHOT:\n"
        for player_data in event_data.get('players', []):
            player_id = safe_get(player_data, 'playerId', 'value')
            player_name = player_map.get(player_id, {}).get('displayName', '[unknown]')
            health = safe_get(player_data, 'aliveState', 'health')
            armor = safe_get(player_data, 'aliveState', 'armor')
            money = safe_get(player_data, 'money')
            kills = safe_get(player_data, 'kills')
            deaths = safe_get(player_data, 'deaths')
            assists = safe_get(player_data, 'assists')
            position = safe_get(player_data, 'aliveState', 'position', default={'x': '[unknown]', 'y': '[unknown]', 'z': '[unknown]'})
            
            if health == '[unknown]':
                status = "Dead"
            else:
                status = f"Health: {health}, Armor: {armor}"
            
            if position['x'] != '[unknown]' and position['y'] != '[unknown]':
                callout = find_nearest_callout(position['x'], position['y'], callouts)
                location_str = f", Location: {callout}"
            else:
                location_str = ""
            
            result += f"{player_name}: Status: {status}, Money: {money}, K/D/A: {kills}/{deaths}/{assists}, "
            result += f"Position: (x: {position['x']}, y: {position['y']}, z: {position['z']}){location_str}\n"
        return result
    
    elif event_type == 'gamePhase':
        phase = safe_get(event_data, 'phase')
        round_number = safe_get(event_data, 'roundNumber')
        return f"Game phase changed to {phase} in round {round_number}."
    
    elif event_type == 'spikeStatus':
        status = safe_get(event_data, 'status')
        carrier_id = safe_get(event_data, 'carrier', 'value')
        carrier = player_map.get(carrier_id, {}).get('displayName', '[unknown]')
        
        carrier_pos = last_snapshot.get(carrier_id, {}).get('position', {})
        if carrier_pos:
            callout = find_nearest_callout(carrier_pos['x'], carrier_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            return f"Spike status: {status}."
    
    elif event_type == 'roundDecided':
        round_number = safe_get(event_data, 'result', 'roundNumber')
        winning_team_id = safe_get(event_data, 'result', 'winningTeam', 'value')
        cause = safe_get(event_data, 'result', 'spikeModeResult', 'cause')
        result = f"Round {round_number} decided. Winning team: {winning_team_id}, Cause: {cause}"
        return result
    
    elif event_type == 'spikePlantStarted':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} started planting the spike{location_str}."
    
    elif event_type == 'spikePlantStopped':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} stopped planting the spike{location_str}."
    
    elif event_type == 'spikeDefuseStarted':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} started defusing the spike{location_str}."
    
    elif event_type == 'spikeDefuseStopped':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        
        player_pos = last_snapshot.get(player_id, {}).get('position', {})
        if player_pos:
            callout = find_nearest_callout(player_pos['x'], player_pos['y'], callouts)
            location_str = f" near {callout}"
        else:
            location_str = ""
        
        return f"{player} stopped defusing the spike{location_str}."
    
    elif event_type == 'gameDecided':
        winning_team_id = safe_get(event_data, 'winningTeam', 'value')
        state = safe_get(event_data, 'state')
        result = f"Game decided. Winning team: {winning_team_id}, State: {state}"
        return result
    
    else:
        return None  # Return None for events we want to skip

def process_game_file(input_file: str, output_dir: str, include_snapshots: bool, mappings: Dict[str, Dict[str, str]], callouts: List[Dict[str, Any]]):
    with open(input_file, 'r') as f:
        game_data = json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Process configuration
    config_event = next((event for event in game_data if 'configuration' in event), None)
    if config_event:
        config_info, player_map = parse_configuration(config_event['configuration'], mappings)
        with open(os.path.join(output_dir, 'configuration.txt'), 'w') as f:
            f.write(config_info)
    else:
        print("Warning: No configuration event found.")
        player_map = {}
    
    # Process rounds
    current_round = 0
    round_events = []
    last_snapshot = {}
    
    for event in game_data:
        if 'roundStarted' in event:
            current_round = safe_get(event['roundStarted'], 'roundNumber')
            round_events = []
            last_snapshot = {}
        
        wall_time = safe_get(event, 'metadata', 'wallTime')
        
        for event_type, event_data in event.items():
            if event_type == 'snapshot':
                for player_data in event_data.get('players', []):
                    player_id = safe_get(player_data, 'playerId', 'value')
                    last_snapshot[player_id] = player_data
            
            if event_type not in ['metadata', 'configuration', 'roundStarted', 'roundEnded', 'platformGameId', 'observerTarget']:
                parsed_event = parse_event(event_type, event_data, player_map, include_snapshots, mappings, callouts, last_snapshot)
                if parsed_event:
                    round_events.append(f"[{wall_time}] {parsed_event}")
        
        if 'roundEnded' in event:
            with open(os.path.join(output_dir, f'round_{current_round}.txt'), 'w') as f:
                f.write('\n'.join(round_events))

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mappings_file = os.path.join(script_dir, 'valorant_mappings.json')
    mappings = load_mappings(mappings_file)
    
    maps_file = os.path.join(script_dir, 'maps.json')
    callouts = load_map_callouts(maps_file)
    
    input_file = '/home/colin/vct-esports-manager/data/test-files/sample/sample.json'
    output_dir = input("Enter the directory to store the output files: ")
    include_snapshots = input("Include snapshot events? (y/n): ").lower() == 'y'
    
    process_game_file(input_file, output_dir, include_snapshots, mappings, callouts)
    print("Processing complete. Check the output directory for results.")
        
