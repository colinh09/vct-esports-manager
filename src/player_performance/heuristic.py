import json
import os
from typing import Dict, List, Any

def load_mappings(file_path, agents_file_path, weapons_file_path):
    with open(file_path, 'r') as f:
        mappings = json.load(f)
    
    with open(agents_file_path, 'r') as f:
        agents_data = json.load(f)
    
    with open(weapons_file_path, 'r') as f:
        weapons_data = json.load(f)
    
    mappings['weapons'] = {k.lower(): v for k, v in mappings['weapons'].items()}
    mappings['agents'] = {k.lower(): v for k, v in mappings['agents'].items()}
    mappings['abilities'] = {k.lower(): v for k, v in mappings['abilities'].items()}
    
    mappings['agents_info'] = {}
    for agent in agents_data['agents']:
        uuid = agent['uuid'].lower()
        mappings['agents_info'][uuid] = {
            'name': agent['name'],
            'role': agent['role'],
            'abilities': {ability['slot'].lower(): ability for ability in agent['abilities']}
        }
    
    mappings['weapons_cost'] = {}
    mappings['weapons_name'] = {}
    for weapon in weapons_data:
        uuid = weapon['uuid'].lower()
        mappings['weapons_name'][uuid] = weapon['displayName']
        if 'shopData' in weapon and weapon['shopData'] is not None and 'cost' in weapon['shopData']:
            mappings['weapons_cost'][uuid] = weapon['shopData']['cost']
        else:
            mappings['weapons_cost'][uuid] = 0  # Default cost if not available
    
    return mappings

class Player:
    def __init__(self, id):
        self.kills = {'attacking': 0, 'defending': 0}
        self.deaths = {'attacking': 0, 'defending': 0}
        self.assists = {'attacking': 0, 'defending': 0}
        self.id = id
        self.display_name = ''
        self.agent_guid = ''
        self.agent_name = ''
        self.agent_role = ''
        self.team_id = None
        self.ability_used_this_round = False
        self.is_alive = True
        self.current_weapon = None
        self.current_weapon_cost = 0
        self.rounds_won = 0
        self.rounds_survived = 0
        self.clutch_wins = 0
        self.in_clutch_scenario = False
        self.enemies_alive_at_clutch_start = 0
        self.ability_usage = {'damaging': 0, 'non_damaging': 0}
        self.ability_effectiveness = {'damaging': 0, 'non_damaging': 0}
        self.last_ability_used = None
        self.last_ability_time = None
        self.active_abilities = {}
        self.first_bloods = 0
        self.multi_kills = 0
        self.kills_this_round = 0
        self.econ_kills = 0
        self.initiator_ability_deaths = 0
        self.rounds_played = 0
        self.score = 0
        self.normalized_score = 0

    def __str__(self):
        return (f"Player: {self.display_name} (ID: {self.id})\n"
                f"Agent: {self.agent_name} (Role: {self.agent_role}) (GUID: {self.agent_guid})\n"
                f"Team ID: {self.team_id}\n"
                f"Kills: Attacking: {self.kills['attacking']}, Defending: {self.kills['defending']}\n"
                f"Deaths: Attacking: {self.deaths['attacking']}, Defending: {self.deaths['defending']}\n"
                f"Assists: Attacking: {self.assists['attacking']}, Defending: {self.assists['defending']}\n"
                f"Total KDA: {sum(self.kills.values())}/{sum(self.deaths.values())}/{sum(self.assists.values())}\n"
                f"Rounds Won: {self.rounds_won}, Rounds Survived: {self.rounds_survived}\n"
                f"Clutch Wins: {self.clutch_wins}\n"
                f"Ability Usage: Damaging: {self.ability_usage['damaging']}, Non-damaging: {self.ability_usage['non_damaging']}\n"
                f"Ability Effectiveness: Damaging: {self.ability_effectiveness['damaging']}, Non-damaging: {self.ability_effectiveness['non_damaging']}\n"
                f"First Bloods: {self.first_bloods}\n"
                f"Multi-kills: {self.multi_kills}\n"
                f"Econ Kills: {self.econ_kills}\n"
                f"Initiator Ability Deaths: {self.initiator_ability_deaths}\n"
                f"Rounds Played: {self.rounds_played}\n"
                f"Final Score: {self.score:.2f}\n"
                f"Normalized Score: {self.normalized_score:.2f}")
    
    def reset_round_stats(self):
        self.ability_used_this_round = False
        self.is_alive = True
        self.current_weapon = None
        self.current_weapon_cost = 0
        self.in_clutch_scenario = False
        self.enemies_alive_at_clutch_start = 0
        self.last_ability_used = None
        self.last_ability_time = None
        self.active_abilities = {}
        self.kills_this_round = 0
        self.rounds_played += 1

    def use_ability(self, ability_slot, current_time, ability_info):
        self.ability_used_this_round = True
        ability_type = 'damaging' if ability_info['dealsDamage'] else 'non_damaging'
        self.ability_usage[ability_type] += 1
        self.last_ability_used = ability_slot
        self.last_ability_time = current_time

        if not ability_info['dealsDamage'] and ability_info['duration'] > 0:
            end_time = current_time + ability_info['duration']
            self.active_abilities[ability_slot] = end_time

    def update_active_abilities(self, current_time):
        self.active_abilities = {slot: end_time for slot, end_time in self.active_abilities.items() if end_time > current_time}

    def has_active_non_damaging_ability(self):
        return bool(self.active_abilities)

    def add_kill(self, is_attacking):
        side = 'attacking' if is_attacking else 'defending'
        self.kills[side] += 1
        self.kills_this_round += 1
        
        if self.kills_this_round >= 2:
            self.multi_kills += 1

