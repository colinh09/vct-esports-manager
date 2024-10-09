import os
import psycopg2
import logging
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(filename='team_captain_scraper_v2.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("RDS_DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Get team names
cursor.execute("SELECT name FROM teams")
team_names = [row[0] for row in cursor.fetchall()]

# Set up WebDriver
driver = webdriver.Chrome()  # or webdriver.Firefox()

# Initialize results dictionary
results = {}

# Perform initial dummy search to get to the advanced search page
driver.get("https://www.vlr.gg")
search_bar = WebDriverWait(driver, 3).until(
    EC.presence_of_element_located((By.CLASS_NAME, "ui-autocomplete-input"))
)
search_bar.clear()
search_bar.send_keys("dummy search")
search_bar.send_keys(Keys.RETURN)

# Wait for search results to load
WebDriverWait(driver, 3).until(
    EC.presence_of_element_located((By.CLASS_NAME, "wf-card"))
)

def safe_click(element):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            element.click()
            return True
        except StaleElementReferenceException:
            if attempt == max_attempts - 1:
                return False
            driver.refresh()
    return False

def get_team_links():
    try:
        return WebDriverWait(driver, 3).until(
            EC.presence_of_all_elements_located((By.XPATH, "//a[contains(@class, 'wf-module-item')]"))
        )
    except TimeoutException:
        return []

for index, team_name in enumerate(team_names, 1):
    logging.info(f"Processing team {index}/{len(team_names)}: {team_name}")
    results[team_name] = []
    try:
        # Set filter to "Teams"
        category_select = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.NAME, "type"))
        )
        for option in category_select.find_elements(By.TAG_NAME, 'option'):
            if option.text == 'Teams':
                option.click()
                break

        # Perform search for the team
        search_input = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.ID, "form-q"))
        )
        search_input.clear()
        search_input.send_keys(team_name)
        search_input.send_keys(Keys.RETURN)

        team_links = get_team_links()
        if not team_links:
            logging.info(f"No teams found for {team_name}")
            continue

        for i in range(len(team_links)):
            # Re-fetch links to avoid stale elements
            team_links = get_team_links()
            if i >= len(team_links):
                break

            link = team_links[i]
            found_team_name = link.text
            if not safe_click(link):
                logging.info(f"Failed to click on link for {found_team_name}")
                continue

            # Find team captain
            try:
                captain_element = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//i[@class='fa fa-star']/../.."))
                )
                captain_name = captain_element.find_element(By.CLASS_NAME, "team-roster-item-name-alias").text
                logging.info(f"Captain found for {found_team_name}: {captain_name}")
                results[team_name].append((found_team_name, captain_name))
            except (TimeoutException, NoSuchElementException):
                logging.info(f"No captain found for {found_team_name}")
                results[team_name].append((found_team_name, None))

            # Go back to search results
            driver.back()
            
            # Wait for search results to load again
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CLASS_NAME, "wf-card"))
            )

        if not results[team_name]:
            logging.info(f"No matches found for {team_name}")

    except Exception as e:
        logging.info(f"Error processing {team_name}: Unable to complete search")
        results[team_name].append((None, "Error: Unable to complete search"))

# Write results to JSON file
with open("team_captains_v2.json", "w") as f:
    json.dump(results, f, indent=2)

logging.info("Scraping completed. Results written to team_captains_v2.json")

# Cleanup
cursor.close()
conn.close()
driver.quit()

logging.info("Script execution completed")