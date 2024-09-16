import requests
import json
import os

BASE_URL = "https://valorant-api.com/v1"
DATA_DIR = "../data/api-data"

def ensure_data_directory():
    """
    Ensure that the data directory exists.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

def fetch_data(endpoint, params=None):
    """
    Fetch data from the specified API endpoint.
    """
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()['data']

def save_to_json(data, filename):
    """
    Save the data to a JSON file in the data directory.
    """
    file_path = os.path.join(DATA_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_and_save_agents():
    """
    Fetch agent data and save it to a JSON file.
    """
    agents = fetch_data("agents", params={"isPlayableCharacter": "true"})
    save_to_json(agents, "agents.json")

def fetch_and_save_weapons():
    """
    Fetch weapon data and save it to a JSON file.
    """
    weapons = fetch_data("weapons")
    save_to_json(weapons, "weapons.json")

def main():
    ensure_data_directory()
    fetch_and_save_agents()
    fetch_and_save_weapons()
    print("Data fetched and saved successfully.")

if __name__ == "__main__":
    main()