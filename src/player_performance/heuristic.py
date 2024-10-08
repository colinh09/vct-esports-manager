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

class Player:
    def __init__(self, id):
        self.kills = 0
        self.assists = 0
        self.deaths = 0
        self.id = id
        self.value = 0  # For heuristic calculations
        self.display_name = ''
        self.agent_guid = ''
        self.damage_done = {}      # key: victim_id, value: total damage done to that victim
        self.damage_received = {}  # key: attacker_id, value: total damage received from that attacker
    
    def __str__(self):
        return (f"Player ID: {self.id}, Name: {self.display_name}, "
                f"Kills: {self.kills}, Deaths: {self.deaths}, Assists: {self.assists}, Value: {self.value}")

kda_values = {
    "attack_kill_no_trade": 5,
    "attack_kill_with_trade": 2,
    "defender_kill_no_trade": 4,
    "defender_kill_with_trade": 1,
    "damage_dealt_to_death": 0.5,
    "no_damage_death": -1,
    "assist": 1,
}

def parse_configuration(config: Dict[str, Any], mappings: Dict[str, Dict[str, str]]) -> tuple:
    players = config['players']
    map_info = safe_get(config, 'selectedMap', 'fallback', 'guid')
    
    result = f"Map: {map_info}\n\nPlayers:\n"
    player_map = {}  # Mapping player ID to Player instance

    for player in players:
        player_id = safe_get(player, 'playerId', 'value')
        display_name = safe_get(player, 'displayName')
        agent_guid = safe_get(player, 'selectedAgent', 'fallback', 'guid').lower()
        agent_name = mappings['agents'].get(agent_guid, agent_guid)
        
        # Create a new Player instance and store it in the player_map
        player_instance = Player(player_id)
        player_instance.display_name = display_name
        player_instance.agent_guid = agent_guid
        player_map[player_id] = player_instance
        
        result += f"ID: {player_id}, Name: {display_name}, Agent: {agent_name}\n"
    
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

def parse_event(event_type: str, event_data: Dict[str, Any], player_map: Dict[str, Player], include_snapshots: bool, mappings: Dict[str, Dict[str, str]]) -> str:
    if event_type == 'damageEvent':
        causer_id = safe_get(event_data, 'causerId', 'value')
        victim_id = safe_get(event_data, 'victimId', 'value')
        damage = safe_get(event_data, 'damageAmount')

        causer_player = player_map.get(causer_id)
        victim_player = player_map.get(victim_id)
        
        # Update damage dictionaries
        if causer_player and victim_player:
            # Update causer's damage_done
            causer_player.damage_done[victim_id] = causer_player.damage_done.get(victim_id, 0) + damage
            # Update victim's damage_received
            victim_player.damage_received[causer_id] = victim_player.damage_received.get(causer_id, 0) + damage

        # Existing code to generate event description
        causer_name = causer_player.display_name if causer_player else '[unknown]'
        victim_name = victim_player.display_name if victim_player else '[unknown]'
        weapon_guid = safe_get(event_data, 'weapon', 'fallback', 'guid').lower()
        weapon_name = mappings['weapons'].get(weapon_guid, weapon_guid)
        return f"{causer_name} dealt {damage} damage to {victim_name} using {weapon_name}."

    elif event_type == 'playerDied':
        killer_id = safe_get(event_data, 'killerId', 'value')
        victim_id = safe_get(event_data, 'deceasedId', 'value')
        
        killer_player = player_map.get(killer_id)
        victim_player = player_map.get(victim_id)
        
        killer_name = killer_player.display_name if killer_player else '[unknown]'
        victim_name = victim_player.display_name if victim_player else '[unknown]'
        
        # Update player stats
        if killer_player:
            killer_player.kills += 1
        if victim_player:
            victim_player.deaths += 1
        
        # Process damage received by the victim to apply heuristic
        if victim_player:
            total_damage_received = sum(victim_player.damage_received.values())
            if total_damage_received > 0:
                # The victim dealt damage before dying
                victim_player.value += kda_values['damage_dealt_to_death']
            else:
                # The victim did not deal damage before dying
                victim_player.value += kda_values['no_damage_death']
            
            # Reset damage_received for the victim
            victim_player.damage_received = {}
        
        # Update killer's heuristic value
        if killer_player:
            # Determine if the kill was with or without trade
            # For simplicity, we'll assume no trade
            killer_player.value += kda_values['attack_kill_no_trade']  # or defender_kill_no_trade based on role

        weapon_guid = safe_get(event_data, 'weapon', 'fallback', 'guid').lower()
        weapon_name = mappings['weapons'].get(weapon_guid, weapon_guid)
        
        ability_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot')
        ability_name = '[unknown ability]'
        if ability_slot != '[unknown]' and killer_player:
            killer_agent_guid = killer_player.agent_guid
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
        
        assists = []
        for assist in event_data.get('assistants', []):
            assistant_id = safe_get(assist, 'assistantId', 'value')
            assistant_player = player_map.get(assistant_id)
            assistant_name = assistant_player.display_name if assistant_player else '[unknown]'
            assists.append(assistant_name)
            # Update assistant stats
            if assistant_player:
                assistant_player.assists += 1
                # Update assistant's heuristic value
                assistant_player.value += kda_values['assist']
        
        assist_str = f" assisted by {', '.join(assists)}" if assists else ""
        
        return f"{killer_name} killed {victim_name} using {' and '.join(cause_of_death)}{assist_str}."

    # ... [rest of the existing event handlers] ...

    else:
        return None  # Return None for events we want to skip

def process_game_file(input_file: str, output_dir: str, include_snapshots: bool, mappings: Dict[str, Dict[str, str]]):
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
    
    for event in game_data:
        if 'roundStarted' in event:
            current_round = safe_get(event['roundStarted'], 'roundNumber')
            round_events = []
        
        wall_time = safe_get(event, 'metadata', 'wallTime')
        
        for event_type, event_data in event.items():
            if event_type not in ['metadata', 'configuration', 'roundStarted', 'roundEnded', 'platformGameId', 'observerTarget']:
                parsed_event = parse_event(event_type, event_data, player_map, include_snapshots, mappings)
                if parsed_event:
                    round_events.append(f"[{wall_time}] {parsed_event}")
        
        if 'roundEnded' in event:
            with open(os.path.join(output_dir, f'round_{current_round}.txt'), 'w') as f:
                f.write('\n'.join(round_events))
    
    # After processing, you can output player stats
    with open(os.path.join(output_dir, 'player_stats.txt'), 'w') as f:
        for player_id, player in player_map.items():
            f.write(str(player) + '\n')
            print(player)

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mappings_file = os.path.join(script_dir, 'valorant_mappings.json')
    mappings = load_mappings(mappings_file)
    
    input_file = input("Enter the path to the input JSON file: ")
    output_dir = input("Enter the directory to store the output files: ")
    include_snapshots = input("Include snapshot events? (y/n): ").lower() == 'y'
    
    process_game_file(input_file, output_dir, include_snapshots, mappings)
    print("Processing complete. Check the output directory for results.")

