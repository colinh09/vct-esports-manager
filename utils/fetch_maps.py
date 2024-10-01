import requests
import json

# Full URL including API key
FULL_URL = "https://na.api.riotgames.com/val/content/v1/contents?api_key=RGAPI-fb77c0c1-adc5-4399-9937-63baf1abc8ab"

def get_valorant_data():
    try:
        response = requests.get(FULL_URL)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"An error occurred while fetching data: {e}")
        if hasattr(e, 'response'):
            print(f"Response status code: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        return None

def extract_map_data(data):
    return data.get('maps', [])

def save_map_data(map_data, filename='all_map_data.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(map_data, f, indent=2, ensure_ascii=False)
    print(f"All map data has been saved to {filename}")

def print_map_summary(map_data):
    print(f"\nFound {len(map_data)} maps. Here's a summary:")
    for map_info in map_data:
        print(f"- {map_info.get('name', 'Unnamed map')} (ID: {map_info.get('id', 'No ID')})")
    print("\nCheck all_map_data.json for complete details on each map.")

def main():
    data = get_valorant_data()
    
    if data:
        map_data = extract_map_data(data)
        save_map_data(map_data)
        print_map_summary(map_data)
    else:
        print("Failed to retrieve data.")

if __name__ == "__main__":
    main()