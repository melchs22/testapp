import os
import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import pydeck as pdk
import requests
import os
import re
from dotenv import load_dotenv
import io
from fpdf import FPDF
import base64
import uuid
from plotly.io import to_image

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('script.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Hardcoded credentials (consider moving to environment variables)
USERNAME = "tutu.melchizedek@bodabodaunion.ug"
PASSWORD = "tutu.melchizedek"

# Git repository details
REPO_PATH = r"C:\testapp"
REPO_REMOTE = "origin"
REPO_BRANCH = "main"

# Download directory
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Set wait time to 30 seconds
WAIT_TIME = 30
MAX_RETRIES = 3

def setup_driver(headless=False):
    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")
    # Configure Firefox to show Save As pop-up
    options.set_preference("browser.download.folderList", 0)  # 0 = Desktop (default)
    options.set_preference("browser.download.dir", DOWNLOAD_DIR)  # Default suggestion
    options.set_preference("browser.download.manager.showWhenStarting", True)  # Show dialog
    # Removed: browser.helperApps.neverAsk.saveToDisk to allow pop-up

    try:
        driver = webdriver.Firefox(options=options)
        logger.info("Firefox WebDriver initialized successfully.")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Firefox WebDriver: {str(e)}")
        raise

def take_screenshot(driver, filename):
    try:
        driver.save_screenshot(filename)
        logger.info(f"Screenshot saved: {filename}")
    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

def wait_for_download(download_dir, timeout=60, retries=3):
    logger.info(f"Waiting for file to download in {download_dir}...")
    for attempt in range(retries):
        start_time = time.time()
        while time.time() - start_time < timeout:
            files = [f for f in os.listdir(download_dir) if not f.endswith('.part')]
            if files:
                downloaded_file = max([os.path.join(download_dir, f) for f in files], key=os.path.getctime)
                logger.info(f"Download detected: {downloaded_file}")
                return downloaded_file
            time.sleep(1)
        logger.warning(f"Download attempt {attempt + 1}/{retries} failed. Retrying...")
    logger.error("No file downloaded after all retries.")
    return None

def download_rename_and_convert_csv(driver, url, page_name, file_name):
    logger.info(f"Navigating to {page_name} page: {url}")
    try:
        driver.get(url)
        logger.info(f"Immediately searching for CSV button on {page_name} page...")

        # Retry finding and clicking the CSV button
        for attempt in range(MAX_RETRIES):
            try:
                # Updated XPath to target the button in the toolbar above the table
                csv_button = WebDriverWait(driver, WAIT_TIME).until(
                    EC.element_to_be_clickable((
                        By.XPATH, 
                        "//*[contains(translate(., 'CSV', 'csv'), 'csv') and not(contains(@disabled, 'disabled'))]"
                        # Fallback: Target button in the actions row
                        # "//div[contains(@class, 'actions')]//*[contains(translate(., 'CSV', 'csv'), 'csv')]"
                    ))
                )
                logger.info(f"Found CSV button: tag={csv_button.tag_name}, text={csv_button.text}, "
                           f"enabled={not csv_button.get_attribute('disabled')}, "
                           f"outerHTML={csv_button.get_attribute('outerHTML')[:200]}...")
                break
            except TimeoutException:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"CSV button not found, retrying ({attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(5)
                else:
                    raise
            except Exception as e:
                logger.error(f"Error finding CSV button: {str(e)}")
                take_screenshot(driver, f"{page_name}_button_error_{attempt}.png")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5)
                else:
                    raise

        # Clear download directory
        for f in os.listdir(DOWNLOAD_DIR):
            os.remove(os.path.join(DOWNLOAD_DIR, f))
        logger.info(f"Cleared download directory: {DOWNLOAD_DIR}")

        # Attempt to click the button with retries
        for attempt in range(MAX_RETRIES):
            try:
                # Try JavaScript click to bypass potential clickability issues
                driver.execute_script("arguments[0].scrollIntoView(true);", csv_button)
                driver.execute_script("arguments[0].click();", csv_button)
                logger.info(f"Clicked CSV button for {page_name} (attempt {attempt + 1})")
                break
            except ElementClickInterceptedException:
                logger.warning(f"Click intercepted, retrying ({attempt + 1}/{MAX_RETRIES})...")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Error clicking CSV button: {str(e)}")
                take_screenshot(driver, f"{page_name}_click_error_{attempt}.png")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                else:
                    raise

        # Warn about pop-up and pause for manual handling
        logger.warning("Firefox Save As pop-up should appear. Please select save location (e.g., DOWNLOAD_DIR) and click Save.")
        time.sleep(10)  # Pause for manual interaction

        # Optional: Automate pop-up handling with pyautogui (uncomment to use)
        # if pyautogui:
        #     time.sleep(2)  # Wait for pop-up to appear
        #     pyautogui.write(os.path.join(DOWNLOAD_DIR, f"{file_name}.csv"))
        #     pyautogui.press('enter')
        #     logger.info("Handled Save As pop-up with pyautogui.")
        # else:
        #     logger.warning("pyautogui not available; manual pop-up handling required.")

        # Wait for download with retries
        downloaded_file = wait_for_download(DOWNLOAD_DIR, timeout=WAIT_TIME * 2, retries=MAX_RETRIES)
        if not downloaded_file:
            logger.error(f"Download failed for {page_name}")
            take_screenshot(driver, f"{page_name}_no_download.png")
            return None

        if not downloaded_file.lower().endswith('.csv'):
            logger.warning(f"Downloaded file {downloaded_file} is not a CSV.")
            take_screenshot(driver, f"{page_name}_wrong_file.png")
            return None

        logger.info(f"Converting {downloaded_file} to XLSX...")
        # Fixed typo: download_file → downloaded_file
        df = pd.read_csv(downloaded_file)
        new_filename = f"{file_name}.xlsx"
        new_filepath = os.path.join(REPO_PATH, new_filename)
        df.to_excel(new_filepath, index=False)
        os.remove(downloaded_file)
        logger.info(f"File converted and saved to: {new_filepath}")
        return new_filename

    except TimeoutException:
        logger.error(f"Timeout waiting for CSV button on {page_name} page.")
        take_screenshot(driver, f"{page_name}_timeout.png")
        logger.debug(f"Page source: {driver.page_source[:1000]}...")
    except Exception as e:
        logger.error(f"Error processing {page_name}: {str(e)}")
        take_screenshot(driver, f"{page_name}_error.png")
    return None

