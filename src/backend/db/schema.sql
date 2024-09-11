-- Create Leagues Table
CREATE TABLE IF NOT EXISTS leagues (
  league_id VARCHAR(255),
  tournament_type VARCHAR(255),
  region VARCHAR(10),
  dark_logo_url TEXT,
  light_logo_url TEXT,
  name VARCHAR(255),
  slug VARCHAR(255),
  PRIMARY KEY (league_id, tournament_type)
);

-- Create Tournaments Table
CREATE TABLE IF NOT EXISTS tournaments (
  tournament_id VARCHAR(255),
  tournament_type VARCHAR(255),
  status VARCHAR(50),
  league_id VARCHAR(255),
  time_zone VARCHAR(50),
  name VARCHAR(255),
  PRIMARY KEY (tournament_id, tournament_type),
  FOREIGN KEY (league_id, tournament_type) REFERENCES leagues(league_id, tournament_type) ON DELETE CASCADE
);

-- Create Teams Table
CREATE TABLE IF NOT EXISTS teams (
  team_id VARCHAR(255),
  tournament_type VARCHAR(255),
  acronym VARCHAR(10),
  home_league_id VARCHAR(255),
  dark_logo_url TEXT,
  light_logo_url TEXT,
  slug VARCHAR(255),
  name VARCHAR(255),
  PRIMARY KEY (team_id, tournament_type),
  FOREIGN KEY (home_league_id, tournament_type) REFERENCES leagues(league_id, tournament_type) ON DELETE CASCADE,
  UNIQUE (team_id, tournament_type)
);

-- Create Players Table
CREATE TABLE IF NOT EXISTS players (
  player_id VARCHAR(255),
  tournament_type VARCHAR(255),
  handle VARCHAR(255),
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  status VARCHAR(50),
  photo_url TEXT,
  home_team_id VARCHAR(255),
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (player_id, tournament_type)
);

-- Create Game Mapping Table
CREATE TABLE IF NOT EXISTS game_mapping (
  platform_game_id VARCHAR(255) PRIMARY KEY,
  esports_game_id VARCHAR(255),
  tournament_id VARCHAR(255),
  tournament_type VARCHAR(255),
  year INTEGER,
  FOREIGN KEY (tournament_id, tournament_type) REFERENCES tournaments(tournament_id, tournament_type) ON DELETE CASCADE
);

-- Create Player Mapping Table
CREATE TABLE IF NOT EXISTS player_mapping (
  internal_player_id VARCHAR(255),
  player_id VARCHAR(255),
  tournament_type VARCHAR(255),
  platform_game_id VARCHAR(255),
  PRIMARY KEY (internal_player_id, platform_game_id),
  FOREIGN KEY (player_id, tournament_type) REFERENCES players(player_id, tournament_type) ON DELETE CASCADE,
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Team Mapping Table
CREATE TABLE IF NOT EXISTS team_mapping (
  internal_team_id VARCHAR(255),
  team_id VARCHAR(255),
  tournament_type VARCHAR(255),
  platform_game_id VARCHAR(255),
  PRIMARY KEY (internal_team_id, platform_game_id),
  FOREIGN KEY (team_id, tournament_type) REFERENCES teams(team_id, tournament_type) ON DELETE CASCADE,
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Events Table
CREATE TABLE IF NOT EXISTS events (
  event_id BIGSERIAL PRIMARY KEY,
  platform_game_id VARCHAR(255),
  event_type VARCHAR(255),
  tournament_type VARCHAR(255),
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Event Players Table
CREATE TABLE IF NOT EXISTS event_players (
  event_player_id BIGSERIAL PRIMARY KEY,
  event_id BIGINT,
  internal_player_id VARCHAR(255),
  platform_game_id VARCHAR(255),
  
  kill_id VARCHAR(255) DEFAULT NULL,
  death_id VARCHAR(255) DEFAULT NULL,
  assist_id VARCHAR(255) DEFAULT NULL,
  
  damage_dealt FLOAT DEFAULT NULL,
  damage_location VARCHAR(50) DEFAULT NULL,
  
  spike_status VARCHAR(50) DEFAULT NULL,
  weapon_used VARCHAR(255) DEFAULT NULL,
  
  ability_used VARCHAR(255) DEFAULT NULL,
  
  revived_by_id VARCHAR(255) DEFAULT NULL,
  revived_player_id VARCHAR(255) DEFAULT NULL,
  
  FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE,
  FOREIGN KEY (internal_player_id, platform_game_id) REFERENCES player_mapping(internal_player_id, platform_game_id) ON DELETE CASCADE
);
