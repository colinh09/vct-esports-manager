import logging
import json
from PIL import Image, ImageDraw
import io
import base64
from db_connection import get_db_connection
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_game_positions(platform_game_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get player mappings for the game
        query = """
            SELECT DISTINCT internal_player_id
            FROM player_mapping
            WHERE platform_game_id = %s
        """
        cursor.execute(query, (platform_game_id,))
        
        all_results = cursor.fetchall()
        logger.info(f"Player mapping query results: {all_results}")
        
        players = [row['internal_player_id'] for row in all_results if 'internal_player_id' in row]
        logger.info(f"Processed players: {players}")

        # Get player death events
        cursor.execute("""
            SELECT deceased_id, killer_id, deceased_x, deceased_y, killer_x, killer_y
            FROM player_died
            WHERE platform_game_id = %s
        """, (platform_game_id,))
        death_events = cursor.fetchall()
        
        if not death_events:
            logger.warning(f"No death events found for game {platform_game_id}")
        else:
            logger.info(f"First death event: {death_events[0]}")

        cursor.close()
        conn.close()

        return players, death_events

    except Exception as e:
        logger.error(f"Error in get_game_positions: {str(e)}", exc_info=True)
        raise

def transform_coordinates(x, y, map_data, image_width, image_height):
    try:
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
    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Error in transform_coordinates: {str(e)}")
        return None, None

def create_map_visualization(platform_game_id):
    try:
        players, death_events = get_game_positions(platform_game_id)

        # Load map data
        map_data = get_map_data(platform_game_id)

        with Image.open("Lotus.png") as img:
            draw = ImageDraw.Draw(img)
            image_width, image_height = img.size
            
            for event in death_events:
                logger.info(f"Processing event: {event}")

                deceased_id = event['deceased_id']
                killer_id = event['killer_id']
                deceased_x = event['deceased_x']
                deceased_y = event['deceased_y']
                killer_x = event['killer_x']
                killer_y = event['killer_y']
                
                logger.info(f"Raw coordinates - deceased: ({deceased_x}, {deceased_y}), killer: ({killer_x}, {killer_y})")
                
                deceased_pixel_x, deceased_pixel_y = transform_coordinates(deceased_x, deceased_y, map_data, image_width, image_height)
                killer_pixel_x, killer_pixel_y = transform_coordinates(killer_x, killer_y, map_data, image_width, image_height)
                
                logger.info(f"Transformed coordinates - deceased: ({deceased_pixel_x}, {deceased_pixel_y}), killer: ({killer_pixel_x}, {killer_pixel_y})")

                # Draw the line and points only if coordinates are valid
                if all(coord is not None for coord in [killer_pixel_x, killer_pixel_y, deceased_pixel_x, deceased_pixel_y]):
                    draw.line((killer_pixel_x, killer_pixel_y, deceased_pixel_x, deceased_pixel_y), 
                              fill="red", width=2)

                    draw.ellipse((deceased_pixel_x - 5, deceased_pixel_y - 5, 
                                  deceased_pixel_x + 5, deceased_pixel_y + 5), 
                                 fill="black")

                    draw.text((deceased_pixel_x, deceased_pixel_y), 
                              str(deceased_id), fill="white")
                    draw.text((killer_pixel_x, killer_pixel_y), 
                              str(killer_id), fill="white")
                else:
                    logger.warning(f"Skipping event due to invalid coordinates: {event}")

            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            return img_str
    except FileNotFoundError:
        logger.error("Lotus.png not found in the current directory", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error in create_map_visualization: {str(e)}", exc_info=True)
        raise

def get_map_visualization(platform_game_id):
    try:
        img_str = create_map_visualization(platform_game_id)
        return {
            "map_image": img_str,
            "platform_game_id": platform_game_id
        }
    except Exception as e:
        logger.error(f"Error in get_map_visualization: {str(e)}", exc_info=True)
        return {
            "error": str(e),
            "platform_game_id": platform_game_id
        }

def get_map_data(platform_game_id):
    # This function should return a dictionary with keys:
    # 'xMultiplier', 'yMultiplier', 'xScalarToAdd', 'yScalarToAdd'
    # The values should be strings that can be converted to Decimal
    # For now, we'll return placeholder values. You should replace this
    # with actual logic to fetch the correct map data for each game.
    return {
        'xMultiplier': '7.2e-05',
        'yMultiplier': '-7.2e-05',
        'xScalarToAdd': '0.454789',
        'yScalarToAdd': '0.917752'
    }