import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw, ImageFont
import io
import json
import requests
import colorsys
from datetime import datetime
from decimal import Decimal
import os
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET_NAME = "map-imgs"
S3_REGION = "us-east-1"
s3_client = boto3.client('s3', region_name=S3_REGION)

def get_db_connection():
    db_url = os.getenv('RDS_DATABASE_URL')
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def transform_coordinates(x, y, map_data, image_width, image_height):
    """Transform game coordinates to image coordinates"""
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

def get_map_data(map_url: str):
    """Get map data from maps.json file"""
    try:
        script_dir = Path(__file__).parent
        json_path = script_dir / 'maps.json'
        
        with open(json_path, 'r') as f:
            maps_data = json.load(f)
        return maps_data
        
        for map_data in maps_data:
            if map_data['mapUrl'] == map_url:
                return {
                    'displayName': map_data['displayName'],
                    'displayIcon': map_data['displayIcon'],
                    'xMultiplier': str(map_data['xMultiplier']),
                    'yMultiplier': str(map_data['yMultiplier']),
                    'xScalarToAdd': str(map_data['xScalarToAdd']),
                    'yScalarToAdd': str(map_data['yScalarToAdd']),
                    'mapUrl': map_data['mapUrl']
                }
        
        logger.warning(f"Map data not found for {map_url}")
        return None
    
    except Exception as e:
        logger.error(f"Error in get_map_data: {str(e)}", exc_info=True)
        raise

async def process_player_map_visualizations(player_id: str, maps_data: List[Dict], conn) -> List[Dict]:
    """Process visualizations for a player's top maps"""
    try:
        updated_maps = []
        for map_info in maps_data:
            viz_data = await generate_map_visualization(player_id, map_info['map'], conn)
            if viz_data:
                map_info.update(viz_data)
            updated_maps.append(map_info)
        return updated_maps
    except Exception as e:
        logger.error(f"Error processing map visualizations for player {player_id}: {str(e)}")
        return maps_data

