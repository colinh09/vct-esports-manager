import json
import requests
from PIL import Image, ImageDraw, ImageFont
import io
from decimal import Decimal, getcontext
import random

# Set a high precision for decimal calculations
getcontext().prec = 50

DEFAULT_GAME_JSON = "/home/colin/vct-esports-manager/data/test-files/sample/sample.json"
DEFAULT_MAPS_JSON = "/home/colin/vct-esports-manager/src/event_locations/maps.json"

def download_image(url):
    response = requests.get(url)
    return Image.open(io.BytesIO(response.content))

def load_json_file(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

def transform_coordinates(x, y, map_data, image_width, image_height):
    x, y = Decimal(str(x)), Decimal(str(y))
    xMultiplier = Decimal(str(map_data['xMultiplier']))
    yMultiplier = Decimal(str(map_data['yMultiplier']))
    xScalarToAdd = Decimal(str(map_data['xScalarToAdd']))
    yScalarToAdd = Decimal(str(map_data['yScalarToAdd']))
    
    norm_x = (y * xMultiplier) + xScalarToAdd
    norm_y = (x * yMultiplier) + yScalarToAdd
    
    pixel_x = int((norm_x * Decimal(str(image_height))).to_integral_value())
    pixel_y = int((norm_y * Decimal(str(image_width))).to_integral_value())
    
    return pixel_x, pixel_y

def generate_random_color():
    return (random.randint(64, 255), random.randint(64, 255), random.randint(64, 255))

def parse_configuration(config):
    players = config['players']
    player_info = {}
    for player in players:
        player_id = player['playerId']['value']
        display_name = player['displayName']
        agent_name = player['selectedAgent']['fallback']['displayName']
        player_info[player_id] = {
            'displayName': display_name,
            'agentName': agent_name
        }
    return player_info

def plot_events(game_data, map_data, event_type):
    minimap = download_image(map_data['displayIcon'])
    image_width, image_height = minimap.size
    draw = ImageDraw.Draw(minimap)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except IOError:
        font = ImageFont.load_default()

    player_colors = {}
    last_known_positions = {}
    player_info = None

    for event in game_data:
        if 'configuration' in event:
            player_info = parse_configuration(event['configuration'])
            break

    if player_info is None:
        print("Error: Configuration event not found in game data")
        return

    for player_id in player_info:
        player_colors[player_id] = generate_random_color()

    for event in game_data:
        if 'snapshot' in event:
            for player in event['snapshot']['players']:
                player_id = player['playerId']['value']
                if 'aliveState' in player:
                    x = player['aliveState']['position']['x']
                    y = player['aliveState']['position']['y']
                    last_known_positions[player_id] = (x, y)
        
        elif event_type == 'kills' and 'playerDied' in event:
            killer_id = event['playerDied']['killerId']['value']
            if killer_id in last_known_positions:
                x, y = last_known_positions[killer_id]
                pixel_x, pixel_y = transform_coordinates(x, y, map_data, image_width, image_height)
                
                circle_radius = 3
                draw.ellipse([pixel_x - circle_radius, pixel_y - circle_radius,
                              pixel_x + circle_radius, pixel_y + circle_radius],
                             fill=player_colors[killer_id], outline='white')

        elif event_type == 'deaths' and 'playerDied' in event:
            deceased_id = event['playerDied']['deceasedId']['value']
            if deceased_id in last_known_positions:
                x, y = last_known_positions[deceased_id]
                pixel_x, pixel_y = transform_coordinates(x, y, map_data, image_width, image_height)
                
                draw.line((pixel_x - 5, pixel_y - 5, pixel_x + 5, pixel_y + 5), fill=player_colors[deceased_id], width=2)
                draw.line((pixel_x - 5, pixel_y + 5, pixel_x + 5, pixel_y - 5), fill=player_colors[deceased_id], width=2)

        elif event_type == 'spike_plants' and 'spikePlantCompleted' in event:
            planter_id = event['spikePlantCompleted']['playerId']['value']
            x = event['spikePlantCompleted']['plantLocation']['x']
            y = event['spikePlantCompleted']['plantLocation']['y']
            pixel_x, pixel_y = transform_coordinates(x, y, map_data, image_width, image_height)
            
            draw.rectangle([pixel_x - 5, pixel_y - 5, pixel_x + 5, pixel_y + 5],
                           fill=player_colors[planter_id], outline='white')

    # Create color legend
    legend_width = 200
    legend_height = len(player_colors) * 20 + 10
    legend = Image.new('RGBA', (legend_width, legend_height), (0, 0, 0, 180))
    legend_draw = ImageDraw.Draw(legend)

    for i, (player_id, color) in enumerate(player_colors.items()):
        y = i * 20 + 5
        legend_draw.rectangle([5, y, 25, y + 15], fill=color, outline='white')
        player_name = player_info[player_id]['displayName']
        agent_name = player_info[player_id]['agentName']
        legend_draw.text((30, y), f"{player_name} ({agent_name})", fill='white', font=font)

    minimap.paste(legend, (image_width - legend_width - 10, 10), legend)

    minimap.save(f'player_{event_type}.png')
    print(f"Player {event_type} plotted and saved as 'player_{event_type}.png'")

if __name__ == "__main__":
    game_json_file = input(f"Enter the path to the game JSON file (default: {DEFAULT_GAME_JSON}): ") or DEFAULT_GAME_JSON
    maps_json_file = input(f"Enter the path to the maps JSON file (default: {DEFAULT_MAPS_JSON}): ") or DEFAULT_MAPS_JSON

    try:
        game_data = load_json_file(game_json_file)
        maps_data = load_json_file(maps_json_file)

        # Find the correct map data
        map_name = 'Lotus'
        if map_name is None:
            print("Error: Map name not found in game data")
            exit(1)

        map_data = next((map_data for map_data in maps_data if map_data['displayName'] == map_name), None)
        if map_data is None:
            print(f"Error: Map data not found for {map_name}")
            exit(1)

        event_types = ['kills', 'deaths', 'spike_plants']
        for event_type in event_types:
            plot_events(game_data, map_data, event_type)

    except FileNotFoundError as e:
        print(f"Error: File not found - {e}")
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in input file - {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")