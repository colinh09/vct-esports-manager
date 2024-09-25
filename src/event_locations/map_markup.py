import json
import requests
from PIL import Image, ImageDraw, ImageFont
import io

def download_image(url):
    response = requests.get(url)
    return Image.open(io.BytesIO(response.content))

def load_map_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def transform_coordinates(x, y, map_data, image_width, image_height):
    # Normalize the coordinates
    norm_x = (x * map_data['xMultiplier']) + map_data['xScalarToAdd']
    norm_y = (y * map_data['yMultiplier']) + map_data['yScalarToAdd']
    
    # Rotate 90 degrees clockwise
    rotated_x = norm_y
    rotated_y = 1 - norm_x
    
    # Invert horizontally
    inverted_x = 1 - rotated_x
    inverted_y = rotated_y
    
    # Convert to pixel coordinates
    pixel_x = int(inverted_x * image_height)
    pixel_y = int(inverted_y * image_width)
    
    return pixel_x, pixel_y

def draw_callouts(image, map_data):
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except IOError:
        font = ImageFont.load_default()
    image_width, image_height = image.size
    
    for callout in map_data['callouts']:
        x, y = callout['location']['x'], callout['location']['y']
        pixel_x, pixel_y = transform_coordinates(x, y, map_data, image_width, image_height)
        
        # Draw a small circle for each callout
        circle_radius = 5
        draw.ellipse([pixel_x - circle_radius, pixel_y - circle_radius,
                      pixel_x + circle_radius, pixel_y + circle_radius],
                     fill='red', outline='white')
        
        # Draw the callout name with super region
        callout_text = f"{callout['superRegionName']} {callout['regionName']}"
        draw.text((pixel_x + 10, pixel_y + 10), callout_text, fill='white', font=font)

def main():
    # Load map data
    maps_data = load_map_data('maps.json')
    
    # Find the Sunset map
    sunset_map = next((map_data for map_data in maps_data if map_data['displayName'] == 'Sunset'), None)
    
    if sunset_map is None:
        print("Sunset map not found in the data.")
        return
    
    # Download the minimap image
    minimap = download_image(sunset_map['displayIcon'])
    
    # Draw callouts on the minimap
    draw_callouts(minimap, sunset_map)
    
    # Save the result
    minimap.save('sunset_map_with_callouts2.png')
    print("Map with callouts saved as 'sunset_map_with_callouts.png'")

if __name__ == "__main__":
    main()