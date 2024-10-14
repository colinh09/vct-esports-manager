import logging
import os
import json
import io
import base64
import requests
from collections import defaultdict
import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw, ImageFont
from db_connection import get_db_connection
from get_last_game_map import get_map_data, transform_coordinates
import colorsys

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET_NAME = "map-imgs"
S3_REGION = "us-east-1"

s3_client = boto3.client('s3', region_name=S3_REGION)

def get_tournament_map_visualizations(player_id, event_type='both'):
    try:
        cached_data = get_cached_tournament_data(player_id)
        if cached_data:
            logger.info(f"Returning cached data for player {player_id}")
            return cached_data

        tournament_info = get_latest_tournament(player_id)
        if not tournament_info:
            return {"error": "No recent tournament found for the player"}

        games = get_tournament_games(player_id, tournament_info['tournament_id'], tournament_info['tournament_type'])
        if not games:
            return {"error": "No games found for the player in the latest tournament"}

        games_by_map = defaultdict(list)
        for game in games:
            games_by_map[game['map']].append(game)

        colors = get_distinct_colors(len(games))
        map_visualizations = {}

        for map_url, map_games in games_by_map.items():
            map_data = get_map_data(map_url)
            if not map_data:
                logger.warning(f"Map data not found for {map_url}")
                continue

            img_attacking = Image.open(io.BytesIO(requests.get(map_data['displayIcon']).content))
            img_defending = Image.open(io.BytesIO(requests.get(map_data['displayIcon']).content))
            draw_attacking = ImageDraw.Draw(img_attacking)
            draw_defending = ImageDraw.Draw(img_defending)

            for i, game in enumerate(map_games):
                game['color'] = colors[i]
                game['attacker_kills'], game['defender_kills'], game['attacker_deaths'], game['defender_deaths'] = plot_game_events(draw_attacking, draw_defending, game, player_id, map_data, event_type)

            map_visualizations[map_url] = {
                'image_attacking': img_attacking,
                'image_defending': img_defending,
                'games': map_games,
                'display_name': map_data['displayName']
            }

        result = {
            "player_id": player_id,
            "tournament_id": tournament_info['tournament_id'],
            "tournament_type": tournament_info['tournament_type'],
            "tournament_name": tournament_info['tournament_name'],
            "league_name": tournament_info['league_name'],
            "league_region": tournament_info['league_region'],
            "event_type": event_type,
            "maps": {}
        }

        for map_url, map_viz in map_visualizations.items():
            img_attacking_with_legend = add_legend(map_viz['image_attacking'], map_viz['games'], event_type, "Attacking")
            img_defending_with_legend = add_legend(map_viz['image_defending'], map_viz['games'], event_type, "Defending")
            
            map_directory = f"{player_id}_last_tournament/{map_viz['display_name']}"
            file_name_attacking = f"{map_directory}/attacking_{tournament_info['tournament_id']}.png"
            file_name_defending = f"{map_directory}/defending_{tournament_info['tournament_id']}.png"
            
            img_buffer_attacking = io.BytesIO()
            img_attacking_with_legend.save(img_buffer_attacking, format='PNG')
            img_buffer_attacking.seek(0)
            
            img_buffer_defending = io.BytesIO()
            img_defending_with_legend.save(img_buffer_defending, format='PNG')
            img_buffer_defending.seek(0)
            
            s3_url_attacking = upload_to_s3(file_name_attacking, img_buffer_attacking, 'image/png')
            s3_url_defending = upload_to_s3(file_name_defending, img_buffer_defending, 'image/png')
            
            if s3_url_attacking and s3_url_defending:
                result["maps"][map_viz['display_name']] = {
                    "file_url_attacking": s3_url_attacking,
                    "file_url_defending": s3_url_defending,
                    "map_url": map_url,
                    "games": [{
                        "match_id": game['match_id'],
                        "game_date": game['game_date'].strftime('%Y-%m-%d'),
                        "color": '#{:02x}{:02x}{:02x}'.format(*game['color']),
                        "kills": game['kills'],
                        "deaths": game['deaths'],
                        "assists": game['assists'],
                        "combat_score": game['combat_score'],
                        "attacker_kills": game['attacker_kills'],
                        "defender_kills": game['defender_kills'],
                        "attacker_deaths": game['attacker_deaths'],
                        "defender_deaths": game['defender_deaths']
                    } for game in map_viz['games']]
                }
            else:
                logger.error(f"Failed to upload images to S3 for map: {map_viz['display_name']}")

        cache_tournament_data(player_id, result)

        return result

    except Exception as e:
        logger.error(f"Error in get_tournament_map_visualizations: {str(e)}", exc_info=True)
        return {"error": str(e)}