def push_to_git(repo_path, files):
    try:
        repo = git.Repo(repo_path)
        logger.info("Discarding all local changes...")
        repo.git.reset('--hard')
        repo.git.clean('-fd')

        logger.info(f"Pulling latest changes from {REPO_REMOTE}/{REPO_BRANCH}...")
        repo.remotes[REPO_REMOTE].pull()

        logger.info("Removing existing XLSX files...")
        for file in os.listdir(repo_path):
            if file.endswith('.xlsx'):
                file_path = os.path.join(repo_path, file)
                os.remove(file_path)
                repo.git.add(file_path)
                logger.info(f"Removed and staged: {file}")

        for file in files:
            src = os.path.join(REPO_PATH, file)
            repo.git.add(src)
            logger.info(f"Staged new file: {file}")

        if repo.is_dirty():
            commit_message = f"Update XLSX files - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            repo.index.commit(commit_message)
            logger.info(f"Committed changes: {commit_message}")
            repo.remotes[REPO_REMOTE].push()
            logger.info("Pushed changes to repository.")
        else:
            logger.info("No changes to commit.")

    except Exception as e:
        logger.error(f"Git operation failed: {str(e)}")
        raise

def run_csv_download_job():
    """
    Run the CSV download, conversion, and Git push job.
    Returns a dictionary with status and results.
    """
    result = {"status": "success", "message": "", "files": []}
    driver = None
    try:
        driver = setup_driver(headless=False)  # Non-headless for manual pop-up handling

        logger.info("Navigating to login page...")
        driver.get("https://backend.bodabodaunion.ug/admin")
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        logger.info("Entering credentials...")
        username_field = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='data[User][username]']"))
        )
        username_field.clear()
        username_field.send_keys(USERNAME)

        password_field = WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='data[User][password]']"))
        )
        password_field.clear()
        password_field.send_keys(PASSWORD)

        login_button = WebDriverWait(driver, WAIT_TIME).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        login_button.click()

        WebDriverWait(driver, WAIT_TIME).until(EC.url_contains("/admin"))
        if "login" in driver.current_url.lower():
            logger.error("Login failed: Still on login page.")
            take_screenshot(driver, "login_failed.png")
            raise Exception("Login failed.")

        logger.info("Login successful.")

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
                logger.info(f"Processed {page_name}: {file_path}")
            else:
                logger.warning(f"Failed to process {page_name}")

        if xlsx_files:
            logger.info("Files processed:")
            for file in xlsx_files:
                logger.info(f"- {os.path.join(REPO_PATH, file)}")
            push_to_git(REPO_PATH, xlsx_files)
            result["files"] = xlsx_files
            result["message"] = f"Successfully processed {len(xlsx_files)} files."
        else:
            result["status"] = "warning"
            result["message"] = "No files were processed."

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Job failed: {str(e)}"
        logger.error(f"Job failed: {str(e)}")
        take_screenshot(driver, "error.png")
    finally:
        if driver:
            driver.quit()
            logger.info("Browser closed.")
    return result



# Load environment variables
load_dotenv()
OPENCAGE_API_KEY = os.getenv('OPENCAGE_API_KEY')

# Configure page
st.set_page_config(
    page_title="Union App Metrics Dashboard",
    page_icon=r"./TUTU.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for the dashboard
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stMetric label, .stMetric div {
        color: black !important;
    }
    .stPlotlyChart, .stPydeckChart {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

PASSENGERS_FILE_PATH = r"./PASSENGERS.xlsx"
DRIVERS_FILE_PATH = r"./DRIVERS.xlsx"
DATA_FILE_PATH = r"./BEER.xlsx"
TRANSACTIONS_FILE_PATH = r"./TRANSACTIONS.xlsx"
UNION_STAFF_FILE_PATH = r"./UNION STAFF.xlsx"

# Enhanced function to extract UGX amounts from any column
def extract_ugx_amount(value):
    try:
        if pd.isna(value) or value is None:
            return 0.0
        # Convert to string and clean
        value_str = str(value).replace('UGX', '').replace(',', '').strip()
        # Extract numeric part using regex
        amounts = re.findall(r'[\d]+(?:\.\d+)?', value_str)
        if amounts:
            return float(amounts[0])
        # Try direct conversion if it's a numeric string
        if value_str.replace('.', '').isdigit():
            return float(value_str)
        return 0.0
    except (ValueError, TypeError):
        return 0.0

# Function to load passengers data with date filtering
def load_passengers_data(date_range=None):
    try:
        df = pd.read_excel(PASSENGERS_FILE_PATH)
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        if 'Wallet Balance' in df.columns:
            df['Wallet Balance'] = df['Wallet Balance'].apply(extract_ugx_amount)

        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['Created'].dt.date >= start_date) &
                    (df['Created'].dt.date <= end_date)]
        return df
    except Exception as e:
        st.error(f"Error loading passengers data: {str(e)}")
        return pd.DataFrame()

