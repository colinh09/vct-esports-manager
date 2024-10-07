import os
import psycopg2
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(filename='team_captain_scraper2.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()

# Database connection
DATABASE_URL = os.getenv("RDS_DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Function to preprocess team names
def preprocess_name(name):
    # Convert to lowercase
    name = name.lower()
    # Remove special characters and extra spaces
    name = re.sub(r'[^a-z0-9\s]', '', name)
    # Remove extra spaces
    name = ' '.join(name.split())
    return name

# Get team names and preprocess them
cursor.execute("SELECT name FROM teams")
team_names = [(row[0], preprocess_name(row[0])) for row in cursor.fetchall()]

# Set up WebDriver
driver = webdriver.Chrome()

results = []

# Perform initial dummy search to get to the advanced search page
driver.get("https://www.vlr.gg")
search_bar = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "ui-autocomplete-input"))
)
search_bar.clear()
search_bar.send_keys("dummy search")
search_bar.send_keys(Keys.RETURN)

# Wait for search results to load
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "wf-card"))
)

for index, (original_name, processed_name) in enumerate(team_names, 1):
    logging.info(f"Processing team {index}/{len(team_names)}: {original_name}")
    try:
        # Set filter to "Teams"
        category_select = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "type"))
        )
        for option in category_select.find_elements(By.TAG_NAME, 'option'):
            if option.text == 'Teams':
                option.click()
                break

        # Perform search for the team
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "form-q"))
        )
        search_input.clear()
        search_input.send_keys(original_name)
        search_input.send_keys(Keys.RETURN)

        # Wait for search results to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "wf-card"))
        )

        # Find and click on the team link
        try:
            team_links = driver.find_elements(By.XPATH, "//a[contains(@class, 'wf-module-item')]")
            matched_link = None
            for link in team_links:
                link_text = link.text
                processed_link_text = preprocess_name(link_text)
                if processed_name in processed_link_text:
                    matched_link = link
                    break

            if matched_link:
                matched_link.click()

                # Find team captain
                try:
                    captain_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, "//i[@class='fa fa-star']/../.."))
                    )
                    captain_name = captain_element.find_element(By.CLASS_NAME, "team-roster-item-name-alias").text
                    logging.info(f"Captain found for {original_name}: {captain_name}")
                    results.append(f"{original_name} | {captain_name}")
                except (TimeoutException, NoSuchElementException):
                    logging.warning(f"No captain found for {original_name}")
                    results.append(f"{original_name} | No captain found")

                # Go back to search results
                driver.back()
            else:
                logging.warning(f"No match found for {original_name}")
                results.append(f"{original_name} | No match found")

        except (TimeoutException, NoSuchElementException):
            logging.warning(f"No match found for {original_name}")
            results.append(f"{original_name} | No match found")

    except Exception as e:
        logging.error(f"Error processing {original_name}: {str(e)}")
        results.append(f"{original_name} | Error: {str(e)}")

# Write results to file
with open("team_captains2.txt", "w") as f:
    for result in results:
        f.write(result + "\n")

logging.info("Scraping completed. Results written to team_captains.txt")

# Cleanup
cursor.close()
conn.close()
driver.quit()

logging.info("Script execution completed")