def plot_game_events(draw_attacking, draw_defending, game, player_id, map_data, event_type):
    events = get_game_events(game['platform_game_id'], player_id, event_type)
    image_width, image_height = draw_attacking.im.size
    color = game['color']
    
    attacker_kills, defender_kills, attacker_deaths, defender_deaths = 0, 0, 0, 0
    
    for event in events:
        deceased_x, deceased_y = transform_coordinates(event['deceased_x'], event['deceased_y'], map_data, image_width, image_height)
        killer_x, killer_y = transform_coordinates(event['killer_x'], event['killer_y'], map_data, image_width, image_height)
        
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
    draw.line((x - size, y - size, x + size, y + size), fill=fill, width=2)
    draw.line((x - size, y + size, x + size, y - size), fill=fill, width=2)

def add_legend(img, games, event_type, side):
    legend_width = 300
    new_img = Image.new('RGB', (img.width + legend_width, img.height), color='white')
    new_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    
    x, y = img.width + 10, 10
    draw.text((x, y), f"Legend ({side}):", fill="black", font=font)
    y += 30
    
    for i, game in enumerate(games):
        team1, team2 = get_team_acronyms(game['match_id'])
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
    
    # Add legend item for kill direction
    draw.line((x, y, x + 20, y), fill="black", width=1)
    draw.ellipse((x + 18, y - 2, x + 22, y + 2), fill="black")
    draw.text((x + 30, y - 7), "Kill direction", fill="black", font=font)
    
    return new_img

def get_cached_tournament_data(player_id):
    try:
        cache_file = f"{player_id}_last_tournament/cache.json"
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=cache_file)
        cached_data = json.loads(response['Body'].read().decode('utf-8'))
        return cached_data
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        else:
            logger.error(f"Error retrieving cached data: {str(e)}")
            return None

def cache_tournament_data(player_id, data):
    try:
        cache_file = f"{player_id}_last_tournament/cache.json"
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=cache_file,
            Body=json.dumps(data),
            ContentType='application/json'
        )
        logger.info(f"Cached tournament data for player {player_id}")
    except ClientError as e:
        logger.error(f"Error caching tournament data: {str(e)}")

def get_latest_tournament(player_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT 
        gm.tournament_id, 
        gm.tournament_type, 
        gm.game_date, 
        t.name as tournament_name,
        l.name as league_name,
        l.region as league_region
    FROM game_mapping gm
    JOIN player_mapping pm ON gm.platform_game_id = pm.platform_game_id
    JOIN tournaments t ON gm.tournament_id = t.tournament_id AND gm.tournament_type = t.tournament_type
    JOIN leagues l ON t.league_id = l.league_id AND t.tournament_type = l.tournament_type
    WHERE pm.player_id = %s
    ORDER BY gm.game_date DESC
    LIMIT 1
    """
    
    cursor.execute(query, (player_id,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if result:
        return {
            'tournament_id': result['tournament_id'],
            'tournament_type': result['tournament_type'],
            'tournament_name': result['tournament_name'].replace('_', ' ').title(),
            'league_name': result['league_name'].replace('_', ' ').title(),
            'league_region': 'International' if result['league_region'] == 'INTL' else result['league_region']
        }
    else:
        return None

def get_tournament_games(player_id, tournament_id, tournament_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT gm.platform_game_id, gm.map, gm.game_date, gm.match_id,
           pm.kills, pm.deaths, pm.assists, pm.combat_score
    FROM game_mapping gm
    JOIN player_mapping pm ON gm.platform_game_id = pm.platform_game_id
    WHERE pm.player_id = %s AND gm.tournament_id = %s AND gm.tournament_type = %s
    ORDER BY gm.game_date
    """
    
    cursor.execute(query, (player_id, tournament_id, tournament_type))
    games = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return games

def get_game_events(platform_game_id, player_id, event_type):
    try:
        conn = get_db_connection()
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

        cursor.close()
        conn.close()

        if event_type == 'kills':
            return [e for e in events if e['true_killer_id'] == player_id]
        elif event_type == 'deaths':
            return [e for e in events if e['true_deceased_id'] == player_id]
        else:
            return events

    except Exception as e:
        logger.error(f"Error in get_game_events: {str(e)}", exc_info=True)
        raise

def get_team_acronyms(match_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT t.acronym
    FROM game_mapping gm
    JOIN team_mapping tm ON gm.platform_game_id = tm.platform_game_id
    JOIN teams t ON tm.team_id = t.team_id
    WHERE gm.match_id = %s
    """
    
    cursor.execute(query, (match_id,))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    if len(results) == 2:
        return results[0]['acronym'], results[1]['acronym']
    elif len(results) == 1:
        return results[0]['acronym'], 'TBD'
    else:
        return 'TBD', 'TBD'

def get_distinct_colors(n):
    hue_start = 0.0
    hue_step = 0.618033988749895  # Golden ratio conjugate
    saturation = 0.7
    value = 0.95

    colors = []
    for i in range(n):
        hue = (hue_start + i * hue_step) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        colors.append((int(r*255), int(g*255), int(b*255)))

    # Predefined colorblind-friendly palette
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

    # Use the colorblind-friendly palette first, then fall back to generated colors
    return cb_friendly_palette[:min(n, len(cb_friendly_palette))] + colors[:max(0, n - len(cb_friendly_palette))]

def upload_to_s3(file_name, file_content, content_type):
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