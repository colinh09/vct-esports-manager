# Query Summary

## Player Queries

### get_player_info_by_handle
- Parameters: handle (string)
- Output: Player info including team and league details
- Description: Retrieves player information based on their handle

### get_player_info_by_name
- Parameters: first_name (string), last_name (string)
- Output: Player info including team and league details
- Description: Retrieves player information based on their first and last name

## Game Queries

### get_all_player_games
- Parameters: player_id (string), tournament_type (string)
- Output: List of games (internal_player_id, platform_game_id)
- Description: Retrieves all games played by a player in a specific tournament type

### get_all_player_games_from_tournament
- Parameters: player_id (string), tournament_type (string), tournament_id (string)
- Output: List of games (internal_player_id, platform_game_id)
- Description: Retrieves all games played by a player in a specific tournament

### get_damage_stats
- Parameters: platform_game_id (string), internal_player_id (string)
- Output: List of damage events (platform_game_id, causer_id, victim_id, damage_amount, location, kill_event)
- Description: Retrieves damage statistics for a player in a specific game

### get_assists
- Parameters: platform_game_id (string), internal_player_id (string)
- Output: List of assist events (platform_game_id, assister_id)
- Description: Retrieves assist statistics for a player in a specific game

### get_deaths
- Parameters: platform_game_id (string), internal_player_id (string)
- Output: List of death events (platform_game_id, deceased_id, killer_id, weapon_guid)
- Description: Retrieves death statistics for a player in a specific game

## Stats Calculations

### get_player_game_stats
- Parameters: player_id (string)
- Output: Aggregated stats (games_played, total_damage, total_kills, total_deaths, total_assists, averages, kda_ratio)
- Description: Calculates aggregated stats for a player across all their games

### get_player_tournament_stats
- Parameters: player_id (string), tournament_id (string)
- Output: Aggregated stats for the tournament (same as get_player_game_stats, plus tournament_id)
- Description: Calculates aggregated stats for a player in a specific tournament