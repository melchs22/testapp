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
TRIPS_FILE_PATH = r"./BEER.xlsx"
TRANSACTIONS_FILE_PATH = r"./TRANSACTIONS.xlsx"
UNION_STAFF_FILE_PATH = r"./UNION STAFF.xlsx"

# Function to load passengers data with date filtering
def load_passengers_data(date_range=None):
    try:
        if not os.path.exists(PASSENGERS_FILE_PATH):
            st.warning(f"Passengers file not found at {PASSENGERS_FILE_PATH}")
            return pd.DataFrame()
        df = pd.read_excel(PASSENGERS_FILE_PATH)
        if 'Created' not in df.columns:
            st.warning("Missing 'Created' column in PASSENGERS.xlsx")
            return pd.DataFrame()
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        df = df.dropna(subset=['Created'])
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
        if not os.path.exists(DRIVERS_FILE_PATH):
            st.warning(f"Drivers file not found at {DRIVERS_FILE_PATH}")
            return pd.DataFrame()
        df = pd.read_excel(DRIVERS_FILE_PATH)
        if 'Created' not in df.columns:
            st.warning("Missing 'Created' column in DRIVERS.xlsx")
            return pd.DataFrame()
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        df = df.dropna(subset=['Created'])
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['Created'].dt.date >= start_date) &
                    (df['Created'].dt.date <= end_date)]
        return df
    except Exception as e:
        st.error(f"Error loading drivers data: {str(e)}")
        return pd.DataFrame()

# Function to calculate passenger metrics
def passenger_metrics(passengers_df):
    if passengers_df.empty:
        return 0, 0
    app_downloads = len(passengers_df)
    wallet_balance = passengers_df['Wallet Balance'].sum() if 'Wallet Balance' in passengers_df.columns else 0
    return app_downloads, wallet_balance

# Function to calculate driver metrics
def driver_metrics(drivers_df):
    if drivers_df.empty:
        return 0, 0, 0
    riders_onboarded = len(drivers_df)
    driver_wallet_balance = drivers_df[drivers_df['Wallet Balance'] > 0]['Wallet Balance'].sum() if 'Wallet Balance' in drivers_df.columns else 0
    commission_owed = abs(drivers_df[drivers_df['Wallet Balance'] < 0]['Wallet Balance'].sum()) if 'Wallet Balance' in drivers_df.columns else 0
    return riders_onboarded, driver_wallet_balance, commission_owed