# Function to load drivers data with date filtering
def load_drivers_data(date_range=None):
    try:
        df = pd.read_excel(DRIVERS_FILE_PATH)
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        if 'Wallet Balance' in df.columns:
            df['Wallet Balance'] = df['Wallet Balance'].apply(extract_ugx_amount)
        return df
    except Exception as e:
        st.error(f"Error loading drivers data: {str(e)}")
        return pd.DataFrame()

# Function to load and merge transactions data
def load_transactions_data():
    try:
        transactions_df = pd.read_excel(TRANSACTIONS_FILE_PATH)
        
        if 'Company Amt (UGX)' in transactions_df.columns:
            transactions_df['Company Commission Cleaned'] = transactions_df['Company Amt (UGX)'].apply(extract_ugx_amount)
        else:
            st.warning("No 'Company Amt (UGX)' column found in transactions data")
            transactions_df['Company Commission Cleaned'] = 0.0
            
        if 'Pay Mode' in transactions_df.columns:
            transactions_df['Pay Mode'] = transactions_df['Pay Mode'].fillna('Unknown')
        else:
            st.warning("No 'Pay Mode' column found in transactions data")
            transactions_df['Pay Mode'] = 'Unknown'
            
        return transactions_df[['Company Commission Cleaned', 'Pay Mode']]
    except Exception as e:
        st.error(f"Error loading transactions data: {str(e)}")
        return pd.DataFrame()

def load_data():
    try:
        df = pd.read_excel(DATA_FILE_PATH)
        
        transactions_df = load_transactions_data()
        if not transactions_df.empty:
            if 'Company Commission Cleaned' in df.columns and 'Company Commission Cleaned' in transactions_df.columns:
                df['Company Commission Cleaned'] += transactions_df['Company Commission Cleaned']
            elif 'Company Commission Cleaned' not in df.columns:
                df['Company Commission Cleaned'] = transactions_df['Company Commission Cleaned']
                
            if 'Pay Mode' not in df.columns:
                df['Pay Mode'] = transactions_df['Pay Mode']

        df['Trip Date'] = pd.to_datetime(df['Trip Date'], errors='coerce')
        df['Trip Hour'] = df['Trip Date'].dt.hour
        df['Day of Week'] = df['Trip Date'].dt.day_name()
        df['Month'] = df['Trip Date'].dt.month_name()

        if 'Trip Pay Amount' in df.columns:
            df['Trip Pay Amount Cleaned'] = df['Trip Pay Amount'].apply(extract_ugx_amount)
        else:
            st.warning("No 'Trip Pay Amount' column found - creating placeholder")
            df['Trip Pay Amount Cleaned'] = 0.0

        df['Distance'] = pd.to_numeric(df['Trip Distance (KM/Mi)'], errors='coerce').fillna(0)

        if 'Company Commission Cleaned' not in df.columns:
            st.warning("No company commission data found - creating placeholder")
            df['Company Commission Cleaned'] = 0.0

        if 'Pay Mode' not in df.columns:
            st.warning("No 'Pay Mode' column found - adding placeholder")
            df['Pay Mode'] = 'Unknown'

        return df

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# Define metrics functions
def passenger_metrics(df_passengers):
    try:
        app_downloads = len(df_passengers) if not df_passengers.empty else 0
        passenger_wallet_balance = float(df_passengers['Wallet Balance'].sum()) if 'Wallet Balance' in df_passengers.columns else 0.0
        return app_downloads, passenger_wallet_balance
    except Exception as e:
        st.error(f"Error in passenger metrics: {str(e)}")
        return 0, 0.0

def driver_metrics(df_drivers):
    try:
        riders_onboarded = len(df_drivers) if not df_drivers.empty else 0
        if 'Wallet Balance' in df_drivers.columns:
            # Sum positive values for Driver Wallet Balance
            driver_wallet_balance = float(df_drivers[df_drivers['Wallet Balance'] > 0]['Wallet Balance'].sum())
            # Sum absolute of negative values for Commission Owed
            commission_owed = float(df_drivers[df_drivers['Wallet Balance'] < 0]['Wallet Balance'].abs().sum())
        else:
            driver_wallet_balance = 0.0
            commission_owed = 0.0
        return riders_onboarded, driver_wallet_balance, commission_owed
    except Exception as e:
        st.error(f"Error in driver metrics: {str(e)}")
        return 0, 0.0, 0.0

def calculate_driver_retention_rate(riders_onboarded, app_downloads, unique_drivers):
    try:
        retention_rate = (unique_drivers / riders_onboarded * 100) if riders_onboarded > 0 else 0.0
        passenger_ratio = (app_downloads / unique_drivers) if unique_drivers > 0 else 0.0
        return float(retention_rate), float(passenger_ratio)
    except Exception as e:
        st.error(f"Error calculating retention rate: {str(e)}")
        return 0.0, 0.0

