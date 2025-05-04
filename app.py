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

# Load environment variables
load_dotenv()
OPENCAGE_API_KEY = os.getenv('OPENCAGE_API_KEY')

# Configure page
st.set_page_config(
    page_title="Union App Metrics Dashboard",
    page_icon=r"./your_image.png",
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

# Function to extract UGX amounts from any column
def extract_ugx_amount(value):
    try:
        if pd.isna(value):
            return 0.0
        # Handle both "UGX1000" and "UGX 1,000" formats
        amounts = re.findall(r'UGX\s*([\d,]+)', str(value))
        if amounts:
            return sum(float(amount.replace(',', '')) for amount in amounts)
        return float(str(value).replace(',', '')) if str(value).replace(',', '').isdigit() else 0.0
    except:
        return 0.0

# Function to load passengers data with date filtering
def load_passengers_data(date_range=None):
    try:
        df = pd.read_excel(PASSENGERS_FILE_PATH)
        df['Created Time'] = pd.to_datetime(df['Created Time'], errors='coerce')

        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['Created Time'].dt.date >= start_date) &
                    (df['Created Time'].dt.date <= end_date)]
        return df
    except Exception as e:
        st.error(f"Error loading passengers data: {str(e)}")
        return pd.DataFrame()

# Function to load drivers data with date filtering
def load_drivers_data(date_range=None):
    try:
        df = pd.read_excel(DRIVERS_FILE_PATH)
        df['Created Time'] = pd.to_datetime(df['Created Time'], errors='coerce')

        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['Created Time'].dt.date >= start_date) &
                    (df['Created Time'].dt.date <= end_date)]
        return df
    except Exception as e:
        st.error(f"Error loading drivers data: {str(e)}")
        return pd.DataFrame()

# Function to load and merge transactions data
def load_transactions_data():
    try:
        transactions_df = pd.read_excel(TRANSACTIONS_FILE_PATH)
        
        # Process Company Amt (UGX)
        if 'Company Amt (UGX)' in transactions_df.columns:
            transactions_df['Company Commission Cleaned'] = transactions_df['Company Amt (UGX)'].apply(extract_ugx_amount)
        else:
            st.warning("No 'Company Amt (UGX)' column found in transactions data")
            transactions_df['Company Commission Cleaned'] = 0.0
            
        # Process Pay Mode
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
        # Load main data
        df = pd.read_excel(DATA_FILE_PATH)
        
        # Load and merge transactions data
        transactions_df = load_transactions_data()
        if not transactions_df.empty:
            # Merge transactions data with main data
            if 'Company Commission Cleaned' in df.columns and 'Company Commission Cleaned' in transactions_df.columns:
                df['Company Commission Cleaned'] += transactions_df['Company Commission Cleaned']
            elif 'Company Commission Cleaned' not in df.columns:
                df['Company Commission Cleaned'] = transactions_df['Company Commission Cleaned']
                
            if 'Pay Mode' not in df.columns:
                df['Pay Mode'] = transactions_df['Pay Mode']

        # Data cleaning
        df['Trip Date'] = pd.to_datetime(df['Trip Date'], errors='coerce')
        df['Trip Hour'] = df['Trip Date'].dt.hour
        df['Day of Week'] = df['Trip Date'].dt.day_name()
        df['Month'] = df['Trip Date'].dt.month_name()

        # Process Trip Pay Amount
        if 'Trip Pay Amount' in df.columns:
            df['Trip Pay Amount Cleaned'] = df['Trip Pay Amount'].apply(extract_ugx_amount)
        else:
            st.warning("No 'Trip Pay Amount' column found - creating placeholder")
            df['Trip Pay Amount Cleaned'] = 0.0

        # Process Distance
        df['Distance'] = pd.to_numeric(df['Trip Distance (KM/Mi)'], errors='coerce').fillna(0)

        # Ensure Company Commission exists
        if 'Company Commission Cleaned' not in df.columns:
            st.warning("No company commission data found - creating placeholder")
            df['Company Commission Cleaned'] = 0.0

        # Ensure Pay Mode exists
        if 'Pay Mode' not in df.columns:
            st.warning("No 'Pay Mode' column found - adding placeholder")
            df['Pay Mode'] = 'Unknown'

        return df

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# [Rest of your existing functions remain the same...]

def main():
    st.title("Union App Metrics Dashboard")
    UNION_STAFF_FILE_PATH = r"./UNION STAFF.xlsx"

    try:
        # Clear any cached data to ensure fresh load
        st.cache_data.clear()

        # Get date range first
        min_date = datetime(2023, 1, 1).date()  # Default minimum date
        max_date = datetime.now().date()  # Default maximum date

        # Try to get min/max dates from trip data if available
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

        # Load all data with date filtering
        df = load_data()
        if len(date_range) == 2:
            df = df[(df['Trip Date'].dt.date >= date_range[0]) &
                    (df['Trip Date'].dt.date <= date_range[1])]

        # Load passenger and driver data with the same date filtering
        df_passengers = load_passengers_data(date_range)
        df_drivers = load_drivers_data(date_range)

        if df.empty:
            st.error("No data loaded - please check the backend data file")
            return

        if 'Trip Date' not in df.columns:
            st.error("No 'Trip Date' column found in the data")
            return

        # Calculate passenger and driver metrics with filtered data
        app_downloads, passenger_wallet_balance = passenger_metrics(df_passengers)
        riders_onboarded, driver_wallet_balance, commission_owed = driver_metrics(df_drivers)

        unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
        retention_rate, passenger_ratio = calculate_driver_retention_rate(
            riders_onboarded, app_downloads, unique_drivers
        )

        # Prepare download buttons
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

        with tab1:  # Overview Tab
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

        with tab2:  # Financial Tab
            st.header("Financial Performance")

            col1, col2, col3 = st.columns(3)
            with col1:
                total_revenue = df['Trip Pay Amount Cleaned'].sum()
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

        with tab3:  # User Analysis Tab
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
            passenger_value_segmentation(df)
            top_10_drivers_by_earnings(df)

            # Union Staff trips table - passenger based
            st.markdown("---")
            st.subheader("Union Staff Trip Completion")

            try:
                if os.path.exists(UNION_STAFF_FILE_PATH):
                    union_staff_df = pd.read_excel(UNION_STAFF_FILE_PATH)
                    # Assume first column is staff names
                    if union_staff_df.empty or union_staff_df.shape[1] == 0:
                        st.warning("Union Staff file is empty or does not contain columns.")
                    else:
                        union_staff_names = union_staff_df.iloc[:, 0].dropna().astype(str).tolist()
                        st.metric("Total Union Staff Members", len(union_staff_names))

                        staff_trips_df = get_completed_trips_by_union_passengers(df, union_staff_names)
                        if not staff_trips_df.empty:
                            st.dataframe(staff_trips_df)
                        else:
                            st.info("No matching completed trips found for Union Staff members.")
                else:
                    st.info(f"Union Staff file not found at: {UNION_STAFF_FILE_PATH}")

            except Exception as e:
                st.error(f"Error processing Union Staff file: {e}")

        with tab4:  # Geographic Tab
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
