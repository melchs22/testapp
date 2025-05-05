import os
import time
import schedule
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import git
from datetime import datetime
import shutil
import pandas as pd
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('script.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Hardcoded credentials (replace with your actual credentials)
USERNAME = "tutu.melchizedek@bodabodaunion.ug"
PASSWORD = "tutu.melchizedek"

# Git repository details
REPO_PATH = r"C:\testapp"  # Local repository path
REPO_REMOTE = "origin"  # Replace with your remote name if different
REPO_BRANCH = "main"  # Replace with your branch name if different

# Optional: Set download directory
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

options = webdriver.ChromeOptions()
prefs = {"download.default_directory": DOWNLOAD_DIR}
options.add_experimental_option("prefs", prefs)

# Set wait time to 15 seconds
WAIT_TIME = 15

def download_rename_and_convert_csv(driver, url, page_name, file_name):
    logger.info(f"Navigating to {page_name} page...")
    driver.get(url)
    time.sleep(WAIT_TIME)  # Wait for page to load

    logger.info(f"Looking for CSV download button on {page_name} page...")
    try:
        csv_elements = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_all_elements_located((By.XPATH, "//*[contains(text(), 'CSV') or contains(@value, 'CSV')]"))
        )

        for element in csv_elements:
            try:
                logger.info(f"Attempting to click element: {element.text or element.get_attribute('value')}")
                element.click()
                logger.info(f"CSV download initiated for {page_name}")
                time.sleep(WAIT_TIME)  # Wait for download to complete
                
                # Find the downloaded CSV file
                downloaded_file = max([os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)], key=os.path.getctime)
                
                # Convert CSV to XLSX and save directly to REPO_PATH, overwriting existing file
                df = pd.read_csv(downloaded_file)
                new_filename = f"{file_name}.xlsx"
                new_filepath = os.path.join(REPO_PATH, new_filename)
                df.to_excel(new_filepath, index=False)
                
                # Remove the original CSV file
                os.remove(downloaded_file)
                
                logger.info(f"File converted to XLSX and saved to: {new_filepath}")
                return new_filename  # Return the relative file name for Git staging
            except Exception as click_error:
                logger.error(f"Failed to click element or process file: {str(click_error)}")
        else:
            logger.warning(f"No clickable CSV element found on {page_name} page")
            return None

    except TimeoutException:
        logger.error(f"CSV button not found within the timeout period on {page_name} page.")
        return None

def push_to_git(repo_path, files):
    try:
        repo = git.Repo(repo_path)

        # Pull the latest changes to avoid conflicts
        logger.info(f"Pulling latest changes from {REPO_REMOTE}/{REPO_BRANCH}...")
        repo.remotes[REPO_REMOTE].pull()

        # Stage the specific files (overwriting existing ones)
        logger.info(f"Staging {len(files)} files: {files}")
        repo.index.add(files)  # Add or update the files in the index

        # Check if there are changes to commit
        if repo.is_dirty(untracked_files=True):
            # Commit the changes
            commit_message = f"Update XLSX files - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            repo.index.commit(commit_message)
            logger.info(f"Committed changes with message: {commit_message}")

            # Push the changes
            repo.remotes[REPO_REMOTE].push()
            logger.info(f"Successfully pushed {len(files)} files to the repository.")
        else:
            logger.info("No changes to commit. Repository is up to date.")

    except Exception as e:
        logger.error(f"An error occurred while pushing to Git: {str(e)}")

def main_job():
    logger.info("Starting job execution...")
    driver = None
    try:
        # Start browser
        driver = webdriver.Chrome(options=options)

        # Login process
        logger.info("Opening login page...")
        driver.get("https://backend.bodabodaunion.ug/admin")

        logger.info("Waiting for page to load...")
        WebDriverWait(driver, WAIT_TIME).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        logger.info(f"Current URL: {driver.current_url}")

        logger.info("Filling in username...")
        username_field = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='data[User][username]']"))
        )
        username_field.send_keys(USERNAME)

        logger.info("Filling in password...")
        password_field = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='data[User][password]']"))
        )
        password_field.send_keys(PASSWORD)

        logger.info("Clicking login button...")
        login_button = WebDriverWait(driver, WAIT_TIME).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        login_button.click()

        logger.info("Waiting for login to complete...")
        WebDriverWait(driver, WAIT_TIME).until(EC.url_changes("https://backend.bodabodaunion.ug/admin"))

        logger.info(f"New URL after login: {driver.current_url}")

        # Download CSVs from different pages
        pages = [
            ("https://backend.bodabodaunion.ug/admin/drivers", "Drivers", "DRIVERS"),
            ("https://backend.bodabodaunion.ug/admin/users/storeindex", "Active Passengers", "PASSENGERS"),
            ("https://backend.bodabodaunion.ug/admin/trips", "Trips", "BEER"),
            ("https://backend.bodabodaunion.ug/admin/transactions", "Transaction Manager", "TRANSACTIONS")
        ]

        xlsx_files = []
        for url, page_name, file_name in pages:
            file_path = download_rename_and_convert_csv(driver, url, page_name, file_name)
            if file_path:
                xlsx_files.append(file_path)
                logger.info(f"✅ CSV downloaded, converted to XLSX, and replaced for {page_name}")
            else:
                logger.warning(f"❌ Failed to download and process CSV for {page_name}")

        if xlsx_files:
            logger.info("\nDownloaded, converted, and replaced XLSX files:")
            for file in xlsx_files:
                logger.info(f"- {os.path.join(REPO_PATH, file)}")

            # Push to Git
            push_to_git(REPO_PATH, xlsx_files)
        else:
            logger.warning("\n❌ No files were successfully downloaded, converted, and replaced")

    except Exception as e:
        logger.error(f"An error occurred in main job: {str(e)}")
        logger.debug("Current page source:")
        logger.debug(driver.page_source if driver else "No driver available")

    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed.")

def run_scheduler():
    # Schedule the job every 45 minutes
    schedule.every(45).minutes.do(main_job)
    logger.info("Scheduler started. Running job every 45 minutes. Press Ctrl+C to stop.")

    # Run the first job immediately
    main_job()

    # Keep the script running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute to reduce CPU usage
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
            break
        except Exception as e:
            logger.error(f"Error in scheduler: {str(e)}")
            time.sleep(60)  # Wait before retrying to prevent rapid error loops

if __name__ == "__main__":
    run_scheduler()