heuristic = {
    "attacking_kill": {
        "Duelist": 2,
        "Initiator": 1,
        "Sentinel": 1,
        "Controller": 1
    },
    "defending_kill": {
        "Duelist": 2,
        "Initiator": 1,
        "Sentinel": 1,
        "Controller": 1
    },
    "attacking_death": {
        "Duelist": -1,
        "Initiator": -1,
        "Sentinel": -0.5,
        "Controller": -2
    },
    "defending_death": {
        "Duelist": -0.5,
        "Initiator": -1,
        "Sentinel": -2,
        "Controller": -2
    },
    "assist": {
        "Duelist": 0.5,
        "Initiator": 1,
        "Sentinel": 0.5,
        "Controller": 0.5
    },
    "econ_kill": 0.5,
    "round_win": 1,
    "round_survive": 0.5,
    "ability_usage": {
        "damaging": 0.05,
        "non_damaging": 1
    },
    "first_blood": 1.5,
    "multi_kill": 1,
    "clutch_win": 2,
    "initiator_ability_death": 0.5
}

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
    player_map = {}  # Mapping player ID to Player instance
    team_players = {}  # Mapping team ID to list of player IDs

    for player in players:
        player_id = safe_get(player, 'playerId', 'value')
        display_name = safe_get(player, 'displayName')
        agent_guid = safe_get(player, 'selectedAgent', 'fallback', 'guid').lower()
        
        player_instance = Player(player_id)
        player_instance.display_name = display_name
        player_instance.agent_guid = agent_guid
        
        agent_info = mappings['agents_info'].get(agent_guid, {})
        player_instance.agent_name = agent_info.get('name', 'Unknown')
        player_instance.agent_role = agent_info.get('role', 'Unknown')
        
        player_map[player_id] = player_instance
        
        result += f"ID: {player_id}, Name: {display_name}, Agent: {player_instance.agent_name}, Role: {player_instance.agent_role}\n"
    
    for team in config.get('teams', []):
        team_id = team['teamId']['value']
        team_players[team_id] = [player['value'] for player in team.get('playersInTeam', [])]
        for player_id in team_players[team_id]:
            if player_id in player_map:
                player_map[player_id].team_id = team_id

    return result, player_map, team_players