# Updated load_data with robust column checking
def load_data():
    try:
        # Load trips data
        if not os.path.exists(TRIPS_FILE_PATH):
            st.warning(f"Trips file not found at {TRIPS_FILE_PATH}")
            return pd.DataFrame()
        df_trips = pd.read_excel(TRIPS_FILE_PATH)
        st.write("Columns in BEER.xlsx:", df_trips.columns.tolist())

        # Find Trip Date column
        trip_date_col = next((col for col in df_trips.columns if 'trip date' in col.lower() or 'date' in col.lower()), None)
        if not trip_date_col:
            st.error("No 'Trip Date' column found in BEER.xlsx. Available columns: " + str(df_trips.columns.tolist()))
            return pd.DataFrame()
        df_trips = df_trips.rename(columns={trip_date_col: 'Trip Date'})

        # Load transactions data
        if not os.path.exists(TRANSACTIONS_FILE_PATH):
            st.warning(f"Transactions file not found at {TRANSACTIONS_FILE_PATH}")
            return df_trips
        df_transactions = pd.read_excel(TRANSACTIONS_FILE_PATH)
        st.write("Columns in TRANSACTIONS.xlsx:", df_transactions.columns.tolist())

        df_trips['Trip Date'] = pd.to_datetime(df_trips['Trip Date'], errors='coerce')
        df_trips['Trip Hour'] = df_trips['Trip Date'].dt.hour
        df_trips['Day of Week'] = df_trips['Trip Date'].dt.day_name()
        df_trips['Month'] = df_trips['Trip Date'].dt.month_name()

        # Handle Trip Pay Amount
        trip_pay_col = next((col for col in df_trips.columns if 'trip pay' in col.lower()), None)
        if trip_pay_col:
            def extract_and_sum_amounts(value):
                try:
                    if pd.isna(value):
                        return 0.0
                    amounts = re.findall(r'UGX[\s]*(\d+)', str(value), re.IGNORECASE)
                    return sum(float(amount) for amount in amounts) if amounts else 0.0
                except:
                    return 0.0
            df_trips['Trip Pay Amount Cleaned'] = df_trips[trip_pay_col].apply(extract_and_sum_amounts)
        else:
            st.warning("No 'Trip Pay Amount' column found in BEER.xlsx")
            df_trips['Trip Pay Amount Cleaned'] = 0.0

        df_trips['Distance'] = pd.to_numeric(df_trips['Trip Distance (KM/Mi)'], errors='coerce').fillna(0)

        # Initialize default columns
        df_trips['Company Commission Cleaned'] = 0.0
        df_trips['Pay Mode'] = 'Unknown'

        # Merge with transactions for completed trips
        completed_trips = df_trips[df_trips['Trip Status'] == 'Job Completed'].copy()
        if not df_transactions.empty:
            # Assume Trip ID is the linking key (replace with actual key if different)
            trip_id_col_trips = next((col for col in df_trips.columns if 'trip id' in col.lower()), None)
            trip_id_col_trans = next((col for col in df_transactions.columns if 'trip id' in col.lower()), None)
            if trip_id_col_trips and trip_id_col_trans:
                df_transactions = df_transactions.rename(columns={trip_id_col_trans: 'Trip ID'})
                completed_trips = completed_trips.rename(columns={trip_id_col_trips: 'Trip ID'})
                merge_cols = ['Trip ID']
            else:
                # Fallback: Match on Trip Date, Driver, Passenger
                st.warning("No Trip ID found, attempting to match on Trip Date, Driver, Passenger")
                merge_cols = ['Trip Date', 'Driver', 'Passenger']
                df_transactions['Trip Date'] = pd.to_datetime(df_transactions['Trip Date'], errors='coerce')

            # Find Company Amt and Pay Mode columns
            company_amt_col = next((col for col in df_transactions.columns if 'company amt' in col.lower() or 'company amount' in col.lower()), None)
            pay_mode_col = next((col for col in df_transactions.columns if 'pay mode' in col.lower() or 'payment mode' in col.lower()), None)

            if company_amt_col:
                df_transactions['Company Commission Cleaned'] = pd.to_numeric(df_transactions[company_amt_col], errors='coerce').fillna(0)
            else:
                st.warning("No 'Company Amt (UGX)' column found in TRANSACTIONS.xlsx")
                df_transactions['Company Commission Cleaned'] = 0.0

            if pay_mode_col:
                df_transactions['Pay Mode'] = df_transactions[pay_mode_col].fillna('Unknown')
            else:
                st.warning("No 'Pay Mode' column found in TRANSACTIONS.xlsx")
                df_transactions['Pay Mode'] = 'Unknown'

            # Merge completed trips with transactions
            merged_completed = completed_trips.merge(
                df_transactions[merge_cols + ['Company Commission Cleaned', 'Pay Mode']],
                on=merge_cols,
                how='left'
            )
            merged_completed['Company Commission Cleaned'] = merged_completed['Company Commission Cleaned'].fillna(0.0)
            merged_completed['Pay Mode'] = merged_completed['Pay Mode'].fillna('Unknown')

            # Update original dataframe
            df_trips = pd.concat([df_trips[df_trips['Trip Status'] != 'Job Completed'], merged_completed], ignore_index=True)

        return df_trips
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# New Metrics Functions
def trip_completion_rate(df):
    if 'Trip Status' not in df.columns:
        return None
    completed_trips = df[df['Trip Status'] == 'Job Completed'].shape[0]
    total_trips = df.shape[0]
    return (completed_trips / total_trips * 100) if total_trips > 0 else 0

def daily_active_users(df):
    if 'Trip Date' not in df.columns or 'Passenger' not in df.columns or 'Driver' not in df.columns:
        return None
    df['Date'] = df['Trip Date'].dt.date
    dau = df.groupby('Date').agg({
        'Passenger': 'nunique',
        'Driver': 'nunique'
    }).reset_index()
    dau.columns = ['Date', 'Active Passengers', 'Active Drivers']
    return dau

def plot_dau(df):
    dau = daily_active_users(df)
    if dau is not None:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dau['Date'], y=dau['Active Passengers'], name='Active Passengers', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=dau['Date'], y=dau['Active Drivers'], name='Active Drivers', line=dict(color='green')))
        fig.update_layout(title='Daily Active Users', xaxis_title='Date', yaxis_title='Number of Users')
        st.plotly_chart(fig, use_container_width=True)

def net_revenue_per_trip(df):
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    total_commission = df['Company Commission Cleaned'].sum()
    num_trips = len(df)
    return ((total_revenue - total_commission) / num_trips) if num_trips > 0 else 0

def payment_method_success_rate(df):
    if 'Pay Mode' not in df.columns or 'Trip Status' not in df.columns:
        return None
    completed_trips = df[df['Trip Status'] == 'Job Completed']
    non_cash_trips = completed_trips[completed_trips['Pay Mode'].str.lower() != 'cash'].shape[0]
    total_completed = completed_trips.shape[0]
    return (non_cash_trips / total_completed * 100) if total_completed > 0 else 0

def repeat_passenger_rate(df):
    if 'Passenger' not in df.columns or 'Trip Status' not in df.columns:
        return None
    completed_trips = df[df['Trip Status'] == 'Job Completed']
    passenger_trip_counts = completed_trips['Passenger'].value_counts()
    repeat_passengers = passenger_trip_counts[passenger_trip_counts > 1].count()
    total_passengers = passenger_trip_counts.count()
    return (repeat_passengers / total_passengers * 100) if total_passengers > 0 else 0

def driver_churn_rate(df, df_drivers):
    if 'Driver' not in df.columns or df.empty or df_drivers.empty:
        return None
    active_drivers = df['Driver'].nunique()
    total_drivers = len(df_drivers)
    inactive_drivers = total_drivers - active_drivers
    return (inactive_drivers / total_drivers * 100) if total_drivers > 0 else 0