async def generate_map_visualization(player_id: str, map_name: str, conn) -> Optional[Dict]:
    """Generate visualization for a specific map"""
    try:
        map_data = get_map_data(map_name)
        if not map_data:
            return None

        map_directory = f"{player_id}/maps/{map_data['displayName']}"
        file_name_attacking = f"{map_directory}/attacking.png"
        file_name_defending = f"{map_directory}/defending.png"

        # Check if files already exist in S3
        try:
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=file_name_attacking)
            s3_client.head_object(Bucket=S3_BUCKET_NAME, Key=file_name_defending)
            
            # If we get here, both files exist
            return {
                "visualization": {
                    "attacking_url": f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_name_attacking}",
                    "defending_url": f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_name_defending}"
                }
            }
        except ClientError as e:
            # Files don't exist, continue with generation
            pass

        # Get recent games for this map (limit to last 5 for performance)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        games_query = """
            SELECT 
                pm.platform_game_id, pm.kills, pm.deaths, pm.assists, 
                pm.combat_score, gm.game_date, gm.match_id
            FROM game_mapping gm
            JOIN player_mapping pm ON gm.platform_game_id = pm.platform_game_id
            WHERE pm.player_id = %s AND gm.map = %s
            ORDER BY gm.game_date DESC
            LIMIT 5
        """
        cursor.execute(games_query, (player_id, map_name))
        games = cursor.fetchall()

        if not games:
            return None

        # Create base images
        img_attacking = Image.open(io.BytesIO(requests.get(map_data['displayIcon']).content))
        img_defending = Image.open(io.BytesIO(requests.get(map_data['displayIcon']).content))
        draw_attacking = ImageDraw.Draw(img_attacking)
        draw_defending = ImageDraw.Draw(img_defending)

        # Generate colors and process games
        colors = get_distinct_colors(len(games))
        for i, game in enumerate(games):
            game['color'] = colors[i]
            game['attacker_kills'], game['defender_kills'], game['attacker_deaths'], game['defender_deaths'] = plot_game_events(
                draw_attacking, draw_defending, game, player_id, map_data, 'both', conn
            )

        # Add legends
        img_attacking_with_legend = add_legend(img_attacking, games, 'both', "ATTACKING", map_data['displayName'])
        img_defending_with_legend = add_legend(img_defending, games, 'both', "DEFENDING", map_data['displayName'])

        # Upload to S3
        img_buffer_attacking = io.BytesIO()
        img_attacking_with_legend.save(img_buffer_attacking, format='PNG')
        img_buffer_attacking.seek(0)
        
        img_buffer_defending = io.BytesIO()
        img_defending_with_legend.save(img_buffer_defending, format='PNG')
        img_buffer_defending.seek(0)

        s3_url_attacking = upload_to_s3(file_name_attacking, img_buffer_attacking, 'image/png')
        s3_url_defending = upload_to_s3(file_name_defending, img_buffer_defending, 'image/png')

        if s3_url_attacking and s3_url_defending:
            return {
                "visualization": {
                    "attacking_url": s3_url_attacking,
                    "defending_url": s3_url_defending,
                }
            }
        return None

    except Exception as e:
        logger.error(f"Error generating map visualization: {str(e)}")
        return None

def plot_game_events(draw_attacking, draw_defending, game, player_id, map_data, event_type, conn):
    """Plot game events on the map"""
    events = get_game_events(game['platform_game_id'], player_id, event_type, conn)
    image_width, image_height = draw_attacking.im.size
    color = game['color']
    
    attacker_kills, defender_kills, attacker_deaths, defender_deaths = 0, 0, 0, 0
    
    for event in events:
        deceased_x, deceased_y = transform_coordinates(
            event['deceased_x'], event['deceased_y'], 
            map_data, image_width, image_height
        )
        killer_x, killer_y = transform_coordinates(
            event['killer_x'], event['killer_y'], 
            map_data, image_width, image_height
        )
        
        if all(coord is not None for coord in [killer_x, killer_y, deceased_x, deceased_y]):
            if event['true_killer_id'] == player_id and (event_type in ['kills', 'both']):
                if event['killer_is_attacking']:
                    draw_attacking.ellipse((killer_x - 5, killer_y - 5, killer_x + 5, killer_y + 5), fill=color)
                    draw_attacking.line((killer_x, killer_y, deceased_x, deceased_y), fill=color, width=1)
                    draw_attacking.ellipse((deceased_x - 2, deceased_y - 2, deceased_x + 2, deceased_y + 2), fill=color)
                    attacker_kills += 1
                else:
                    draw_defending.ellipse((killer_x - 5, killer_y - 5, killer_x + 5, killer_y + 5), fill=color)
                    draw_defending.line((killer_x, killer_y, deceased_x, deceased_y), fill=color, width=1)
                    draw_defending.ellipse((deceased_x - 2, deceased_y - 2, deceased_x + 2, deceased_y + 2), fill=color)
                    defender_kills += 1
            elif event['true_deceased_id'] == player_id and (event_type in ['deaths', 'both']):
                if event['deceased_is_attacking']:
                    draw_x(draw_attacking, deceased_x, deceased_y, 5, color)
                    draw_attacking.line((killer_x, killer_y, deceased_x, deceased_y), fill=color, width=1)
                    attacker_deaths += 1
                else:
                    draw_x(draw_defending, deceased_x, deceased_y, 5, color)
                    draw_defending.line((killer_x, killer_y, deceased_x, deceased_y), fill=color, width=1)
                    defender_deaths += 1
    
    return attacker_kills, defender_kills, attacker_deaths, defender_deaths

def draw_x(draw, x, y, size, fill):
    """Draw an X marker on the map"""
    draw.line((x - size, y - size, x + size, y + size), fill=fill, width=2)
    draw.line((x - size, y + size, x + size, y - size), fill=fill, width=2)

def add_legend(img, games, event_type, side, map_display_name):  # Added map_display_name parameter
    """Add legend to the map image"""
    legend_width = 300
    new_img = Image.new('RGB', (img.width + legend_width, img.height), color='white')
    new_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    
    x, y = img.width + 10, 10
    draw.text((x, y), "Legend", fill="black", font=font)  # Changed from f"Legend ({side})"
    y += 20
    draw.text((x, y), f"{map_display_name} {side.upper()}", fill="black", font=font)  # Added map name line
    y += 30

    
    for i, game in enumerate(games):
        team1, team2 = get_team_acronyms(game['platform_game_id'])
        match_text = f"Game {i+1}: {team1} vs {team2}"
        color = game['color']
        draw.rectangle([x, y, x+20, y+20], fill=color, outline="black")
        draw.text((x+30, y+3), match_text, fill="black", font=font)
        y += 25
        draw.text((x+30, y), f"KDA: {game['kills']}/{game['deaths']}/{game['assists']}", fill="black", font=font)
        y += 20
        draw.text((x+30, y), f"Combat Score: {game['combat_score']}", fill="black", font=font)
        y += 30
    
    y += 10
    icon_size = 10
    if event_type in ['kills', 'both']:
        draw.ellipse((x, y-icon_size//2, x+icon_size, y+icon_size//2), fill="black")
        draw.text((x + 30, y - 7), f"Player's kills ({side})", fill="black", font=font)
        y += 30
    if event_type in ['deaths', 'both']:
        draw_x(draw, x + icon_size//2, y, icon_size//2, "black")
        draw.text((x + 30, y - 7), f"Player's deaths ({side})", fill="black", font=font)
        y += 30
    
    draw.line((x, y, x + 20, y), fill="black", width=1)
    draw.ellipse((x + 18, y - 2, x + 22, y + 2), fill="black")
    draw.text((x + 30, y - 7), "Kill direction", fill="black", font=font)
    
    return new_img

def get_team_acronyms(platform_game_id):
    """Get team acronyms for a match"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT MIN(t.acronym) as acronym
    FROM team_mapping tm
    JOIN teams t ON tm.team_id = t.team_id
    WHERE tm.platform_game_id = %s
    GROUP BY tm.team_id
    """
    
    cursor.execute(query, (platform_game_id,))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if len(results) == 2:
        return results[0]['acronym'], results[1]['acronym']
    elif len(results) == 1:
        return results[0]['acronym'], 'TBD'
    else:
        return 'TBD', 'TBD'

def get_game_events(platform_game_id, player_id, event_type, conn):
    """Get game events for a player"""
    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                deceased_x, deceased_y, killer_x, killer_y,
                true_deceased_id, true_killer_id, killer_is_attacking, deceased_is_attacking
            FROM player_died
            WHERE platform_game_id = %s 
            AND (true_deceased_id = %s OR true_killer_id = %s)
        """
        cursor.execute(query, (platform_game_id, player_id, player_id))
        events = cursor.fetchall()

        if event_type == 'kills':
            return [e for e in events if e['true_killer_id'] == player_id]
        elif event_type == 'deaths':
            return [e for e in events if e['true_deceased_id'] == player_id]
        else:
            return events

    except Exception as e:
        logger.error(f"Error in get_game_events: {str(e)}")
        return []

def get_distinct_colors(n):
    """Generate distinct colors for visualization"""
    hue_start = 0.0
    hue_step = 0.618033988749895
    saturation = 0.7
    value = 0.95

    colors = []
    for i in range(n):
        hue = (hue_start + i * hue_step) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append((int(r*255), int(g*255), int(b*255)))

    cb_friendly_palette = [
        (0, 114, 178),   # Blue
        (230, 159, 0),   # Orange
        (0, 158, 115),   # Green
        (204, 121, 167), # Purple
        (213, 94, 0),    # Vermillion
        (86, 180, 233),  # Sky Blue
        (0, 158, 115),   # Bluish Green
        (240, 228, 66),  # Yellow
    ]

    return cb_friendly_palette[:min(n, len(cb_friendly_palette))] + colors[:max(0, n - len(cb_friendly_palette))]

def upload_to_s3(file_name, file_content, content_type):
    """Upload file to S3 bucket"""
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=file_name,
            Body=file_content,
            ContentType=content_type
        )
        return f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{file_name}"
    except ClientError as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        return None