def parse_event(event_type: str, event_data: Dict[str, Any], player_map: Dict[str, Player], include_snapshots: bool, mappings: Dict[str, Dict[str, str]], attacking_team: int, current_time: float, is_first_kill: bool) -> str:
    if event_type == 'playerDied':
        killer_id = safe_get(event_data, 'killerId', 'value')
        victim_id = safe_get(event_data, 'deceasedId', 'value')
        
        killer_player = player_map.get(killer_id)
        victim_player = player_map.get(victim_id)
        
        killer_name = killer_player.display_name if killer_player else '[unknown]'
        victim_name = victim_player.display_name if victim_player else '[unknown]'
        
        if killer_player and victim_player:
            killer_side = 'attacking' if killer_player.team_id == attacking_team else 'defending'
            victim_side = 'defending' if killer_player.team_id == attacking_team else 'attacking'
            killer_player.add_kill(killer_side == 'attacking')
            victim_player.deaths[victim_side] += 1
            
            if killer_player.current_weapon_cost < victim_player.current_weapon_cost:
                killer_player.econ_kills += 1
                econ_kill_str = f" (Econ kill: {killer_player.current_weapon} (${killer_player.current_weapon_cost}) vs {victim_player.current_weapon} (${victim_player.current_weapon_cost}))"
            else:
                econ_kill_str = f" ({killer_player.current_weapon} (${killer_player.current_weapon_cost}) vs {victim_player.current_weapon} (${victim_player.current_weapon_cost}))"
            
            if victim_player.agent_role == "Initiator" and victim_player.ability_used_this_round:
                victim_player.initiator_ability_deaths += 1
            
            ability_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot').lower()
            if ability_slot:
                ability_info = mappings['agents_info'][killer_player.agent_guid]['abilities'].get(ability_slot)
                if ability_info and ability_info['dealsDamage']:
                    killer_player.ability_effectiveness['damaging'] += 1
            
            victim_player.is_alive = False
            
            if is_first_kill:
                killer_player.first_bloods += 1
                first_blood_str = " (First Blood!)"
            else:
                first_blood_str = ""
            
            if killer_player.kills_this_round == 2:
                multi_kill_str = " (Multi-kill!)"
            else:
                multi_kill_str = ""
        
        assists = []
        for assist in event_data.get('assistants', []):
            assistant_id = safe_get(assist, 'assistantId', 'value')
            assistant_player = player_map.get(assistant_id)
            assistant_name = assistant_player.display_name if assistant_player else '[unknown]'
            assists.append(assistant_name)
            if assistant_player:
                assistant_side = 'attacking' if assistant_player.team_id == attacking_team else 'defending'
                assistant_player.assists[assistant_side] += 1
                
                if assistant_player.has_active_non_damaging_ability():
                    assistant_player.ability_effectiveness['non_damaging'] += 1
        
        assist_str = f" assisted by {', '.join(assists)}" if assists else ""
        
        team_players = {}
        for player in player_map.values():
            if player.is_alive:
                if player.team_id not in team_players:
                    team_players[player.team_id] = []
                team_players[player.team_id].append(player)

        for team_id, alive_players in team_players.items():
            if len(alive_players) == 1 and not alive_players[0].in_clutch_scenario:
                clutch_player = alive_players[0]
                clutch_player.in_clutch_scenario = True
                enemy_team_id = next(tid for tid in team_players.keys() if tid != team_id)
                clutch_player.enemies_alive_at_clutch_start = len(team_players[enemy_team_id])
        
        return f"{killer_name} killed {victim_name}{assist_str}.{econ_kill_str}{first_blood_str}{multi_kill_str}"

    elif event_type == 'abilityUsed':
        player_id = safe_get(event_data, 'playerId', 'value')
        player = player_map.get(player_id)
        if player:
            ability_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot').lower()
            if ability_slot:
                ability_info = mappings['agents_info'][player.agent_guid]['abilities'].get(ability_slot)
                if ability_info:
                    player.use_ability(ability_slot, current_time, ability_info)
        return None 

    elif event_type == 'damageEvent':
        causer_id = safe_get(event_data, 'causerId', 'value')
        causer_player = player_map.get(causer_id)
        if causer_player:
            ability_slot = safe_get(event_data, 'ability', 'fallback', 'inventorySlot', 'slot').lower()
            if ability_slot:
                ability_info = mappings['agents_info'][causer_player.agent_guid]['abilities'].get(ability_slot)
                if ability_info and ability_info['dealsDamage']:
                    causer_player.ability_effectiveness['damaging'] += 1
        return None

    elif event_type == 'snapshot':
        for player_data in event_data.get('players', []):
            player_id = safe_get(player_data, 'playerId', 'value')
            player = player_map.get(player_id)
            if player:
                alive_state = player_data.get('aliveState', {})
                if alive_state:
                    player.is_alive = True
                    equipped_item = alive_state.get('equippedItem', {})
                    weapon_guid = safe_get(equipped_item, 'guid').lower()
                    player.current_weapon = mappings['weapons_name'].get(weapon_guid, weapon_guid)
                    player.current_weapon_cost = mappings['weapons_cost'].get(weapon_guid, 0)
                else:
                    player.is_alive = False
                player.update_active_abilities(current_time)
        return None

    elif event_type == 'roundDecided':
        winning_team = safe_get(event_data, 'result', 'winningTeam', 'value')
        for player in player_map.values():
            if player.team_id == winning_team:
                player.rounds_won += 1
                if player.is_alive:
                    player.rounds_survived += 1
                
                if player.in_clutch_scenario:
                    player.clutch_wins += 1
        
        return f"Round ended. Winning team: {winning_team}"

    else:
        return None

