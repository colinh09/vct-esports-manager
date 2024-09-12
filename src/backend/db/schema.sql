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

-- Create Player Died Table
CREATE TABLE IF NOT EXISTS player_died (
  event_id BIGSERIAL PRIMARY KEY,
  platform_game_id VARCHAR(255),
  deceased_id VARCHAR(255),
  killer_id VARCHAR(255),
  weapon_guid VARCHAR(255),
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Player Assists Table
CREATE TABLE IF NOT EXISTS player_assists (
  event_id BIGSERIAL PRIMARY KEY, 
  platform_game_id VARCHAR(255),
  assister_id VARCHAR(255),
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Spike Status Table
CREATE TABLE IF NOT EXISTS spike_status (
  event_id BIGSERIAL PRIMARY KEY,
  platform_game_id VARCHAR(255),
  carrier_id VARCHAR(255),
  status VARCHAR(50),
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Damage Event Table
CREATE TABLE IF NOT EXISTS damage_event (
  event_id BIGSERIAL PRIMARY KEY,
  platform_game_id VARCHAR(255),
  causer_id VARCHAR(255),
  victim_id VARCHAR(255),
  location VARCHAR(50),
  damage_amount FLOAT,
  kill_event BOOLEAN,
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Player Revived Table
CREATE TABLE IF NOT EXISTS player_revived (
  event_id BIGSERIAL PRIMARY KEY,
  platform_game_id VARCHAR(255),
  revived_by_id VARCHAR(255),
  revived_id VARCHAR(255),
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);

-- Create Ability Used Table
CREATE TABLE IF NOT EXISTS ability_used (
  event_id BIGSERIAL PRIMARY KEY,
  platform_game_id VARCHAR(255),
  player_id VARCHAR(255),
  ability_guid VARCHAR(255),
  inventory_slot VARCHAR(50),
  charges_consumed INTEGER,
  FOREIGN KEY (platform_game_id) REFERENCES game_mapping(platform_game_id) ON DELETE CASCADE
);
