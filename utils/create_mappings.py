import json
import os

def load_json(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_agent_mappings(agents_data):
    agent_mappings = {}
    ability_mappings = {}
    for agent in agents_data:
        agent_mappings[agent['uuid']] = agent['displayName']
        for ability in agent['abilities']:
            ability_key = f"{agent['uuid']}_{ability['slot']}"
            ability_mappings[ability_key] = ability['displayName']
    return agent_mappings, ability_mappings

def generate_weapon_mappings(weapons_data):
    weapon_mappings = {}
    for weapon in weapons_data:
        weapon_mappings[weapon['uuid']] = f"{weapon['displayName']} ({weapon['uuid']})"
    return weapon_mappings

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_file = os.path.join(script_dir, '..', 'data', 'api-data', 'agents.json')
    weapons_file = os.path.join(script_dir, '..', 'data', 'api-data', 'weapons.json')
    
    agents_data = load_json(agents_file)
    weapons_data = load_json(weapons_file)
    
    agent_mappings, ability_mappings = generate_agent_mappings(agents_data)
    weapon_mappings = generate_weapon_mappings(weapons_data)
    
    mappings = {
        'agents': agent_mappings,
        'abilities': ability_mappings,
        'weapons': weapon_mappings
    }
    
    output_file = os.path.join(script_dir, 'valorant_mappings.json')
    with open(output_file, 'w') as f:
        json.dump(mappings, f, indent=2)
    
    print(f"Mappings have been generated and saved to {output_file}")

if __name__ == "__main__":
    main()