def hotspot_analysis(df):
    if 'From Location' not in df.columns or 'Trip Hour' not in df.columns:
        return None
    top_locations = df['From Location'].value_counts().nlargest(5).index
    hotspot_data = df[df['From Location'].isin(top_locations)].groupby(['Trip Hour', 'From Location']).size().reset_index(name='Trips')
    return hotspot_data

def plot_hotspot_analysis(df):
    hotspot_data = hotspot_analysis(df)
    if hotspot_data is not None:
        fig = px.bar(
            hotspot_data,
            x='Trip Hour',
            y='Trips',
            color='From Location',
            title='Pickup Hotspots by Hour',
            labels={'Trip Hour': 'Hour of Day', 'Trips': 'Number of Trips'}
        )
        st.plotly_chart(fig, use_container_width=True)

def calculate_cancellation_rate(df):
    if 'Trip Status' not in df.columns:
        return None
    cancelled_statuses = [
        'Cancelled by Rider',
        'Cancelled by Driver at Pickup Location',
        'Cancelled by Driver'
    ]
    cancelled_trips = df[df['Trip Status'].isin(cancelled_statuses)].shape[0]
    total_trips = df.shape[0]
    return (cancelled_trips / total_trips * 100) if total_trips > 0 else 0

def calculate_passenger_search_timeout(df):
    if 'Trip Status' not in df.columns:
        return None
    expired_trips = df[df['Trip Status'] == 'Expired'].shape[0]
    total_trips = df.shape[0]
    return (expired_trips / total_trips * 100) if total_trips > 0 else 0

def completed_vs_cancelled_daily(df):
    if 'Trip Status' not in df.columns or 'Trip Date' not in df.columns:
        return None
    completed_status = ['Job Completed', 'Partner Assigned', 'Partner Arrived']
    cancelled_statuses = [
        'Cancelled by Rider',
        'Cancelled by Driver at Pickup Location',
        'Cancelled by Driver'
    ]
    expired_status = ['Expired']
    df['Date'] = df['Trip Date'].dt.date
    daily_data = df.groupby(['Date', 'Trip Status']).size().unstack(fill_value=0)
    completed_cols = [col for col in daily_data.columns if col in completed_status]
    cancelled_cols = [col for col in daily_data.columns if col in cancelled_statuses]
    expired_cols = [col for col in daily_data.columns if col in expired_status]
    daily_data['Completed'] = daily_data[completed_cols].sum(axis=1) if completed_cols else 0
    daily_data['Cancelled'] = daily_data[cancelled_cols].sum(axis=1) if cancelled_cols else 0
    daily_data['Expired'] = daily_data[expired_cols].sum(axis=1) if expired_cols else 0
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=daily_data.index,
        y=daily_data['Completed'],
        name='Completed Trips',
        marker_color='green'
    ))
    fig.add_trace(go.Bar(
        x=daily_data.index,
        y=daily_data['Cancelled'],
        name='Cancelled Trips',
        marker_color='red'
    ))
    fig.add_trace(go.Bar(
        x=daily_data.index,
        y=daily_data['Expired'],
        name='Expired Trips',
        marker_color='orange'
    ))
    fig.update_layout(
        title='Daily Trip Status Breakdown',
        xaxis_title='Date',
        yaxis_title='Number of Trips',
        barmode='group'
    )
    return fig

def calculate_driver_retention_rate(riders_onboarded, app_downloads, unique_drivers):
    retention_rate = (unique_drivers / riders_onboarded * 100) if riders_onboarded > 0 else 0
    passenger_ratio = app_downloads / unique_drivers if unique_drivers > 0 else 0
    return retention_rate, passenger_ratio

def total_trips_by_status(df):
    if 'Trip Status' in df.columns:
        status_counts = df['Trip Status'].value_counts().reset_index()
        status_counts.columns = ['Trip Status', 'Count']
        fig = px.bar(
            status_counts,
            x='Trip Status',
            y='Count',
            title='Total Trips by Status',
            labels={'Count': 'Number of Trips'}
        )
        st.plotly_chart(fig, use_container_width=True)

def total_distance_covered(df):
    total_distance = df['Distance'].sum()
    st.metric("Total Distance Covered", f"{total_distance:,.1f} km")

def revenue_by_day(df):
    if 'Trip Date' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        df['Day'] = df['Trip Date'].dt.date
        daily_revenue = df.groupby('Day')['Trip Pay Amount Cleaned'].sum().reset_index()
        fig = px.line(
            daily_revenue,
            x='Day',
            y='Trip Pay Amount Cleaned',
            title='Revenue by Day'
        )
        st.plotly_chart(fig, use_container_width=True)

def avg_revenue_per_trip(df):
    avg_revenue = df['Trip Pay Amount Cleaned'].mean()
    st.metric("Avg. Revenue per Trip", f"{avg_revenue:,.0f} UGX")

def top_pickup_locations(df):
    if 'From Location' in df.columns:
        top_pickups = df['From Location'].value_counts().nlargest(10).reset_index()
        top_pickups.columns = ['Location', 'Trips']
        st.dataframe(top_pickups)
    else:
        st.warning("No pickup location data available")

