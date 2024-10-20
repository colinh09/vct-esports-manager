import os
import psycopg2
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Connect to the database
conn = psycopg2.connect(os.getenv('RDS_DATABASE_URL'))
cursor = conn.cursor()

# Team acronym to region mapping
team_regions = {
    'ACE': 'EMEA',
    'ACEK': 'APAC',
    'AG': 'CN',
    'ANM': 'EMEA',
    'ARFS': 'APAC',
    'ASE': 'CN',
    'ASEO': 'CN',
    'ASTR': 'APAC',
    'BBGS': 'CN',
    'BBL': 'EMEA',
    'BIG': 'EMEA',
    'BLG': 'CN',
    'CAPY': 'APAC',
    'CCG': 'CN',
    'CG': 'APAC',
    'DRG': 'CN',
    'EDG': 'CN',
    'EDGS': 'CN',
    'FKS': 'EMEA',
    'FLC': 'EMEA',
    'FNC': 'EMEA',
    'FPX': 'CN',
    'FRZ': 'EMEA',
    'FUT': 'EMEA',
    'G0DL': 'APAC',
    'GANG': 'APAC',
    'GDR': 'APAC',
    'GE': 'APAC',
    'GES': 'APAC',
    'GIA': 'EMEA',
    'GMB': 'EMEA',
    'GMD': 'APAC',
    'GRY': 'APAC',
    'GUI': 'EMEA',
    'JDG': 'CN',
    'KC': 'EMEA',
    'KOI': 'EMEA',
    'KONE': 'CN',
    'LES': 'APAC',
    'LKR': 'CN',
    'LL': 'APAC',
    'M8': 'EMEA',
    'MAD1': 'APAC',
    'MDL': 'APAC',
    'MLT': 'APAC',
    'N2F': 'APAC',
    'NAVI': 'EMEA',
    'NOVA': 'CN',
    'NPG': 'CN',
    'O3O': 'APAC',
    'OGS': 'APAC',
    'OGT': 'APAC',
    'PURR': 'APAC',
    'QTXX': 'APAC',
    'RBLS': 'EMEA',
    'RGE': 'APAC',
    'RVNT': 'APAC',
    'S1': 'EMEA',
    'SMB': 'EMEA',
    'SUR': 'EMEA',
    'SXG': 'CN',
    'TE': 'CN',
    'TEC': 'CN',
    'TH': 'EMEA',
    'TL': 'EMEA',
    'TLN': 'APAC',
    'TRR': 'APAC',
    'TYL': 'CN',
    'URB': 'CN',
    'UWU': 'KR',
    'VIT': 'EMEA',
    'VLT': 'APAC',
    'WOL': 'CN',
    'XL': 'EMEA',
    'XTB': 'APAC',
    'ZTA': 'EMEA'
}

try:
    # Get all players with 'INTL' region and their team acronyms
    cursor.execute("""
    SELECT DISTINCT p.player_id, t.acronym
    FROM players p
    JOIN teams t ON p.home_team_id = t.team_id
    WHERE p.region = 'INTL';
    """)
    intl_players = cursor.fetchall()

    updated_count = 0
    for player_id, team_acronym in intl_players:
        if team_acronym in team_regions:
            new_region = team_regions[team_acronym]
            # Update the region for this player
            cursor.execute("""
            UPDATE players
            SET region = %s
            WHERE player_id = %s AND region = 'INTL';
            """, (new_region, player_id))
            
            updated_count += 1
            logging.info(f"Updated region for player {player_id} (team {team_acronym}) to {new_region}")
        else:
            logging.warning(f"No region mapping found for team acronym {team_acronym} (player {player_id})")

    conn.commit()
    logging.info(f"Updates completed. {updated_count} players updated.")

    # Check for any remaining 'INTL' players
    cursor.execute("SELECT COUNT(*) FROM players WHERE region = 'INTL';")
    remaining_intl = cursor.fetchone()[0]
    if remaining_intl > 0:
        logging.warning(f"There are still {remaining_intl} players with 'INTL' region.")
    else:
        logging.info("All 'INTL' regions have been updated successfully.")

except Exception as e:
    conn.rollback()
    logging.error(f"An error occurred: {e}")

finally:
    cursor.close()
    conn.close()
    logging.info("Database connection closed")