def process_game_file(input_file: str, output_dir: str, include_snapshots: bool, mappings: Dict[str, Dict[str, str]]):
    with open(input_file, 'r') as f:
        game_data = json.load(f)
    
    os.makedirs(output_dir, exist_ok=True)
    
    config_event = next((event for event in game_data if 'configuration' in event), None)
    if config_event:
        config_info, player_map, team_players = parse_configuration(config_event['configuration'], mappings)
        with open(os.path.join(output_dir, 'configuration.txt'), 'w') as f:
            f.write(config_info)
    else:
        print("Warning: No configuration event found.")
        player_map = {}
        team_players = {}
    
    current_round = 0
    round_events = []
    attacking_team = None
    current_time = 0
    is_first_kill = True
    
    for event in game_data:
        if 'roundStarted' in event:
            current_round = safe_get(event['roundStarted'], 'roundNumber')
            attacking_team = event['roundStarted']['spikeMode']['attackingTeam']['value']
            round_events = []
            round_events.append(f"Round {current_round} started. Attacking team: {attacking_team}")
            
            for player in player_map.values():
                player.reset_round_stats()
            
            is_first_kill = True
        
        wall_time = safe_get(event, 'metadata', 'wallTime')
        
        if 'snapshot' in event:
            current_time += 1
        
        for event_type, event_data in event.items():
            if event_type not in ['metadata', 'configuration', 'roundStarted', 'roundEnded', 'platformGameId', 'observerTarget']:
                parsed_event = parse_event(event_type, event_data, player_map, include_snapshots, mappings, attacking_team, current_time, is_first_kill)
                if parsed_event:
                    round_events.append(f"[{wall_time}] {parsed_event}")
                    if event_type == 'playerDied':
                        is_first_kill = False
        
        if 'roundEnded' in event:
            round_end_event = parse_event('roundEnded', event['roundEnded'], player_map, include_snapshots, mappings, attacking_team, current_time, False)
            round_events.append(f"[{wall_time}] {round_end_event}")
            with open(os.path.join(output_dir, f'round_{current_round}.txt'), 'w') as f:
                f.write('\n'.join(round_events))
    
    # Calculate final scores
    for player in player_map.values():
        player.score = calculate_player_score(player, heuristic)
        player.normalized_score = player.score / player.rounds_played if player.rounds_played > 0 else 0

    with open(os.path.join(output_dir, 'player_stats.txt'), 'w') as f:
        for player_id, player in player_map.items():
            player_info = str(player)
            f.write(player_info + "\n\n")
            print(player_info + "\n")

    print("Processing complete. Check the output directory for results.")

def calculate_player_score(player: Player, heuristic: Dict[str, Any]) -> float:
    score = 0
    
    # Kills and deaths
    for side in ['attacking', 'defending']:
        score += player.kills[side] * heuristic[f"{side}_kill"][player.agent_role]
        score += player.deaths[side] * heuristic[f"{side}_death"][player.agent_role]
    
    # Assists
    score += sum(player.assists.values()) * heuristic["assist"][player.agent_role]
    
    # Econ kills
    score += player.econ_kills * heuristic["econ_kill"]
    
    # Round wins and survivals
    score += player.rounds_won * heuristic["round_win"]
    score += player.rounds_survived * heuristic["round_survive"]
    
    # Ability usage
    score += player.ability_effectiveness['damaging'] * heuristic["ability_usage"]["damaging"]
    score += player.ability_effectiveness['non_damaging'] * heuristic["ability_usage"]["non_damaging"]
    
    # First bloods
    score += player.first_bloods * heuristic["first_blood"]
    
    # Multi-kills
    score += player.multi_kills * heuristic["multi_kill"]
    
    # Clutch wins
    score += player.clutch_wins * heuristic["clutch_win"]
    
    # Initiator ability deaths
    if player.agent_role == "Initiator":
        score += player.initiator_ability_deaths * heuristic["initiator_ability_death"]
    
    return score

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mappings_file = os.path.join(script_dir, 'valorant_mappings.json')
    agents_file = os.path.join(script_dir, 'agent.json')
    weapons_file = os.path.join(script_dir, 'weapons.json')
    mappings = load_mappings(mappings_file, agents_file, weapons_file)
    
    default_input_file = "/home/colin/vct-esports-manager/data/test-files/sample/sample.json"
    default_output_dir = "/home/colin/vct-esports-manager/data/test-files/sample"
    
    input_file = input(f"Enter the path to the input JSON file (default: {default_input_file}): ").strip() or default_input_file
    output_dir = input(f"Enter the directory to store the output files (default: {default_output_dir}): ").strip() or default_output_dir
    include_snapshots = input("Include snapshot events? (y/n): ").lower() == 'y'
    
    process_game_file(input_file, output_dir, include_snapshots, mappings)
    print("Processing complete. Check the output directory for results.")