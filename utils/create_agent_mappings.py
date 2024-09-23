import json
import os

def load_json(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def generate_agent_mappings(agents_data):
    agent_mappings = {}
    for agent in agents_data:
        agent_mappings[agent['uuid']] = {
            'name': agent['displayName'],
            'role': agent['role']['displayName'] if agent['role'] else 'Unknown'
        }
    return agent_mappings

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    agents_file = os.path.join(script_dir, '..', 'data', 'api-data', 'agents.json')

    agents_data = load_json(agents_file)
    agent_mappings = generate_agent_mappings(agents_data)

    output_file = os.path.join(script_dir, 'agents.mapping')
    with open(output_file, 'w') as f:
        json.dump(agent_mappings, f, indent=2)

    print(f"Agent mappings have been generated and saved to {output_file}")

if __name__ == "__main__":
    main()