def total_trips_by_type(df):
    if 'Trip Type' in df.columns:
        trip_type_counts = df['Trip Type'].value_counts().reset_index()
        trip_type_counts.columns = ['Trip Type', 'Count']
        fig = px.pie(
            trip_type_counts,
            names='Trip Type',
            values='Count',
            title='Total Trips by Type'
        )
        st.plotly_chart(fig, use_container_width=True)

def top_drivers_by_revenue(df):
    if 'Driver' in df.columns:
        driver_performance = df.groupby('Driver').agg({
            'Trip Pay Amount Cleaned': 'sum',
            'Distance': 'sum'
        }).nlargest(10, 'Trip Pay Amount Cleaned')
        st.subheader("Top 10 Drivers by Revenue")
        fig = px.bar(
            driver_performance,
            x=driver_performance.index,
            y='Trip Pay Amount Cleaned',
            labels={'Trip Pay Amount Cleaned': 'Revenue (UGX)'}
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No driver data available")

def passenger_insights(df):
    if 'Passenger' in df.columns:
        st.subheader("Top Passengers by Number of Trips")
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        top_passengers = completed_trips['Passenger'].value_counts().nlargest(10).reset_index()
        top_passengers.columns = ['Passenger', 'Trips']
        st.dataframe(top_passengers)
    else:
        st.warning("No passenger data available")

def peak_hours(df):
    if 'Trip Hour' in df.columns:
        hourly_trips = df['Trip Hour'].value_counts().sort_index()
        fig = px.bar(
            hourly_trips,
            title='Requests by Hour of Day',
            labels={'value': 'Number of Trips', 'index': 'Hour'}
        )
        st.plotly_chart(fig, use_container_width=True)

def trip_status_trends(df):
    if 'Trip Status' in df.columns and 'Trip Date' in df.columns:
        status_trends = df.groupby([df['Trip Date'].dt.date, 'Trip Status']).size().reset_index(name='Count')
        fig = px.bar(
            status_trends,
            x='Trip Date',
            y='Count',
            color='Trip Status',
            title='Trip Status Trends Over Time'
        )
        st.plotly_chart(fig, use_container_width=True)

def total_commission(df):
    total_commission = df['Company Commission Cleaned'].sum()
    st.metric("Total Commission", f"{total_commission:,.0f} UGX")

def unique_driver_count(df):
    unique_drivers = df['Driver'].nunique()
    st.metric("Number of Unique Drivers", unique_drivers)

def top_10_drivers_by_earnings(df):
    if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        top_drivers = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().nlargest(10)
        st.subheader("Top 10 Drivers by Earnings (Total Trip Pay)")
        st.dataframe(top_drivers)
    else:
        st.warning("No driver or trip pay data available")

def most_frequent_locations(df):
    if 'From Location' in df.columns and 'To Location' in df.columns:
        from_location_counts = df['From Location'].value_counts().nlargest(10).reset_index()
        to_location_counts = df['To Location'].value_counts().nlargest(10).reset_index()
        from_location_counts.columns = ['Location', 'Trips']
        to_location_counts.columns = ['Location', 'Trips']
        st.subheader("Most Frequent Pickup Locations")
        st.dataframe(from_location_counts)
        st.subheader("Most Frequent Drop-off Locations")
        st.dataframe(to_location_counts)
    else:
        st.warning("No location data available")

def revenue_share(df):
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    total_commission = df['Company Commission Cleaned'].sum()
    if total_revenue > 0:
        revenue_share = total_commission / total_revenue
        st.metric("Revenue Share (Company vs Driver)", f"{revenue_share * 100:.2f}%")
    else:
        st.metric("Revenue Share (Company vs Driver)", "N/A")

def total_payout_to_drivers(df):
    total_payout = df['Company Commission Cleaned'].sum()
    st.metric("Total Commission Paid by Drivers", f"{total_payout:,.0f} UGX")

def fare_per_km(df):
    total_fare = df['Trip Pay Amount Cleaned'].sum()
    total_distance = df['Distance'].sum()
    if total_distance > 0:
        fare_per_km = total_fare / total_distance
        st.metric("Fare per Kilometer/Mile", f"{fare_per_km:,.2f} UGX")
    else:
        st.metric("Fare per Kilometer/Mile", "N/A")

def customer_payment_methods(df):
    if 'Pay Mode' in df.columns:
        pay_mode_counts = df['Pay Mode'].value_counts().reset_index()
        pay_mode_counts.columns = ['Payment Method', 'Count']
        fig = px.pie(
            pay_mode_counts,
            names='Payment Method',
            values='Count',
            title='Customer Payment Methods Breakdown'
        )
        st.plotly_chart(fig, use_container_width=True)

def gross_profit(df):
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    total_commission = df['Company Commission Cleaned'].sum()
    gross_profit = total_revenue - total_commission
    st.metric("Rider Revenue", f"{gross_profit:,.0f} UGX")

def avg_commission_per_trip(df):
    total_commission = df['Company Commission Cleaned'].sum()
    num_trips = len(df)
    if num_trips > 0:
        avg_commission = total_commission / num_trips
        st.metric("Avg. Commission per Trip", f"{avg_commission:,.0f} UGX")
    else:
        st.metric("Avg. Commission per Trip", "N/A")

def revenue_per_driver(df):
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    unique_drivers = df['Driver'].nunique()
    if unique_drivers > 0:
        revenue_per_driver = total_revenue / unique_drivers
        st.metric("Revenue per Driver", f"{revenue_per_driver:,.0f} UGX")
    else:
        st.metric("Revenue per Driver", "N/A")

def driver_earnings_per_trip(df):
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    total_commission = df['Company Commission Cleaned'].sum()
    num_trips = len(df)
    if num_trips > 0:
        earnings_per_trip = (total_revenue - total_commission) / num_trips
        st.metric("Driver Earnings per Trip", f"{earnings_per_trip:,.0f} UGX")
    else:
        st.metric("Driver Earnings per Trip", "N/A")

def trips_per_driver(df):
    if 'Driver' in df.columns:
        num_trips = len(df)
        unique_drivers = df['Driver'].nunique()
        if unique_drivers > 0:
            trips_per_driver = num_trips / unique_drivers
            st.metric("Avg. Trips per Driver", f"{trips_per_driver:.1f}")
        else:
            st.metric("Avg. Trips per Driver", "N/A")

def payment_method_revenue(df):
    if 'Pay Mode' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        payment_revenue = df.groupby('Pay Mode')['Trip Pay Amount Cleaned'].sum().reset_index()
        fig = px.pie(
            payment_revenue,
            names='Pay Mode',
            values='Trip Pay Amount Cleaned',
            title='Revenue by Payment Method'
        )
        st.plotly_chart(fig, use_container_width=True)

def distance_vs_revenue_scatter(df):
    if 'Distance' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        fig = px.scatter(
            df,
            x='Distance',
            y='Trip Pay Amount Cleaned',
            title='Distance vs. Revenue',
            trendline='ols'
        )
        st.plotly_chart(fig, use_container_width=True)

def weekday_vs_weekend_analysis(df):
    if 'Trip Date' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        df['Is Weekend'] = df['Trip Date'].dt.dayofweek >= 5
        weekend_data = df.groupby('Is Weekend').agg({
            'Trip Pay Amount Cleaned': 'sum',
            'Distance': 'sum',
            'Trip Status': 'count'
        }).reset_index()
        weekend_data['Is Weekend'] = weekend_data['Is Weekend'].map({True: 'Weekend', False: 'Weekday'})
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                weekend_data,
                x='Is Weekend',
                y='Trip Pay Amount Cleaned',
                title='Revenue: Weekend vs Weekday'
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.bar(
                weekend_data,
                x='Is Weekend',
                y='Trip Status',
                title='Trips: Weekend vs Weekday'
            )
            st.plotly_chart(fig, use_container_width=True)

def driver_performance_comparison(df):
    if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns and 'Distance' in df.columns:
        driver_stats = df.groupby('Driver').agg({
            'Trip Pay Amount Cleaned': ['mean', 'sum'],
            'Distance': ['mean', 'sum'],
            'Trip Status': 'count'
        }).reset_index()
        driver_stats.columns = ['Driver', 'Avg Revenue per Trip', 'Total Revenue',
                                'Avg Distance per Trip', 'Total Distance', 'Number of Trips']
        st.subheader("Driver Performance Comparison")
        st.dataframe(driver_stats.sort_values('Total Revenue', ascending=False))

def passenger_value_segmentation(df):
    if 'Passenger' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        passenger_stats = df.groupby('Passenger').agg({
            'Trip Pay Amount Cleaned': 'sum',
            'Trip Status': 'count'
        }).reset_index()
        passenger_stats.columns = ['Passenger', 'Total Spend', 'Number of Trips']
        if not passenger_stats['Total Spend'].duplicated().all():
            passenger_stats['Segment'] = pd.qcut(passenger_stats['Total Spend'],
                                                 q=3,
                                                 labels=['Low', 'Medium', 'High'],
                                                 duplicates='drop')
            st.subheader("Passenger Value Segmentation")
            fig = px.scatter(
                passenger_stats,
                x='Number of Trips',
                y='Total Spend',
                color='Segment',
                title='Passenger Value Segmentation'
            )
            st.plotly_chart(fig, use_container_width=True)

def get_download_data(df, df_passengers, df_drivers, union_staff_df):
    return {
        'Trips': df,
        'Passengers': df_passengers,
        'Drivers': df_drivers,
        'Union Staff': union_staff_df
    }

def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded,
                       passenger_wallet_balance, driver_wallet_balance, commission_owed, df_drivers):
    pdf = FPDF()
    pdf.add_page()
    try:
        pdf.image(r"./your_image.png", x=10, y=8, w=50)
        pdf.ln(40)
    except:
        st.warning("Could not add image to PDF")
        pdf.ln(20)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Union App Metrics Dashboard Report", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Date Range: {date_range[0]} to {date_range[1]}", ln=1, align='C')
    pdf.ln(10)

    # Section 1: Overview Metrics
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="1. Overview Metrics", ln=1)
    pdf.set_font("Arial", size=12)
    total_trips = len(df)
    completed_trips = len(df[df['Trip Status'] == 'Job Completed'])
    avg_distance = df['Distance'].mean() if 'Distance' in df.columns else 0
    cancellation_rate = calculate_cancellation_rate(df) or 0
    timeout_rate = calculate_passenger_search_timeout(df) or 0
    completion_rate = trip_completion_rate(df) or 0
    unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
    trips_per_driver = total_trips / unique_drivers if unique_drivers > 0 else 0
    dau = daily_active_users(df)
    avg_passenger_dau = dau['Active Passengers'].mean() if dau is not None else 0
    avg_driver_dau = dau['Active Drivers'].mean() if dau is not None else 0
    pdf.cell(200, 10, txt=f"Total Requests: {total_trips}", ln=1)
    pdf.cell(200, 10, txt=f"Completed Trips: {completed_trips}", ln=1)
    pdf.cell(200, 10, txt=f"Trip Completion Rate: {completion_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Average Daily Active Passengers: {avg_passenger_dau:.0f}", ln=1)
    pdf.cell(200, 10, txt=f"Average Daily Active Drivers: {avg_driver_dau:.0f}", ln=1)
    pdf.cell(200, 10, txt=f"Average Distance: {avg_distance:.1f} km", ln=1)
    pdf.cell(200, 10, txt=f"Driver Cancellation Rate: {cancellation_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Passenger Search Timeout: {timeout_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Passenger App Downloads: {app_downloads}", ln=1)
    pdf.cell(200, 10, txt=f"Riders Onboarded: {riders_onboarded}", ln=1)
    pdf.cell(200, 10, txt=f"Number of Unique Drivers: {unique_drivers}", ln=1)
    pdf.cell(200, 10, txt=f"Average Trips per Driver: {trips_per_driver:.1f}", ln=1)
    pdf.cell(200, 10, txt=f"Driver Retention Rate: {retention_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Passenger-to-Driver Ratio: {passenger_ratio:.1f}", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(200, 5, txt="Explanation: A high daily completion rate indicates reliable service, while DAU reflects engagement. Drops in completion or spikes in timeouts on specific days may signal operational issues like driver shortages or app glitches.")
    pdf.ln(10)

    # Section 2: Financial Metrics
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="2. Financial Metrics", ln=1)
    pdf.set_font("Arial", size=12)
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    total_commission = df['Company Commission Cleaned'].sum()
    gross_profit = total_revenue - total_commission
    avg_revenue = df['Trip Pay Amount Cleaned'].mean()
    avg_commission = total_commission / total_trips if total_trips > 0 else 0
    revenue_per_driver = total_revenue / unique_drivers if unique_drivers > 0 else 0
    earnings_per_trip = gross_profit / total_trips if total_trips > 0 else 0
    net_revenue = net_revenue_per_trip(df)
    payment_success = payment_method_success_rate(df) or 0
    fare_per_km = total_revenue / df['Distance'].sum() if df['Distance'].sum() > 0 else 0
    revenue_share = (total_commission / total_revenue * 100) if total_revenue > 0 else 0
    pdf.cell(200, 10, txt=f"Total Value of Rides: {total_revenue:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Total Commission: {total_commission:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Rider Revenue: {gross_profit:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Net Revenue per Trip: {net_revenue:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Non-Cash Payment Success Rate: {payment_success:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Passenger Wallet Balance: {passenger_wallet_balance:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Driver Wallet Balance: {driver_wallet_balance:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Commission Owed: {commission_owed:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Average Revenue per Trip: {avg_revenue:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Average Commission per Trip: {avg_commission:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Revenue per Driver: {revenue_per_driver:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Driver Earnings per Trip: {earnings_per_trip:,.0f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Fare per Kilometer/Mile: {fare_per_km:,.2f} UGX", ln=1)
    pdf.cell(200, 10, txt=f"Revenue Share (Company vs Driver): {revenue_share:.2f}%", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(200, 5, txt="Explanation: Daily net revenue per trip shows profitability trends. Lower values or drops in non-cash payment success on certain days may indicate payment issues or short, low-value trips.")
    pdf.ln(10)

    # Section 3: User Analysis Metrics
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="3. User Analysis Metrics", ln=1)
    pdf.set_font("Arial", size=12)
    repeat_rate = repeat_passenger_rate(df) or 0
    churn_rate = driver_churn_rate(df, df_drivers) or 0
    pdf.cell(200, 10, txt=f"Passenger App Downloads: {app_downloads}", ln=1)
    pdf.cell(200, 10, txt=f"Riders Onboarded: {riders_onboarded}", ln=1)
    pdf.cell(200, 10, txt=f"Number of Unique Drivers: {unique_drivers}", ln=1)
    pdf.cell(200, 10, txt=f"Repeat Passenger Rate: {repeat_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Driver Churn Rate: {churn_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Driver Retention Rate: {retention_rate:.1f}%", ln=1)
    pdf.cell(200, 10, txt=f"Passenger-to-Driver Ratio: {passenger_ratio:.1f}", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Top 10 Drivers by Earnings:", ln=1)
    pdf.set_font("Arial", size=10)
    if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns:
        top_drivers = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().nlargest(10)
        for i, (driver, amount) in enumerate(top_drivers.items(), 1):
            pdf.cell(200, 7, txt=f"{i}. {driver}: {amount:,.0f} UGX", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Top 10 Passengers by Trips:", ln=1)
    pdf.set_font("Arial", size=10)
    if 'Passenger' in df.columns:
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        top_passengers = completed_trips['Passenger'].value_counts().nlargest(10)
        for i, (passenger, trips) in enumerate(top_passengers.items(), 1):
            pdf.cell(200, 7, txt=f"{i}. {passenger}: {trips} trips", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(200, 5, txt="Explanation: High repeat passenger rates and low churn rates on certain days reflect loyalty and engagement. High churn may indicate driver dissatisfaction, requiring retention strategies.")
    pdf.ln(10)

    # Section 4: Geographic Metrics
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="4. Geographic Metrics", ln=1)
    pdf.set_font("Arial", size=12)
    if 'From Location' in df.columns:
        top_pickups = df['From Location'].value_counts().nlargest(5)
        pdf.cell(200, 10, txt="Top 5 Pickup Locations:", ln=1)
        for i, (location, count) in enumerate(top_pickups.items(), 1):
            pdf.cell(200, 7, txt=f"{i}. {location}: {count} trips", ln=1)
    if 'To Location' in df.columns:
        top_dropoffs = df['To Location'].value_counts().nlargest(5)
        pdf.cell(200, 10, txt="Top 5 Drop-off Locations:", ln=1)
        for i, (location, count) in enumerate(top_dropoffs.items(), 1):
            pdf.cell(200, 7, txt=f"{i}. {location}: {count} trips", ln=1)
    hotspot_data = hotspot_analysis(df)
    if hotspot_data is not None:
        pdf.cell(200, 10, txt="Top 5 Pickup Hotspots by Hour:", ln=1)
        top_hotspots = hotspot_data.groupby('From Location')['Trips'].sum().nlargest(5)
        for i, (location, trips) in enumerate(top_hotspots.items(), 1):
            pdf.cell(200, 7, txt=f"{i}. {location}: {trips} trips", ln=1)
    pdf.ln(5)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(200, 5, txt="Explanation: Hourly hotspot trends guide driver allocation. Daily changes in top locations reveal demand patterns, optimizing service reliability.")
    return pdf

def get_completed_trips_by_union_passengers(df, union_staff_names):
    if 'Trip Status' not in df.columns or 'Passenger' not in df.columns:
        return pd.DataFrame(columns=['Union Staff', 'Completed Trips'])
    completed_trips = df[df['Trip Status'] == 'Job Completed']
    completed_trips['Passenger_lower'] = completed_trips['Passenger'].astype(str).str.strip().str.lower()
    staff_names_lower = [name.strip().lower() for name in union_staff_names]
    filtered_trips = completed_trips[completed_trips['Passenger_lower'].isin(staff_names_lower)]
    trips_count = filtered_trips.groupby('Passenger_lower').size().reset_index(name='Completed Trips')
    results = pd.DataFrame({'Union Staff': union_staff_names})
    results['Union Staff_lower'] = results['Union Staff'].str.strip().str.lower()
    results = results.merge(trips_count, left_on='Union Staff_lower', right_on='Passenger_lower', how='left')
    results['Completed Trips'] = results['Completed Trips'].fillna(0).astype(int)
    results = results.drop(columns=['Union Staff_lower', 'Passenger_lower'])
    return results

def main():
    st.title("Union App Metrics Dashboard")
    
    # Clear cache to ensure fresh data
    st.cache_data.clear()

    # Initialize date range
    default_min_date = datetime(2023, 1, 1).date()
    default_max_date = datetime.now().date()
    min_date = default_min_date
    max_date = default_max_date

    # Load trip data to determine date range
    df = load_data()
    if df.empty:
        st.error("No trip data loaded. Please check the data files and try again.")
        return

    # Find Trip Date column for date range
    trip_date_col = 'Trip Date' if 'Trip Date' in df.columns else None
    if not trip_date_col:
        st.error("Cannot filter by date: 'Trip Date' column not found in data.")
        return
    min_date = df[trip_date_col].min().date() or default_min_date
    max_date = df[trip_date_col].max().date() or default_max_date

    # Improved date filter
    st.sidebar.subheader("Filter Data")
    date_range = st.sidebar.date_input(
        "Select Date Range",
        value=[max_date, max_date],
        min_value=min_date,
        max_value=max_date,
        help="Choose a start and end date to filter the data. The range is limited to available trip data."
    )
    if len(date_range) == 2 and date_range[0] > date_range[1]:
        st.sidebar.error("Start date must be before end date")
        return

    # Apply date filtering
    if len(date_range) == 2 and trip_date_col:
        df = df[(df[trip_date_col].dt.date >= date_range[0]) &
                (df[trip_date_col].dt.date <= date_range[1])]

    df_passengers = load_passengers_data(date_range)
    df_drivers = load_drivers_data(date_range)
    union_staff_df = pd.read_excel(UNION_STAFF_FILE_PATH) if os.path.exists(UNION_STAFF_FILE_PATH) else pd.DataFrame()

    if df.empty:
        st.error("No trip data available for the selected date range")
        return

    # Calculate metrics
    app_downloads, passenger_wallet_balance = passenger_metrics(df_passengers)
    riders_onboarded, driver_wallet_balance, commission_owed = driver_metrics(df_drivers)
    unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
    retention_rate, passenger_ratio = calculate_driver_retention_rate(
        riders_onboarded, app_downloads, unique_drivers
    )

    # Download buttons
    st.sidebar.markdown("---")
    st.sidebar.subheader("Export Data")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        data_dict = get_download_data(df, df_passengers, df_drivers, union_staff_df)
        for sheet_name, data in data_dict.items():
            data.to_excel(writer, sheet_name=sheet_name, index=False)
    excel_data = output.getvalue()
    st.sidebar.download_button(
        label="📊 Download All Data (Excel)",
        data=excel_data,
        file_name=f"union_app_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    pdf = create_metrics_pdf(df, date_range, retention_rate, passenger_ratio,
                             app_downloads, riders_onboarded, passenger_wallet_balance,
                             driver_wallet_balance, commission_owed, df_drivers)
    pdf_output = pdf.output(dest='S').encode('latin1')
    st.sidebar.download_button(
        label="📄 Download Metrics Report (PDF)",
        data=pdf_output,
        file_name=f"union_app_metrics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime="application/pdf"
    )

    # Dashboard tabs
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
            st.metric("Driver Cancellation Rate", f"{cancellation_rate:.1f}%" if cancellation_rate is not None else "N/A")
        with col5:
            completion_rate = trip_completion_rate(df)
            st.metric("Trip Completion Rate", f"{completion_rate:.1f}%" if completion_rate is not None else "N/A")
        col6, col7, col8 = st.columns(3)
        with col6:
            timeout_rate = calculate_passenger_search_timeout(df)
            st.metric("Passenger Search Timeout", f"{timeout_rate:.1f}%" if timeout_rate is not None else "N/A")
        with col7:
            trips_per_driver(df)
        with col8:
            st.metric("Passenger App Downloads", app_downloads)
        col9, col10 = st.columns(2)
        with col9:
            st.metric("Riders Onboarded", riders_onboarded)
        with col10:
            unique_driver_count(df)
        status_breakdown_fig = completed_vs_cancelled_daily(df)
        if status_breakdown_fig:
            st.plotly_chart(status_breakdown_fig, use_container_width=True)
        plot_dau(df)
        total_trips_by_status(df)
        total_distance_covered(df)
        revenue_by_day(df)
        avg_revenue_per_trip(df)
        total_commission(df)

    with tab2:
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
            net_revenue = net_revenue_per_trip(df)
            st.metric("Net Revenue per Trip", f"{net_revenue:,.0f} UGX")
        col10, col11, col12 = st.columns(3)
        with col10:
            payment_success = payment_method_success_rate(df)
            st.metric("Non-Cash Payment Success Rate", f"{payment_success:.1f}%" if payment_success is not None else "N/A")
        with col11:
            fare_per_km(df)
        with col12:
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
        col4, col5, col6 = st.columns(3)
        with col4:
            st.metric("Driver Retention Rate", f"{retention_rate:.1f}%",
                      help="Percentage of onboarded riders who are active drivers")
        with col5:
            st.metric("Passenger-to-Driver Ratio", f"{passenger_ratio:.1f}",
                      help="Number of passengers per active driver")
        with col6:
            repeat_rate = repeat_passenger_rate(df)
            st.metric("Repeat Passenger Rate", f"{repeat_rate:.1f}%" if repeat_rate is not None else "N/A")
        col7, col8 = st.columns(2)
        with col7:
            churn_rate = driver_churn_rate(df, df_drivers)
            st.metric("Driver Churn Rate", f"{churn_rate:.1f}%" if churn_rate is not None else "N/A")
        with col8:
            st.metric("Number of Unique Drivers", unique_drivers)
        top_drivers_by_revenue(df)
        driver_performance_comparison(df)
        passenger_insights(df)
        passenger_value_segmentation(df)
        top_10_drivers_by_earnings(df)
        st.markdown("---")
        st.subheader("Union Staff Trip Completion")
        if not union_staff_df.empty:
            union_staff_names = union_staff_df.iloc[:, 0].dropna().astype(str).tolist()
            st.metric("Total Union Staff Members", len(union_staff_names))
            staff_trips_df = get_completed_trips_by_union_passengers(df, union_staff_names)
            if not staff_trips_df.empty:
                st.dataframe(staff_trips_df)
            else:
                st.info("No matching completed trips found for Union Staff members")
        else:
            st.info(f"Union Staff file not found at: {UNION_STAFF_FILE_PATH}")

    with tab4:
        st.header("Geographic Analysis")
        most_frequent_locations(df)
        peak_hours(df)
        plot_hotspot_analysis(df)
        trip_status_trends(df)
        customer_payment_methods(df)

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    main()