# Define other required functions
def calculate_cancellation_rate(df):
    try:
        if 'Trip Status' not in df.columns:
            return None
        total_trips = len(df)
        cancelled_trips = len(df[df['Trip Status'].str.contains('Cancel', case=False, na=False)])
        return (cancelled_trips / total_trips * 100) if total_trips > 0 else 0.0
    except:
        return None

def calculate_passenger_search_timeout(df):
    try:
        if 'Trip Status' not in df.columns:
            return None
        total_trips = len(df)
        expired_trips = len(df[df['Trip Status'].str.lower() == 'expired'])
        return (expired_trips / total_trips * 100) if total_trips > 0 else 0.0
    except:
        return None

def completed_vs_cancelled_daily(df):
    try:
        if 'Trip Status' not in df.columns or 'Trip Date' not in df.columns:
            return None
        status_df = df.groupby([df['Trip Date'].dt.date, 'Trip Status']).size().unstack(fill_value=0)
        fig = go.Figure()
        for status in status_df.columns:
            fig.add_trace(go.Bar(
                x=status_df.index,
                y=status_df[status],
                name=status
            ))
        fig.update_layout(
            title="Daily Trip Status Breakdown",
            xaxis_title="Date",
            yaxis_title="Number of Trips",
            barmode='stack',
            template="plotly_white"
        )
        return fig
    except:
        return None

def trips_per_driver(df):
    try:
        if 'Driver' not in df.columns:
            st.metric("Trips per Driver", "N/A")
            return
        trips_by_driver = df.groupby('Driver').size()
        avg_trips = trips_by_driver.mean() if not trips_by_driver.empty else 0
        st.metric("Avg. Trips per Driver", f"{avg_trips:.1f}")
    except Exception as e:
        st.error(f"Error in trips per driver: {str(e)}")

def total_trips_by_status(df):
    try:
        if 'Trip Status' not in df.columns:
            return
        status_counts = df['Trip Status'].value_counts()
        fig = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Trip Status Distribution"
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in total trips by status: {str(e)}")
        return None

def total_distance_covered(df):
    try:
        if 'Distance' not in df.columns or 'Trip Status' not in df.columns:
            return
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        total_distance = completed_trips['Distance'].sum()
        st.metric("Total Distance Covered", f"{total_distance:,.0f} km")
    except Exception as e:
        st.error(f"Error in total distance covered: {str(e)}")

