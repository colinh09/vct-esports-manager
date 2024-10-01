import requests
import json
import gzip
import shutil
import time
import os
from io import BytesIO

# Base URL for the S3 bucket
S3_BUCKET_URL = "https://vcthackathon-data.s3.us-west-2.amazonaws.com"

def download_gzip_and_write_to_json(file_name, full_url):
    if os.path.isfile(f"{file_name}.json"):
        print(f"{file_name}.json already exists, skipping download.")
        return

    response = requests.get(full_url)
    if response.status_code == 200:
        try:
            gzip_bytes = BytesIO(response.content)
            with gzip.GzipFile(fileobj=gzip_bytes, mode="rb") as gzipped_file:
                with open(f"{file_name}.json", 'wb') as output_file:
                    shutil.copyfileobj(gzipped_file, output_file)
                print(f"{file_name}.json written")
        except Exception as e:
            print("Error:", e)
    else:
        print(response)
        print(f"Failed to download {file_name}")

def download_esports_files(tournament, specific_files=None):
    directory = f"/home/colin/vct-esports-manager/data/{tournament}/esports-data"
    if not os.path.exists(directory):
        os.makedirs(directory)

    esports_data_files = ["leagues", "tournaments", "players", "teams", "mapping_data", "mapping_data_v2"]

    if specific_files:
        files_to_download = [file for file in esports_data_files if file in specific_files]
    else:
        files_to_download = esports_data_files

    for file_name in files_to_download:
        file_path = f"{directory}/{file_name}"
        full_url = f"{S3_BUCKET_URL}/{tournament}/esports-data/{file_name}.json.gz"
        download_gzip_and_write_to_json(file_path, full_url)

def download_games(tournament, year, specific_game_id=None):
    start_time = time.time()
    mapping_file = f"/home/colin/vct-esports-manager/data/{tournament}/esports-data/mapping_data.json"
    
    if not os.path.isfile(mapping_file):
        print(f"Mapping file not found: {mapping_file}")
        return

    with open(mapping_file, "r") as json_file:
        mappings_data = json.load(json_file)

    directory = f"/home/colin/vct-esports-manager/data/{tournament}/games/{year}"
    if not os.path.exists(directory):
        os.makedirs(directory)

    game_counter = 0

    if specific_game_id:
        full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{specific_game_id}.json.gz"
        download_gzip_and_write_to_json(f"{directory}/{specific_game_id}", full_url)
    else:
        for esports_game in mappings_data:
            platform_game_id = esports_game["platformGameId"]
            full_url = f"{S3_BUCKET_URL}/{tournament}/games/{year}/{platform_game_id}.json.gz"
            download_gzip_and_write_to_json(f"{directory}/{platform_game_id}", full_url)
            game_counter += 1
            if game_counter % 10 == 0:
                print(f"----- Processed {game_counter} games, current run time: {round((time.time() - start_time)/60, 2)} minutes")

def download_fandom_data(file_choice):
    directory = f"/home/colin/vct-esports-manager/data/fandom"
    if not os.path.exists(directory):
        os.makedirs(directory)

    file_name = file_choice
    file_path = f"{directory}/{file_name}"
    full_url = f"{S3_BUCKET_URL}/fandom/{file_name}.xml.gz"
    download_gzip_and_write_to_json(file_path, full_url)

if __name__ == "__main__":
    # User input for selecting type of data
    print("Select data type to download:")
    print("1: Esports Data (tournaments, players, teams, etc.)")
    print("2: Games Data")
    print("3: Fandom Data")

    choice = input("\nEnter the number corresponding to your choice: ")

    if choice == '1':
        print("\nAvailable tournaments:")
        print("vct-international, vct-challengers, game-changers")
        tournament = input("\nEnter tournament name (e.g., vct-international, vct-challengers, game-changers): ")
        
        print("\nAvailable esports data files:")
        print("leagues, tournaments, players, teams, mapping_data, mapping_data_v2")
        specific_files_input = input("\nEnter the specific esports data files you want to download (comma-separated), or type 'all' to download everything: ")
        
        if specific_files_input.lower() == 'all':
            download_esports_files(tournament)
        else:
            specific_files = [file.strip() for file in specific_files_input.split(',')]
            download_esports_files(tournament, specific_files)
    
    elif choice == '2':
        print("\nAvailable tournaments:")
        print("vct-international, vct-challengers, game-changers")
        tournament = input("\nEnter tournament name (e.g., vct-international, vct-challengers, game-changers): ")
        
        year = input("\nEnter the year (2022, 2023, 2024): ")
        
        specific_game_id = input("\nEnter a specific game ID to download or press Enter to download all games: ")
        
        if specific_game_id:
            download_games(tournament, year, specific_game_id)
        else:
            download_games(tournament, year)
    
    elif choice == '3':
        print("\nAvailable fandom data files:")
        print("valorant_esports_pages, valorant_pages")
        
        file_choice = input("\nEnter the file you want to download: ")
        
        if file_choice in ['valorant_esports_pages', 'valorant_pages']:
            download_fandom_data(file_choice)
        else:
            print("\nInvalid file choice.")
    
    else:
        print("\nInvalid choice. Exiting.")
