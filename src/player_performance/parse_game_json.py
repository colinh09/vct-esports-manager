import json
import os
from typing import Dict, List, Any

def load_mappings(file_path):
    with open(file_path, 'r') as f:
        mappings = json.load(f)
    
    mappings['weapons'] = {k.lower(): v for k, v in mappings['weapons'].items()}
    mappings['agents'] = {k.lower(): v for k, v in mappings['agents'].items()}
    mappings['abilities'] = {k.lower(): v for k, v in mappings['abilities'].items()}
    
    return mappings

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
    
    team_info = {}
    for team in config.get('teams', []):
        team_id = safe_get(team, 'teamId', 'value')
        team_name = safe_get(team, 'name')
        players_in_team = [safe_get(p, 'value') for p in team.get('playersInTeam', [])]
        team_info[team_id] = {
            'name': team_name,
            'players': players_in_team
        }
    
    result += "\nTeams:\n"
    for team_id, team_data in team_info.items():
        result += f"Team ID: {team_id}, Name: {team_data['name']}, Players: {', '.join(map(str, team_data['players']))}\n"
    
    return result, player_map, team_info

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

def parse_event(event_type: str, event_data: Dict[str, Any], player_map: Dict[str, Dict[str, str]], include_snapshots: bool, mappings: Dict[str, Dict[str, str]], team_info: Dict[int, Dict[str, Any]]) -> str:
    if event_type == 'roundStarted':
        round_number = safe_get(event_data, 'roundNumber')
        attacking_team_id = safe_get(event_data, 'spikeMode', 'attackingTeam', 'value')
        defending_team_id = safe_get(event_data, 'spikeMode', 'defendingTeam', 'value')
        attacking_team_name = team_info.get(attacking_team_id, {}).get('name', 'Unknown Team')
        defending_team_name = team_info.get(defending_team_id, {}).get('name', 'Unknown Team')
        return f"Round {round_number} started. Attacking Team: ID {attacking_team_id} ({attacking_team_name}), Defending Team: ID {defending_team_id} ({defending_team_name})"
    
    elif event_type == 'playerDied':
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
        
        return f"{killer} killed {victim} using {' and '.join(cause_of_death)}{assist_str}."
    
    elif event_type == 'damageEvent':
        causer_id = safe_get(event_data, 'causerId', 'value')
        victim_id = safe_get(event_data, 'victimId', 'value')
        causer = player_map.get(causer_id, {}).get('displayName', '[unknown]')
        victim = player_map.get(victim_id, {}).get('displayName', '[unknown]')
        damage = safe_get(event_data, 'damageAmount')
        weapon_guid = safe_get(event_data, 'weapon', 'fallback', 'guid').lower()
        weapon_name = mappings['weapons'].get(weapon_guid, weapon_guid)
        return f"{causer} dealt {damage} damage to {victim} using {weapon_name}."
    
    elif event_type == 'abilityUsed':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        inventory_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot')
        charges_consumed = safe_get(event_data, 'chargesConsumed')
        
        player_agent_guid = player_map.get(player_id, {}).get('agentGuid', '')
        ability_name = get_ability_name(player_agent_guid, inventory_slot, mappings)
        
        return f"{player} used ability {ability_name} from {inventory_slot} slot, consuming {charges_consumed} charges."
    
    elif event_type == 'spikePlantCompleted':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        location = safe_get(event_data, 'plantLocation', default={'x': '[unknown]', 'y': '[unknown]', 'z': '[unknown]'})
        return f"{player} planted the spike at location (x: {location['x']}, y: {location['y']}, z: {location['z']})."
    
    elif event_type == 'spikeDefuseCheckpointReached':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        progress = safe_get(event_data, 'progress')
        return f"{player} reached defuse checkpoint: {progress}."
    
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
        
        return f"{player} {transaction_type} {item_type}: {item_name}."
    
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
            
            result += f"{player_name}: Status: {status}, Money: {money}, K/D/A: {kills}/{deaths}/{assists}, "
            result += f"Position: (x: {position['x']}, y: {position['y']}, z: {position['z']})\n"
        return result
    
    elif event_type == 'gamePhase':
        phase = safe_get(event_data, 'phase')
        round_number = safe_get(event_data, 'roundNumber')
        return f"Game phase changed to {phase} in round {round_number}."
    
    elif event_type == 'spikeStatus':
        status = safe_get(event_data, 'status')
        carrier_id = safe_get(event_data, 'carrier', 'value')
        carrier = player_map.get(carrier_id, {}).get('displayName', '[unknown]')
        return f"Spike status: {status}, Carrier: {carrier}."
    
    elif event_type == 'roundDecided':
        round_number = safe_get(event_data, 'result', 'roundNumber')
        winning_team_id = safe_get(event_data, 'result', 'winningTeam', 'value')
        winning_team = team_info.get(winning_team_id, {}).get('name', f'Team ID {winning_team_id}')
        cause = safe_get(event_data, 'result', 'spikeModeResult', 'cause')
        result = f"Round {round_number} decided. Winning team: {winning_team}, Cause: {cause}"
        return result
    
    elif event_type == 'spikePlantStarted':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        result = f"{player} started planting the spike."
        return result
    
    elif event_type == 'spikePlantStopped':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        result = f"{player} stopped planting the spike."
        return result
    
    elif event_type == 'spikeDefuseStarted':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        result = f"{player} started defusing the spike."
        return result
    
    elif event_type == 'spikeDefuseStopped':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id, {}).get('displayName', '[unknown]')
        result = f"{player} stopped defusing the spike."
        return result
    
    elif event_type == 'gameDecided':
        winning_team_id = safe_get(event_data, 'winningTeam', 'value')
        winning_team = team_info.get(winning_team_id, {}).get('name', f'Team ID {winning_team_id}')
        state = safe_get(event_data, 'state')
        result = f"Game decided. Winning team: {winning_team}, State: {state}"
        return result
    
    else:
        return None