def revenue_by_day(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Trip Date' not in df.columns:
            return
        daily_revenue = df.groupby(df['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].sum()
        fig = px.line(
            x=daily_revenue.index,
            y=daily_revenue.values,
            title="Daily Revenue Trend",
            labels={'x': 'Date', 'y': 'Revenue (UGX)'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in revenue by day: {str(e)}")
        return None

def avg_revenue_per_trip(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns:
            return
        avg_revenue = df['Trip Pay Amount Cleaned'].mean()
        st.metric("Avg. Revenue per Trip", f"{avg_revenue:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in avg revenue per trip: {str(e)}")

def total_commission(df):
    try:
        if 'Company Commission Cleaned' not in df.columns:
            st.metric("Total Commission", "N/A")
            return
        total_comm = df['Company Commission Cleaned'].sum()
        st.metric("Total Commission", f"{total_comm:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in total commission: {str(e)}")

def gross_profit(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            return
        gross_profit = df['Company Commission Cleaned'].sum()
        st.metric("Gross Profit", f"{gross_profit:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in gross profit: {str(e)}")

def avg_commission_per_trip(df):
    try:
        if 'Company Commission Cleaned' not in df.columns:
            return
        avg_comm = df['Company Commission Cleaned'].mean()
        st.metric("Avg. Commission per Trip", f"{avg_comm:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in avg commission per trip: {str(e)}")

def revenue_per_driver(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return
        revenue_by_driver = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum()
        avg_revenue = revenue_by_driver.mean() if not revenue_by_driver.empty else 0
        st.metric("Avg. Revenue per Driver", f"{avg_revenue:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in revenue per driver: {str(e)}")

def driver_earnings_per_trip(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            return
        df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
        avg_earnings = df['Driver Earnings'].mean()
        st.metric("Avg. Driver Earnings per Trip", f"{avg_earnings:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in driver earnings per trip: {str(e)}")

def fare_per_km(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Distance' not in df.columns or 'Trip Status' not in df.columns:
            return
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        completed_trips['Fare per KM'] = completed_trips['Trip Pay Amount Cleaned'] / completed_trips['Distance'].replace(0, 1)
        avg_fare_per_km = completed_trips['Fare per KM'].mean()
        st.metric("Avg. Fare per KM", f"{avg_fare_per_km:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in fare per km: {str(e)}")

def revenue_share(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            return
        total_revenue = df['Trip Pay Amount Cleaned'].sum()
        total_commission = df['Company Commission Cleaned'].sum()
        revenue_share = (total_commission / total_revenue * 100) if total_revenue > 0 else 0
        st.metric("Revenue Share", f"{revenue_share:.1f}%")
    except Exception as e:
        st.error(f"Error in revenue share: {str(e)}")

def total_trips_by_type(df):
    try:
        if 'Trip Type' not in df.columns:
            return
        type_counts = df['Trip Type'].value_counts()
        fig = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            title="Trips by Type"
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in total trips by type: {str(e)}")
        return None

def payment_method_revenue(df):
    try:
        if 'Pay Mode' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return
        revenue_by_payment = df.groupby('Pay Mode')['Trip Pay Amount Cleaned'].sum()
        fig = px.pie(
            values=revenue_by_payment.values,
            names=revenue_by_payment.index,
            title="Revenue by Payment Method"
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in payment method revenue: {str(e)}")
        return None

def distance_vs_revenue_scatter(df):
    try:
        if 'Distance' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return
        fig = px.scatter(
            df,
            x='Distance',
            y='Trip Pay Amount Cleaned',
            title="Distance vs Revenue",
            labels={'Distance': 'Distance (km)', 'Trip Pay Amount Cleaned': 'Revenue (UGX)'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in distance vs revenue scatter: {str(e)}")
        return None

def weekday_vs_weekend_analysis(df):
    try:
        if 'Day of Week' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return
        df['Is Weekend'] = df['Day of Week'].isin(['Saturday', 'Sunday'])
        revenue_by_period = df.groupby('Is Weekend')['Trip Pay Amount Cleaned'].sum()
        fig = px.bar(
            x=['Weekday', 'Weekend'],
            y=revenue_by_period.values,
            title="Weekday vs Weekend Revenue",
            labels={'x': 'Period', 'y': 'Revenue (UGX)'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in weekday vs weekend analysis: {str(e)}")
        return None

def unique_driver_count(df):
    try:
        if 'Driver' not in df.columns:
            return
        unique_drivers = df['Driver'].nunique()
        st.metric("Unique Drivers", unique_drivers)
    except Exception as e:
        st.error(f"Error in unique driver count: {str(e)}")

def top_drivers_by_revenue(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return
        top_drivers = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().nlargest(5)
        fig = px.bar(
            x=top_drivers.values,
            y=top_drivers.index,
            orientation='h',
            title="Top 5 Drivers by Revenue",
            labels={'x': 'Revenue (UGX)', 'y': 'Driver'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in top drivers by revenue: {str(e)}")
        return None

def driver_performance_comparison(df):
    try:
        if 'Driver' not in df.columns:
            return
        driver_stats = df.groupby('Driver').agg({
            'Id': 'count',
            'Trip Pay Amount Cleaned': 'sum',
            'Distance': 'sum'
        }).rename(columns={'Id': 'Trip Count'})
        fig = px.scatter(
            driver_stats,
            x='Trip Count',
            y='Trip Pay Amount Cleaned',
            size='Distance',
            hover_name=driver_stats.index,
            title="Driver Performance Comparison",
            labels={'Trip Count': 'Number of Trips', 'Trip Pay Amount Cleaned': 'Revenue (UGX)'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in driver performance comparison: {str(e)}")
        return None

def passenger_insights(df):
    try:
        if 'Passenger' not in df.columns:
            return
        passenger_trips = df.groupby('Passenger').size().value_counts()
        fig = px.bar(
            x=passenger_trips.index,
            y=passenger_trips.values,
            title="Passenger Trip Frequency",
            labels={'x': 'Number of Trips', 'y': 'Number of Passengers'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in passenger insights: {str(e)}")
        return None

def top_10_drivers_by_earnings(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            return
        df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
        top_drivers = df.groupby('Driver')['Driver Earnings'].sum().nlargest(10)
        fig = px.bar(
            x=top_drivers.values,
            y=top_drivers.index,
            orientation='h',
            title="Top 10 Drivers by Earnings",
            labels={'x': 'Earnings (UGX)', 'y': 'Driver'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in top 10 drivers by earnings: {str(e)}")
        return None

def get_completed_trips_by_union_passengers(df, union_staff_names):
    try:
        if 'Passenger' not in df.columns or 'Trip Status' not in df.columns:
            return pd.DataFrame()
        staff_trips = df[
            (df['Passenger'].isin(union_staff_names)) &
            (df['Trip Status'] == 'Job Completed')
        ][['Passenger', 'Trip Date', 'Trip Pay Amount Cleaned', 'Distance']]
        return staff_trips
    except Exception as e:
        st.error(f"Error in get completed trips by union passengers: {str(e)}")
        return pd.DataFrame()

def most_frequent_locations(df):
    try:
        if 'Pickup Location' not in df.columns or 'Dropoff Location' not in df.columns:
            return
        pickup_counts = df['Pickup Location'].value_counts().head(5)
        dropoff_counts = df['Dropoff Location'].value_counts().head(5)
        col1, col2 = st.columns(2)
        with col1:
            fig1 = px.bar(
                x=pickup_counts.values,
                y=pickup_counts.index,
                orientation='h',
                title="Top 5 Pickup Locations",
                labels={'x': 'Number of Trips', 'y': 'Location'}
            )
            st.plotly_chart(fig1, use_container_width=True)
            return fig1  # Return the figure for PDF
        with col2:
            fig2 = px.bar(
                x=dropoff_counts.values,
                y=dropoff_counts.index,
                orientation='h',
                title="Top 5 Dropoff Locations",
                labels={'x': 'Number of Trips', 'y': 'Location'}
            )
            st.plotly_chart(fig2, use_container_width=True)
            return fig2  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in most frequent locations: {str(e)}")
        return None, None

def peak_hours(df):
    try:
        if 'Trip Hour' not in df.columns:
            return
        hour_counts = df['Trip Hour'].value_counts().sort_index()
        fig = px.bar(
            x=hour_counts.index,
            y=hour_counts.values,
            title="Trip Distribution by Hour",
            labels={'x': 'Hour of Day', 'y': 'Number of Trips'}
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in peak hours: {str(e)}")
        return None

def trip_status_trends(df):
    try:
        if 'Trip Status' not in df.columns or 'Trip Date' not in df.columns:
            return
        status_trends = df.groupby([df['Trip Date'].dt.date, 'Trip Status']).size().unstack(fill_value=0)
        fig = go.Figure()
        for status in status_trends.columns:
            fig.add_trace(go.Scatter(
                x=status_trends.index,
                y=status_trends[status],
                name=status,
                mode='lines+markers'
            ))
        fig.update_layout(
            title="Trip Status Trends Over Time",
            xaxis_title="Date",
            yaxis_title="Number of Trips",
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in trip status trends: {str(e)}")
        return None

def customer_payment_methods(df):
    try:
        if 'Pay Mode' not in df.columns:
            return
        payment_counts = df['Pay Mode'].value_counts()
        fig = px.pie(
            values=payment_counts.values,
            names=payment_counts.index,
            title="Customer Payment Methods"
        )
        st.plotly_chart(fig, use_container_width=True)
        return fig  # Return the figure for PDF
    except Exception as e:
        st.error(f"Error in customer payment methods: {str(e)}")
        return None

def get_download_data(df):
    try:
        download_df = df[['Trip Date', 'Trip Status', 'Driver', 'Passenger', 'Trip Pay Amount Cleaned', 'Company Commission Cleaned', 'Distance', 'Pay Mode']].copy()
        download_df['Trip Date'] = download_df['Trip Date'].dt.strftime('%Y-%m-%d')
        return download_df
    except Exception as e:
        st.error(f"Error in get download data: {str(e)}")
        return pd.DataFrame()

def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed):
    try:
        class PDF(FPDF):
            def header(self):
                self.set_font('Arial', 'B', 12)
                # Add TUTU.png as header image
                if os.path.exists(r"./TUTU.png"):
                    self.image(r"./TUTU.png", 10, 8, 33)  # x, y, width in mm
                self.cell(0, 10, 'Union App Metrics Report', 0, 1, 'C')
                self.ln(10)

            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        pdf = PDF()
        pdf.add_page()
        pdf.set_font('Arial', '', 12)

        # Convert date_range to strings, handling invalid or missing dates
        start_date_str = 'N/A'
        end_date_str = 'N/A'
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            try:
                start_date_str = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
                end_date_str = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)
            except (AttributeError, TypeError):
                pass

        pdf.cell(0, 10, f"Date Range: {start_date_str} to {end_date_str}", 0, 1)
        pdf.ln(5)

        # Section: Overview Metrics
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Overview Metrics", 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.ln(5)
        pdf.multi_cell(0, 10, "This section provides a snapshot of trip activity and user engagement.")
        pdf.ln(5)

        total_trips = int(len(df))
        completed_trips = int(len(df[df['Trip Status'] == 'Job Completed'])) if 'Trip Status' in df.columns else 0
        total_revenue = float(df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum()) if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else 0.0
        total_distance = float(df[df['Trip Status'] == 'Job Completed']['Distance'].sum()) if 'Distance' in df.columns and 'Trip Status' in df.columns else 0.0
        cancellation_rate = calculate_cancellation_rate(df) if calculate_cancellation_rate(df) is not None else 0.0
        timeout_rate = calculate_passenger_search_timeout(df) if calculate_passenger_search_timeout(df) is not None else 0.0
        avg_trips = trips_per_driver(df) if 'Driver' in df.columns else "N/A"
        app_downloads = int(app_downloads) if app_downloads is not None else 0
        riders_onboarded = int(riders_onboarded) if riders_onboarded is not None else 0

        pdf.cell(0, 10, f"Total Requests: {total_trips}", 0, 1)
        pdf.cell(0, 10, f"Completed Trips: {completed_trips}", 0, 1)
        pdf.cell(0, 10, f"Total Revenue: {total_revenue:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Total Distance Covered: {total_distance:,.0f} km", 0, 1)
        pdf.cell(0, 10, f"Driver Cancellation Rate: {cancellation_rate:.1f}%", 0, 1)
        pdf.cell(0, 10, f"Passenger Search Timeout: {timeout_rate:.1f}%", 0, 1)
        pdf.cell(0, 10, f"Avg. Trips per Driver: {avg_trips if isinstance(avg_trips, str) else f'{avg_trips:.1f}'}", 0, 1)
        pdf.cell(0, 10, f"Passenger App Downloads: {app_downloads}", 0, 1)
        pdf.cell(0, 10, f"Riders Onboarded: {riders_onboarded}", 0, 1)
        pdf.ln(10)

        # Add visualizations
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Visualizations", 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.ln(5)
        pdf.multi_cell(0, 10, "The following charts provide visual insights into trip status, revenue trends, and more.")
        pdf.ln(5)

        # Generate and add images of charts
        charts = {
            "Trip Status Distribution": total_trips_by_status(df),
            "Daily Revenue Trend": revenue_by_day(df),
            "Trips by Type": total_trips_by_type(df),
            "Revenue by Payment Method": payment_method_revenue(df),
            "Distance vs Revenue": distance_vs_revenue_scatter(df),
            "Weekday vs Weekend Revenue": weekday_vs_weekend_analysis(df),
            "Top 5 Drivers by Revenue": top_drivers_by_revenue(df),
            "Driver Performance Comparison": driver_performance_comparison(df),
            "Passenger Trip Frequency": passenger_insights(df),
            "Top 10 Drivers by Earnings": top_10_drivers_by_earnings(df),
            "Top 5 Pickup Locations": most_frequent_locations(df)[0] if most_frequent_locations(df)[0] else None,
            "Top 5 Dropoff Locations": most_frequent_locations(df)[1] if most_frequent_locations(df)[1] else None,
            "Trip Distribution by Hour": peak_hours(df),
            "Trip Status Trends": trip_status_trends(df),
            "Customer Payment Methods": customer_payment_methods(df)
        }

        for title, fig in charts.items():
            if fig is not None:
                img_data = to_image(fig, format='png', width=400, height=300)
                pdf.ln(5)
                pdf.set_font('Arial', 'B', 12)
                pdf.cell(0, 10, title, 0, 1)
                pdf.set_font('Arial', '', 12)
                pdf.multi_cell(0, 10, f"Explanation: This chart illustrates {title.lower().replace('vs', 'versus').replace('top', 'the top').replace('by', 'by').replace('distribution', 'distribution of data').replace('trends', 'trends over time')}.")
                pdf.image(io.BytesIO(img_data), x=10, y=None, w=180)
                pdf.ln(10)

        # Section: Financial Metrics
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Financial Metrics", 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.ln(5)
        pdf.multi_cell(0, 10, "This section details the financial performance of the Union App.")
        pdf.ln(5)

        total_revenue = float(df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum()) if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else 0.0
        total_comm = float(df['Company Commission Cleaned'].sum()) if 'Company Commission Cleaned' in df.columns else 0.0
        gross_profit_val = total_comm
        passenger_wallet_balance = float(passenger_wallet_balance) if passenger_wallet_balance is not None else 0.0
        driver_wallet_balance = float(driver_wallet_balance) if driver_wallet_balance is not None else 0.0
        commission_owed = float(commission_owed) if commission_owed is not None else 0.0
        avg_comm = float(df['Company Commission Cleaned'].mean()) if 'Company Commission Cleaned' in df.columns else 0.0
        revenue_per_driver_val = float(df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().mean()) if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns else 0.0
        driver_earnings = float((df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']).mean()) if 'Trip Pay Amount Cleaned' in df.columns and 'Company Commission Cleaned' in df.columns else 0.0
        fare_per_km_val = float(df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum() / df[df['Trip Status'] == 'Job Completed']['Distance'].replace(0, 1).sum()) if 'Trip Pay Amount Cleaned' in df.columns and 'Distance' in df.columns and 'Trip Status' in df.columns else 0.0
        revenue_share_val = (total_comm / total_revenue * 100) if total_revenue > 0 else 0

        pdf.cell(0, 10, f"Total Value of Rides: {total_revenue:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Total Commission: {total_comm:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Gross Profit: {gross_profit_val:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Passenger Wallet Balance: {passenger_wallet_balance:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Driver Wallet Balance: {driver_wallet_balance:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Commission Owed: {commission_owed:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Commission per Trip: {avg_comm:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Revenue per Driver: {revenue_per_driver_val:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Driver Earnings per Trip: {driver_earnings:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Fare per KM: {fare_per_km_val:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Revenue Share: {revenue_share_val:.1f}%", 0, 1)
        pdf.ln(10)

        # Section: User Metrics
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "User Metrics", 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.ln(5)
        pdf.multi_cell(0, 10, "This section analyzes user engagement and performance metrics.")
        pdf.ln(5)

        unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
        retention_rate = float(retention_rate) if retention_rate is not None else 0.0
        passenger_ratio = float(passenger_ratio) if passenger_ratio is not None else 0.0

        pdf.cell(0, 10, f"Unique Drivers: {unique_drivers}", 0, 1)
        pdf.cell(0, 10, f"Passenger App Downloads: {app_downloads}", 0, 1)
        pdf.cell(0, 10, f"Riders Onboarded: {riders_onboarded}", 0, 1)
        pdf.cell(0, 10, f"Driver Retention Rate: {retention_rate:.1f}%", 0, 1)
        pdf.cell(0, 10, f"Passenger-to-Driver Ratio: {passenger_ratio:.1f}", 0, 1)
        pdf.ln(10)

        return pdf
    except Exception as e:
        st.error(f"Error in create metrics pdf: {str(e)}")
        return PDF()

def main():
    st.title("Union App Metrics Dashboard")

    try:
        st.cache_data.clear()

        min_date = datetime(2023, 1, 1).date()
        max_date = datetime.now().date()

        try:
            df = load_data()
            if not df.empty and 'Trip Date' in df.columns:
                min_date = df['Trip Date'].min().date()
                max_date = df['Trip Date'].max().date()
        except:
            pass

        date_range = st.sidebar.date_input(
            "Date Range",
            value=[min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )

        df = load_data()
        if len(date_range) == 2:
            df = df[(df['Trip Date'].dt.date >= date_range[0]) &
                    (df['Trip Date'].dt.date <= date_range[1])]

        df_passengers = load_passengers_data(date_range)
        df_drivers = load_drivers_data(date_range)

        if df.empty:
            st.error("No data loaded - please check the backend data file")
            return

        if 'Trip Date' not in df.columns:
            st.error("No 'Trip Date' column found in the data")
            return

        app_downloads, passenger_wallet_balance = passenger_metrics(df_passengers)
        riders_onboarded, driver_wallet_balance, commission_owed = driver_metrics(df_drivers)

        unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
        retention_rate, passenger_ratio = calculate_driver_retention_rate(
            riders_onboarded, app_downloads, unique_drivers
        )

        st.sidebar.markdown("---")
        st.sidebar.subheader("Export Data")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            get_download_data(df).to_excel(writer, sheet_name='Dashboard Data', index=False)
        excel_data = output.getvalue()
        st.sidebar.download_button(
            label="📊 Download Full Data (Excel)",
            data=excel_data,
            file_name=f"union_app_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        pdf = create_metrics_pdf(df, date_range, retention_rate, passenger_ratio,
                                 app_downloads, riders_onboarded, passenger_wallet_balance,
                                 driver_wallet_balance, commission_owed)
        pdf_output = pdf.output(dest='S').encode('latin1')
        st.sidebar.download_button(
            label="📄 Download Metrics Report (PDF)",
            data=pdf_output,
            file_name=f"union_app_metrics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )

        tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Financial", "User Analysis", "Geographic"])

        with tab1:
            st.header("Trips Overview")

            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Requests", len(df))
            with col2:
                completed_trips = len(df[df['Trip Status'] == 'Job Completed'])
                st.metric("Completed Trips", completed_trips)
            with col3:
                st.metric("Avg. Distance", f"{df['Distance'].mean():.1f} km" if 'Distance' in df.columns else "N/A")
            with col4:
                cancellation_rate = calculate_cancellation_rate(df)
                if cancellation_rate is not None:
                    st.metric("Driver Cancellation Rate", f"{cancellation_rate:.1f}%")
                else:
                    st.metric("Driver Cancellation Rate", "N/A")
            with col5:
                timeout_rate = calculate_passenger_search_timeout(df)
                if timeout_rate is not None:
                    st.metric("Passenger Search Timeout", f"{timeout_rate:.1f}%")
                else:
                    st.metric("Passenger Search Timeout", "N/A")

            status_breakdown_fig = completed_vs_cancelled_daily(df)
            if status_breakdown_fig:
                st.plotly_chart(status_breakdown_fig, use_container_width=True)
            else:
                st.warning("Could not generate trip status breakdown chart - missing required data")

            col6, col7, col8 = st.columns(3)
            with col6:
                trips_per_driver(df)
            with col7:
                st.metric("Passenger App Downloads", app_downloads)
            with col8:
                st.metric("Riders Onboarded", riders_onboarded)

            total_trips_by_status(df)
            total_distance_covered(df)
            revenue_by_day(df)
            avg_revenue_per_trip(df)
            total_commission(df)

        with tab2:
            st.header("Financial Performance")

            col1, col2, col3 = st.columns(3)
            with col1:
                total_revenue = df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum()
                st.metric("Total Value Of Rides", f"{total_revenue:,.0f} UGX")
            with col2:
                total_commission(df)
            with col3:
                gross_profit(df)

            col4, col5, col6 = st.columns(3)
            with col4:
                st.metric("Passenger Wallet Balance", f"{passenger_wallet_balance:,.0f} UGX")
            with col5:
                st.metric("Driver Wallet Balance", f"{driver_wallet_balance:,.0f} UGX")
            with col6:
                st.metric("Commission Owed", f"{commission_owed:,.0f} UGX")

            col7, col8, col9 = st.columns(3)
            with col7:
                avg_commission_per_trip(df)
            with col8:
                revenue_per_driver(df)
            with col9:
                driver_earnings_per_trip(df)

            col10, col11 = st.columns(2)
            with col10:
                fare_per_km(df)
            with col11:
                revenue_share(df)

            total_trips_by_type(df)
            payment_method_revenue(df)
            distance_vs_revenue_scatter(df)
            weekday_vs_weekend_analysis(df)

        with tab3:
            st.header("User Performance")

            col1, col2, col3 = st.columns(3)
            with col1:
                unique_driver_count(df)
            with col2:
                st.metric("Passenger App Downloads", app_downloads)
            with col3:
                st.metric("Riders Onboarded", riders_onboarded)

            col4, col5 = st.columns(2)
            with col4:
                st.metric("Driver Retention Rate", f"{retention_rate:.1f}%",
                          help="Percentage of onboarded riders who are active drivers")
            with col5:
                st.metric("Passenger-to-Driver Ratio", f"{passenger_ratio:.1f}",
                          help="Number of passengers per active driver")

            top_drivers_by_revenue(df)
            driver_performance_comparison(df)
            passenger_insights(df)
            top_10_drivers_by_earnings(df)

            st.markdown("---")
            st.subheader("Union Staff Trip Completion")

            try:
                if os.path.exists(UNION_STAFF_FILE_PATH):
                    union_staff_df = pd.read_excel(UNION_STAFF_FILE_PATH)
                    if union_staff_df.empty or union_staff_df.shape[1] == 0:
                        st.warning("Union Staff file is empty or does not contain columns.")
                    else:
                        union_staff_names = union_staff_df.iloc[:, 0].dropna().astype(str).tolist()
                        st.metric("Total Union's Staff Members", len(union_staff_names))

                        staff_trips_df = get_completed_trips_by_union_passengers(df, union_staff_names)
                        if not staff_trips_df.empty:
                            st.dataframe(staff_trips_df)
                        else:
                            st.info("No matching completed trips found for Union Staff members.")
                else:
                    st.info(f"Union Staff file not found at: {UNION_STAFF_FILE_PATH}")

            except Exception as e:
                st.error(f"Error processing Union Staff file: {e}")

        with tab4:
            st.header("Geographic Analysis")
            most_frequent_locations(df)
            peak_hours(df)
            trip_status_trends(df)
            customer_payment_methods(df)

    except FileNotFoundError:
        st.error("Data file not found. Please ensure the Excel file is placed in the data/ directory.")
    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    main()
