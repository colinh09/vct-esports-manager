import json
import requests
from PIL import Image, ImageDraw, ImageFont
import io
from decimal import Decimal, getcontext

# Set a high precision for decimal calculations
getcontext().prec = 50

def download_image(url):
    response = requests.get(url)
    return Image.open(io.BytesIO(response.content))

def load_map_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def transform_coordinates(x, y, map_data, image_width, image_height):
    # Use Decimal for high-precision calculations
    x = Decimal(str(x))
    y = Decimal(str(y))
    xMultiplier = Decimal(str(map_data['xMultiplier']))
    yMultiplier = Decimal(str(map_data['yMultiplier']))
    xScalarToAdd = Decimal(str(map_data['xScalarToAdd']))
    yScalarToAdd = Decimal(str(map_data['yScalarToAdd']))
    
    # Scale and swap coordinates (implicit 90-degree rotation)
    norm_x = (y * xMultiplier) + xScalarToAdd
    norm_y = (x * yMultiplier) + yScalarToAdd
    
    pixel_x = int((norm_x * Decimal(str(image_height))).to_integral_value())
    pixel_y = int((norm_y * Decimal(str(image_width))).to_integral_value())
    
    return pixel_x, pixel_y

def draw_callouts(image, map_data):
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
    except IOError:
        font = ImageFont.load_default()
    image_width, image_height = image.size
    
    for callout in map_data['callouts']:
        x, y = Decimal(str(callout['location']['x'])), Decimal(str(callout['location']['y']))
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
    minimap.save('sunset_map_with_callouts.png')
    print("Map with callouts saved as 'sunset_map_with_callouts.png'")

if __name__ == "__main__":
    main()