def process_game_file(input_file: str, output_dir: str, include_snapshots: bool, mappings: Dict[str, Dict[str, str]]):
    with open(input_file, 'r') as f:
        game_data = json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Process configuration
    config_event = next((event for event in game_data if 'configuration' in event), None)
    if config_event:
        config_info, player_map, team_info = parse_configuration(config_event['configuration'], mappings)
        with open(os.path.join(output_dir, 'configuration.txt'), 'w') as f:
            f.write(config_info)
    else:
        print("Warning: No configuration event found.")
        player_map = {}
        team_info = {}
    
    # Process rounds
    current_round = 0
    round_events = []
    
    for event in game_data:
        if 'roundStarted' in event:
            if round_events:
                with open(os.path.join(output_dir, f'round_{current_round}.txt'), 'w') as f:
                    f.write('\n'.join(round_events))
            current_round = safe_get(event['roundStarted'], 'roundNumber')
            round_events = []
        
        wall_time = safe_get(event, 'metadata', 'wallTime')
        
        for event_type, event_data in event.items():
            if event_type not in ['metadata', 'configuration', 'roundEnded', 'platformGameId', 'observerTarget']:
                parsed_event = parse_event(event_type, event_data, player_map, include_snapshots, mappings, team_info)
                if parsed_event:
                    round_events.append(f"[{wall_time}] {parsed_event}")
    
    # Write the last round events
    if round_events:
        with open(os.path.join(output_dir, f'round_{current_round}.txt'), 'w') as f:
            f.write('\n'.join(round_events))

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mappings_file = os.path.join(script_dir, 'valorant_mappings.json')
    mappings = load_mappings(mappings_file)
    
    input_file = input("Enter the path to the input JSON file: ")
    output_dir = input("Enter the directory to store the output files: ")
    include_snapshots = input("Include snapshot events? (y/n): ").lower() == 'y'
    
    process_game_file(input_file, output_dir, include_snapshots, mappings)
    print("Processing complete. Check the output directory for results.")