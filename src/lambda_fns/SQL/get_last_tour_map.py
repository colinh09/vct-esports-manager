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
import seaborn as sns

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

            img = Image.open(io.BytesIO(requests.get(map_data['displayIcon']).content))
            draw = ImageDraw.Draw(img)

            for i, game in enumerate(map_games):
                game['color'] = colors[i]
                plot_game_events(draw, game, player_id, map_data, event_type)

            map_visualizations[map_url] = {
                'image': img,
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
            img_with_legend = add_legend(map_viz['image'], map_viz['games'], event_type)
            file_name = f"{player_id}_last_tournament/map_{tournament_info['tournament_id']}_{map_viz['display_name']}.png"
            
            img_buffer = io.BytesIO()
            img_with_legend.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            s3_url = upload_to_s3(file_name, img_buffer, 'image/png')
            
            if s3_url:
                result["maps"][map_viz['display_name']] = {
                    "file_url": s3_url,
                    "map_url": map_url,
                    "games": [{
                        "match_id": game['match_id'],
                        "game_date": game['game_date'].strftime('%Y-%m-%d'),
                        "color": '#{:02x}{:02x}{:02x}'.format(*game['color']),
                        "kills": game['kills'],
                        "deaths": game['deaths'],
                        "assists": game['assists'],
                        "combat_score": game['combat_score']
                    } for game in map_viz['games']]
                }
            else:
                logger.error(f"Failed to upload image to S3: {file_name}")

        cache_tournament_data(player_id, result)

        return result

    except Exception as e:
        logger.error(f"Error in get_tournament_map_visualizations: {str(e)}", exc_info=True)
        return {"error": str(e)}

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
                true_deceased_id, true_killer_id
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

def plot_game_events(draw, game, player_id, map_data, event_type):
    events = get_game_events(game['platform_game_id'], player_id, event_type)
    image_width, image_height = draw.im.size
    color = game['color']
    
    for event in events:
        deceased_x, deceased_y = transform_coordinates(event['deceased_x'], event['deceased_y'], map_data, image_width, image_height)
        killer_x, killer_y = transform_coordinates(event['killer_x'], event['killer_y'], map_data, image_width, image_height)
        
        if all(coord is not None for coord in [killer_x, killer_y, deceased_x, deceased_y]):
            # Draw black line and dot for all events
            draw.line((killer_x, killer_y, deceased_x, deceased_y), fill="black", width=1)
            draw.ellipse((deceased_x - 2, deceased_y - 2, deceased_x + 2, deceased_y + 2), fill="black")

            if event['true_killer_id'] == player_id and (event_type in ['kills', 'both']):
                draw.ellipse((killer_x - 5, killer_y - 5, killer_x + 5, killer_y + 5), fill=color)
            elif event['true_deceased_id'] == player_id and (event_type in ['deaths', 'both']):
                draw_x(draw, killer_x, killer_y, 5, color)

def draw_x(draw, x, y, size, fill):
    draw.line((x - size, y - size, x + size, y + size), fill=fill, width=2)
    draw.line((x - size, y + size, x + size, y - size), fill=fill, width=2)

def add_legend(img, games, event_type):
    legend_width = 300
    new_img = Image.new('RGB', (img.width + legend_width, img.height), color='white')
    new_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    
    x, y = img.width + 10, 10
    draw.text((x, y), "Legend:", fill="black", font=font)
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
        draw.text((x + 30, y - 7), "Player's kills", fill="black", font=font)
        y += 30
    if event_type in ['deaths', 'both']:
        draw_x(draw, x + icon_size//2, y, icon_size//2, "black")
        draw.text((x + 30, y - 7), "Player's deaths", fill="black", font=font)
        y += 30  
    
    draw.line((x, y, x + 20, y), fill="black", width=1)
    draw.ellipse((x + 18, y - 2, x + 22, y + 2), fill="black")
    draw.text((x + 30, y - 7), "Event direction", fill="black", font=font)
    
    return new_img

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
    palette = sns.color_palette("husl", n)
    return [(int(r*255), int(g*255), int(b*255)) for r, g, b in palette]

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

# The main Lambda handler function would go here, calling get_tournament_map_visualizations