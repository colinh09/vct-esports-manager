import logging
import json
from PIL import Image, ImageDraw
import io
import base64
from db_connection import get_db_connection
from decimal import Decimal
import requests
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_latest_game(player_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT gm.platform_game_id, gm.map, gm.game_date
            FROM game_mapping gm
            JOIN player_mapping pm ON gm.platform_game_id = pm.platform_game_id
            WHERE pm.player_id = %s
            ORDER BY gm.game_date DESC
            LIMIT 1
        """
        cursor.execute(query, (player_id,))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if result:
            return result['platform_game_id'], result['map'], result['game_date']
        else:
            logger.warning(f"No games found for player {player_id}")
            return None, None, None

    except Exception as e:
        logger.error(f"Error in get_latest_game: {str(e)}", exc_info=True)
        raise

def get_map_data(map_url):
    try:
        with open('maps.json', 'r') as f:
            maps_data = json.load(f)

        for map_data in maps_data:
            if map_data['mapUrl'] == map_url:
                return {
                    'displayIcon': map_data['displayIcon'],
                    'xMultiplier': str(map_data['xMultiplier']),
                    'yMultiplier': str(map_data['yMultiplier']),
                    'xScalarToAdd': str(map_data['xScalarToAdd']),
                    'yScalarToAdd': str(map_data['yScalarToAdd'])
                }

        logger.warning(f"Map data not found for {map_url}")
        return None

    except Exception as e:
        logger.error(f"Error in get_map_data: {str(e)}", exc_info=True)
        raise

def get_game_events(platform_game_id, player_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT 
                deceased_x, deceased_y, killer_x, killer_y,
                true_deceased_id, true_killer_id
            FROM player_died
            WHERE platform_game_id = %s 
            AND (true_deceased_id = %s OR true_killer_id = %s)
        """
        cursor.execute(query, (platform_game_id, player_id, player_id))
        events = cursor.fetchall()

        cursor.close()
        conn.close()

        return events

    except Exception as e:
        logger.error(f"Error in get_game_events: {str(e)}", exc_info=True)
        raise

def transform_coordinates(x, y, map_data, image_width, image_height):
    try:
        x, y = Decimal(str(x)), Decimal(str(y))
        xMultiplier = Decimal(map_data['xMultiplier'])
        yMultiplier = Decimal(map_data['yMultiplier'])
        xScalarToAdd = Decimal(map_data['xScalarToAdd'])
        yScalarToAdd = Decimal(map_data['yScalarToAdd'])
        
        norm_x = (y * xMultiplier) + xScalarToAdd
        norm_y = (x * yMultiplier) + yScalarToAdd
        
        pixel_x = int((norm_x * Decimal(str(image_width))).to_integral_value())
        pixel_y = int((norm_y * Decimal(str(image_height))).to_integral_value())
        
        return pixel_x, pixel_y
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Error in transform_coordinates: {str(e)}")
        return None, None

def create_map_visualization(player_id, platform_game_id, map_url, map_data):
    try:
        events = get_game_events(platform_game_id, player_id)

        response = requests.get(map_data['displayIcon'])
        img = Image.open(io.BytesIO(response.content))
        draw = ImageDraw.Draw(img)
        image_width, image_height = img.size
        
        for event in events:
            deceased_x, deceased_y = transform_coordinates(event['deceased_x'], event['deceased_y'], map_data, image_width, image_height)
            killer_x, killer_y = transform_coordinates(event['killer_x'], event['killer_y'], map_data, image_width, image_height)
            
            if all(coord is not None for coord in [killer_x, killer_y, deceased_x, deceased_y]):
                if event['true_killer_id'] == player_id:
                    # Player's kill
                    draw.line((killer_x, killer_y, deceased_x, deceased_y), fill="green", width=2)
                    draw.ellipse((deceased_x - 5, deceased_y - 5, deceased_x + 5, deceased_y + 5), fill="green")
                elif event['true_deceased_id'] == player_id:
                    # Player's death
                    draw.line((killer_x, killer_y, deceased_x, deceased_y), fill="red", width=2)
                    draw.ellipse((deceased_x - 5, deceased_y - 5, deceased_x + 5, deceased_y + 5), fill="red")

        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return img_str
    except Exception as e:
        logger.error(f"Error in create_map_visualization: {str(e)}", exc_info=True)
        raise

def get_map_visualization(player_id):
    try:
        platform_game_id, map_url, game_date = get_latest_game(player_id)
        if not platform_game_id:
            return {
                "error": "No games found for the player",
                "player_id": player_id
            }

        map_data = get_map_data(map_url)
        if not map_data:
            return {
                "error": f"Map data not found for {map_url}",
                "player_id": player_id,
                "platform_game_id": platform_game_id
            }

        img_str = create_map_visualization(player_id, platform_game_id, map_url, map_data)
        return {
            "map_image": img_str,
            "player_id": player_id,
            "platform_game_id": platform_game_id,
            "map_url": map_url,
            "game_date": game_date.strftime("%Y-%m-%d") if game_date else None
        }
    except Exception as e:
        logger.error(f"Error in get_map_visualization: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "player_id": player_id
        }