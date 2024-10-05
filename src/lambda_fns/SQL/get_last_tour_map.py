import logging
from db_connection import get_db_connection
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import requests
from get_last_game_map import get_map_data, transform_coordinates
import colorsys
from collections import defaultdict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_n_hue_colors(n):
    HSV_tuples = [(x * 1.0 / n, 0.5, 0.5) for x in range(n)]
    return list(map(lambda x: tuple(int(i * 255) for i in colorsys.hsv_to_rgb(*x)), HSV_tuples))

def get_tournament_map_visualizations(player_id, event_type='both'):
    try:
        tournament_id, tournament_type, tournament_name = get_latest_tournament(player_id)
        if not tournament_id:
            return {"error": "No recent tournament found for the player"}

        games = get_tournament_games(player_id, tournament_id, tournament_type)
        if not games:
            return {"error": "No games found for the player in the latest tournament"}

        # Group games by map
        games_by_map = defaultdict(list)
        for game in games:
            games_by_map[game['map']].append(game)

        colors = get_n_hue_colors(len(games))
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
                'games': map_games
            }

        result = {
            "player_id": player_id,
            "tournament_id": tournament_id,
            "tournament_type": tournament_type,
            "tournament_name": tournament_name,
            "event_type": event_type,
            "maps": {}
        }

        for map_url, map_viz in map_visualizations.items():
            img_with_legend = add_legend(map_viz['image'], map_viz['games'], event_type)
            file_name = f"map_{player_id}_{tournament_id}_{map_url.split('/')[-1]}.png"
            img_with_legend.save(file_name)
            
            result["maps"][map_url] = {
                "file_name": file_name,
                "games": [{"match_id": game['match_id'], "game_date": game['game_date'].strftime('%Y-%m-%d'), "color": '#{:02x}{:02x}{:02x}'.format(*game['color'])} for game in map_viz['games']]
            }

        return result

    except Exception as e:
        logger.error(f"Error in get_tournament_map_visualizations: {str(e)}", exc_info=True)
        return {"error": str(e)}

def get_latest_tournament(player_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT gm.tournament_id, gm.tournament_type, gm.game_date, t.name as tournament_name
    FROM game_mapping gm
    JOIN player_mapping pm ON gm.platform_game_id = pm.platform_game_id
    JOIN tournaments t ON gm.tournament_id = t.tournament_id
    WHERE pm.player_id = %s
    ORDER BY gm.game_date DESC
    LIMIT 1
    """
    
    cursor.execute(query, (player_id,))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return (result['tournament_id'], result['tournament_type'], result['tournament_name']) if result else (None, None, None)

def get_tournament_games(player_id, tournament_id, tournament_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
    SELECT gm.platform_game_id, gm.map, gm.game_date, gm.match_id
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
            if event['true_killer_id'] == player_id and (event_type in ['kills', 'both']):
                draw.line((killer_x, killer_y, deceased_x, deceased_y), fill=color, width=2)
                draw.ellipse((deceased_x - 5, deceased_y - 5, deceased_x + 5, deceased_y + 5), fill=color)
            elif event['true_deceased_id'] == player_id and (event_type in ['deaths', 'both']):
                draw.line((killer_x, killer_y, deceased_x, deceased_y), fill=color, width=2)
                draw.ellipse((deceased_x - 5, deceased_y - 5, deceased_x + 5, deceased_y + 5), fill=color)

def add_legend(img, games, event_type):
    legend_width = 300
    new_img = Image.new('RGB', (img.width + legend_width, img.height), color='white')
    new_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    font = ImageFont.load_default()
    
    x, y = img.width + 10, 10
    draw.text((x, y), "Legend:", fill="black", font=font)
    y += 20
    
    for i, game in enumerate(games):
        team1, team2 = get_team_acronyms(game['match_id'])
        match_text = f"{team1} vs {team2}"
        color = game['color']
        draw.rectangle([x, y, x+20, y+10], fill=color, outline="black")
        draw.text((x+25, y), f"Game {i+1}: {match_text}", fill="black", font=font)
        y += 20
    
    y += 10
    if event_type in ['kills', 'both']:
        draw.text((x, y), "Circles: Player's kills", fill="black", font=font)
        y += 20
    if event_type in ['deaths', 'both']:
        draw.text((x, y), "Circles: Player's deaths", fill="black", font=font)
    
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