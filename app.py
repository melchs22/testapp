import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from fpdf import FPDF
import re
import os
from io import BytesIO
import base64
import tempfile
import logging
import json

# Set page config as the first Streamlit command
st.set_page_config(page_title="Ride-Hailing Metrics Dashboard", layout="wide")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# File paths (relative for Streamlit Cloud)
PASSENGERS_FILE_PATH = "./PASSENGERS.xlsx"
DRIVERS_FILE_PATH = "./DRIVERS.xlsx"
DATA_FILE_PATH = "./BEER.xlsx"
TRANSACTIONS_FILE_PATH = "./TRANSACTIONS.xlsx"
UNION_STAFF_FILE_PATH = "./UNION STAFF.xlsx"
LOGO_PATH = "./TUTU.png"

# Utility function to extract UGX amounts
def extract_ugx_amount(value):
    try:
        if pd.isna(value) or value is None:
            return 0.0
        value_str = str(value).replace('UGX', '').replace(',', '').strip()
        amounts = re.findall(r'[\d]+(?:\.\d+)?', value_str)
        if amounts:
            if '-' in value_str:
                return -float(amounts[0])
            return float(amounts[0])
        if value_str.replace('.', '').replace('-', '').isdigit():
            return float(value_str)
        return 0.0
    except (ValueError, TypeError):
        return 0.0

# Data loading functions
def load_passengers_data(date_range=None):
    try:
        if not os.path.exists(PASSENGERS_FILE_PATH):
            st.error("PASSENGERS.xlsx not found.")
            return pd.DataFrame()
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

def load_drivers_data(date_range=None):
    try:
        if not os.path.exists(DRIVERS_FILE_PATH):
            st.error("DRIVERS.xlsx not found.")
            return pd.DataFrame()
        df = pd.read_excel(DRIVERS_FILE_PATH)
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        if 'Wallet Balance' in df.columns:
            df['Wallet Balance'] = df['Wallet Balance'].apply(extract_ugx_amount)
        return df
    except Exception as e:
        st.error(f"Error loading drivers data: {str(e)}")
        return pd.DataFrame()

def load_transactions_data():
    try:
        if not os.path.exists(TRANSACTIONS_FILE_PATH):
            st.error("TRANSACTIONS.xlsx not found.")
            return pd.DataFrame()
        transactions_df = pd.read_excel(TRANSACTIONS_FILE_PATH)
        if 'Company Amt (UGX)' in transactions_df.columns:
            transactions_df['Company Commission Cleaned'] = transactions_df['Company Amt (UGX)'].apply(extract_ugx_amount)
        else:
            transactions_df['Company Commission Cleaned'] = 0.0
        transactions_df['Pay Mode'] = transactions_df.get('Pay Mode', 'Unknown').fillna('Unknown')
        return transactions_df[['Company Commission Cleaned', 'Pay Mode']]
    except Exception as e:
        st.error(f"Error loading transactions data: {str(e)}")
        return pd.DataFrame()

def load_data():
    try:
        if not os.path.exists(DATA_FILE_PATH):
            st.error("BEER.xlsx not found.")
            return pd.DataFrame()
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
        df['Trip Pay Amount Cleaned'] = df.get('Trip Pay Amount', 0.0).apply(extract_ugx_amount)
        df['Distance'] = pd.to_numeric(df.get('Trip Distance (KM/Mi)', 0), errors='coerce').fillna(0)
        df['Company Commission Cleaned'] = df.get('Company Commission Cleaned', 0.0)
        df['Pay Mode'] = df.get('Pay Mode', 'Unknown')
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# Metric calculation functions
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
            df_drivers['Wallet Balance'] = pd.to_numeric(df_drivers['Wallet Balance'], errors='coerce').fillna(0.0)
            positive_balances = df_drivers[df_drivers['Wallet Balance'] > 0]['Wallet Balance']
            driver_wallet_balance = float(positive_balances.sum()) if not positive_balances.empty else 0.0
            negative_balances = df_drivers[df_drivers['Wallet Balance'] < 0]['Wallet Balance']
            commission_owed = float(negative_balances.abs().sum()) if not negative_balances.empty else 0.0
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
            fig.add_trace(go.Bar(x=status_df.index, y=status_df[status], name=status))
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
            st.metric("Avg. Trips per Driver", "N/A")
            return
        trips_by_driver = df.groupby('Driver').size()
        avg_trips = trips_by_driver.mean() if not trips_by_driver.empty else 0
        st.metric("Avg. Trips per Driver", f"{avg_trips:.1f}")
    except Exception as e:
        st.error(f"Error in trips per driver: {str(e)}")

def total_trips_by_status(df):
    try:
        if 'Trip Status' not in df.columns:
            return None
        status_counts = df['Trip Status'].value_counts()
        fig = px.pie(values=status_counts.values, names=status_counts.index, title="Trip Status Distribution")
        return fig
    except Exception as e:
        st.error(f"Error in total trips by status: {str(e)}")
        return None

def total_distance_covered(df):
    try:
        if 'Distance' not in df.columns or 'Trip Status' not in df.columns:
            st.metric("Total Distance Covered", "N/A")
            return
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        total_distance = completed_trips['Distance'].sum()
        st.metric("Total Distance Covered", f"{total_distance:,.0f} km")
    except Exception as e:
        st.error(f"Error in total distance covered: {str(e)}")

def revenue_by_day(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Trip Date' not in df.columns:
            return None
        daily_revenue = df.groupby(df['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].sum().reset_index()
        daily_revenue['Trip Date'] = daily_revenue['Trip Date'].astype(str)
        fig = px.line(
            daily_revenue,
            x='Trip Date',
            y='Trip Pay Amount Cleaned',
            title="Daily Revenue Trend",
            labels={'Trip Date': 'Date', 'Trip Pay Amount Cleaned': 'Revenue (UGX)'}
        )
        fig.update_traces(mode='lines+markers')
        return fig
    except Exception as e:
        st.error(f"Error in revenue by day: {str(e)}")
        return None

def avg_revenue_per_trip(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns:
            st.metric("Avg. Revenue per Trip", "N/A")
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
            st.metric("Gross Profit", "N/A")
            return
        gross_profit = df['Company Commission Cleaned'].sum()
        st.metric("Gross Profit", f"{gross_profit:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in gross profit: {str(e)}")

def avg_commission_per_trip(df):
    try:
        if 'Company Commission Cleaned' not in df.columns:
            st.metric("Avg. Commission per Trip", "N/A")
            return
        avg_comm = df['Company Commission Cleaned'].mean()
        st.metric("Avg. Commission per Trip", f"{avg_comm:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in avg commission per trip: {str(e)}")

def revenue_per_driver(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            st.metric("Avg. Revenue per Driver", "N/A")
            return
        revenue_by_driver = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum()
        avg_revenue = revenue_by_driver.mean() if not revenue_by_driver.empty else 0
        st.metric("Avg. Revenue per Driver", f"{avg_revenue:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in revenue per driver: {str(e)}")

def driver_earnings_per_trip(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            st.metric("Avg. Driver Earnings per Trip", "N/A")
            return
        df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
        avg_earnings = df['Driver Earnings'].mean()
        st.metric("Avg. Driver Earnings per Trip", f"{avg_earnings:,.0f} UGX")
    except Exception as e:
        st.error(f"Error in driver earnings per trip: {str(e)}")

def fare_per_km(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Distance' not in df.columns or 'Trip Status' not in df.columns:
            st.metric("Avg. Fare per KM", "N/A")
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
            st.metric("Revenue Share", "N/A")
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
            return None
        type_counts = df['Trip Type'].value_counts()
        fig = px.pie(values=type_counts.values, names=type_counts.index, title="Trips by Type")
        return fig
    except Exception as e:
        st.error(f"Error in total trips by type: {str(e)}")
        return None

def payment_method_revenue(df):
    try:
        if 'Pay Mode' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return None
        revenue_by_payment = df.groupby('Pay Mode')['Trip Pay Amount Cleaned'].sum()
        fig = px.pie(values=revenue_by_payment.values, names=revenue_by_payment.index, title="Revenue by Payment Method")
        return fig
    except Exception as e:
        st.error(f"Error in payment method revenue: {str(e)}")
        return None

def distance_vs_revenue_scatter(df):
    try:
        if 'Distance' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return None
        fig = px.scatter(
            df,
            x='Distance',
            y='Trip Pay Amount Cleaned',
            title="Distance vs Revenue",
            labels={'Distance': 'Distance (km)', 'Trip Pay Amount Cleaned': 'Revenue (UGX)'}
        )
        return fig
    except Exception as e:
        st.error(f"Error in distance vs revenue scatter: {str(e)}")
        return None

def weekday_vs_weekend_analysis(df):
    try:
        if 'Day of Week' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return None
        df['Is Weekend'] = df['Day of Week'].isin(['Saturday', 'Sunday'])
        revenue_by_period = df.groupby('Is Weekend')['Trip Pay Amount Cleaned'].sum()
        fig = px.bar(
            x=['Weekday', 'Weekend'],
            y=revenue_by_period.values,
            title="Weekday vs Weekend Revenue",
            labels={'x': 'Period', 'y': 'Revenue (UGX)'}
        )
        return fig
    except Exception as e:
        st.error(f"Error in weekday vs weekend analysis: {str(e)}")
        return None

def unique_driver_count(df):
    try:
        if 'Driver' not in df.columns:
            st.metric("Unique Drivers", "N/A")
            return
        unique_drivers = df['Driver'].nunique()
        st.metric("Unique Drivers", unique_drivers)
    except Exception as e:
        st.error(f"Error in unique driver count: {str(e)}")

def top_drivers_by_revenue(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            return None
        top_drivers = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().nlargest(5)
        fig = px.bar(
            x=top_drivers.values,
            y=top_drivers.index,
            orientation='h',
            title="Top 5 Drivers by Revenue",
            labels={'x': 'Revenue (UGX)', 'y': 'Driver'}
        )
        return fig
    except Exception as e:
        st.error(f"Error in top drivers by revenue: {str(e)}")
        return None

def driver_performance_comparison(df):
    try:
        if 'Driver' not in df.columns:
            return None
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
        return fig
    except Exception as e:
        st.error(f"Error in driver performance comparison: {str(e)}")
        return None

def passenger_insights(df):
    try:
        if 'Passenger' not in df.columns:
            return None
        passenger_trips = df.groupby('Passenger').size().value_counts()
        fig = px.bar(
            x=passenger_trips.index,
            y=passenger_trips.values,
            title="Passenger Trip Frequency",
            labels={'x': 'Number of Trips', 'y': 'Number of Passengers'}
        )
        return fig
    except Exception as e:
        st.error(f"Error in passenger insights: {str(e)}")
        return None

def top_10_drivers_by_earnings(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            return None
        df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
        top_drivers = df.groupby('Driver')['Driver Earnings'].sum().nlargest(10)
        fig = px.bar(
            x=top_drivers.values,
            y=top_drivers.index,
            orientation='h',
            title="Top 10 Drivers by Earnings",
            labels={'x': 'Earnings (UGX)', 'y': 'Driver'}
        )
        return fig
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
            return None
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
        with col2:
            fig2 = px.bar(
                x=dropoff_counts.values,
                y=dropoff_counts.index,
                orientation='h',
                title="Top 5 Dropoff Locations",
                labels={'x': 'Number of Trips', 'y': 'Location'}
            )
            st.plotly_chart(fig2, use_container_width=True)
        return fig1  # Return one for report purposes
    except Exception as e:
        st.error(f"Error in most frequent locations: {str(e)}")
        return None

def peak_hours(df):
    try:
        if 'Trip Hour' not in df.columns:
            return None
        hour_counts = df['Trip Hour'].value_counts().sort_index()
        fig = px.bar(
            x=hour_counts.index,
            y=hour_counts.values,
            title="Trip Distribution by Hour",
            labels={'x': 'Hour of Day', 'y': 'Number of Trips'}
        )
        return fig
    except Exception as e:
        st.error(f"Error in peak hours: {str(e)}")
        return None

def trip_status_trends(df):
    try:
        if 'Trip Status' not in df.columns or 'Trip Date' not in df.columns:
            return None
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
        return fig
    except Exception as e:
        st.error(f"Error in trip status trends: {str(e)}")
        return None

def customer_payment_methods(df):
    try:
        if 'Pay Mode' not in df.columns:
            return None
        payment_counts = df['Pay Mode'].value_counts()
        fig = px.pie(values=payment_counts.values, names=payment_counts.index, title="Customer Payment Methods")
        return fig
    except Exception as e:
        st.error(f"Error in customer payment methods: {str(e)}")
        return None

def get_download_data(df, date_range):
    try:
        if df.empty or 'Trip Date' not in df.columns:
            return pd.DataFrame()
        start_date, end_date = date_range
        date_list = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
        daily_data = pd.DataFrame(index=date_list)
        daily_data.index.name = 'Date'

        if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns:
            completed_trips = df[df['Trip Status'] == 'Job Completed']
            daily_value = completed_trips.groupby(completed_trips['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].sum()
            for date in date_list:
                daily_data.loc[date, 'Total Value of Rides (UGX)'] = daily_value.get(date, 0.0)

        if 'Company Commission Cleaned' in df.columns:
            daily_commissions = df.groupby(df['Trip Date'].dt.date)['Company Commission Cleaned'].sum()
            for date in date_list:
                daily_data.loc[date, 'Total Rider Commissions Made per Day'] = daily_commissions.get(date, 0.0)

        if 'Trip Status' in df.columns:
            completed_counts = df[df['Trip Status'] == 'Job Completed'].groupby(df['Trip Date'].dt.date).size()
            for date in date_list:
                daily_data.loc[date, 'Total # of Rides Completed per Day'] = completed_counts.get(date, 0)

        total_requests = df.groupby(df['Trip Date'].dt.date).size()
        for date in date_list:
            daily_data.loc[date, 'Total Requests'] = total_requests.get(date, 0)

        if 'Distance' in df.columns and 'Trip Status' in df.columns:
            completed_trips = df[df['Trip Status'] == 'Job Completed']
            daily_distance = completed_trips.groupby(completed_trips['Trip Date'].dt.date)['Distance'].mean()
            for date in date_list:
                daily_data.loc[date, 'Average Trip Distance (km)'] = daily_distance.get(date, 0.0)

        if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns:
            completed_trips = df[df['Trip Status'] == 'Job Completed']
            daily_price = completed_trips.groupby(completed_trips['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].mean()
            for date in date_list:
                daily_data.loc[date, 'Average Customer Price per Ride'] = daily_price.get(date, 0.0)

        return daily_data.reset_index()
    except Exception as e:
        st.error(f"Error in get download data: {str(e)}")
        return pd.DataFrame()

def print_console_summary(df, df_passengers, df_drivers, date_range, app_downloads, passenger_wallet_balance, riders_onboarded, driver_wallet_balance, commission_owed, retention_rate, passenger_ratio):
    logging.info("=== Ride-Hailing Metrics Summary ===")
    logging.info(f"Date Range: {date_range[0]} to {date_range[1]}")
    logging.info("\nPassenger Metrics:")
    logging.info(f"  - App Downloads: {app_downloads:,}")
    logging.info(f"  - Total Wallet Balance: {passenger_wallet_balance:,.0f} UGX")
    logging.info("\nDriver Metrics:")
    logging.info(f"  - Riders Onboarded: {riders_onboarded:,}")
    logging.info(f"  - Unique Drivers: {df['Driver'].nunique() if 'Driver' in df.columns else 0:,}")
    logging.info(f"  - Driver Wallet Balance: {driver_wallet_balance:,.0f} UGX")
    logging.info(f"  - Commission Owed: {commission_owed:,.0f} UGX")
    logging.info(f"  - Retention Rate: {retention_rate:.1f}%")
    logging.info(f"  - Passenger-to-Driver Ratio: {passenger_ratio:.1f}")
    logging.info("\nTrip Metrics:")
    total_requests = len(df)
    completed_trips = len(df[df['Trip Status'] == 'Job Completed']) if 'Trip Status' in df.columns else 0
    cancellation_rate = calculate_cancellation_rate(df)
    timeout_rate = calculate_passenger_search_timeout(df)
    avg_distance = df['Distance'].mean() if 'Distance' in df.columns else 0
    logging.info(f"  - Total Requests: {total_requests:,}")
    logging.info(f"  - Completed Trips: {completed_trips:,}")
    logging.info(f"  - Cancellation Rate: {cancellation_rate:.1f}%")
    logging.info(f"  - Search Timeout Rate: {timeout_rate:.1f}%")
    logging.info(f"  - Average Distance: {avg_distance:.1f} km")
    logging.info("\nFinancial Metrics:")
    total_revenue = df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum() if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else 0
    total_commission = df['Company Commission Cleaned'].sum() if 'Company Commission Cleaned' in df.columns else 0
    avg_revenue_per_trip = df['Trip Pay Amount Cleaned'].mean() if 'Trip Pay Amount Cleaned' in df.columns else 0
    revenue_share = (total_commission / total_revenue * 100) if total_revenue > 0 else 0
    logging.info(f"  - Total Revenue: {total_revenue:,.0f} UGX")
    logging.info(f"  - Total Commission: {total_commission:,.0f} UGX")
    logging.info(f"  - Average Revenue per Trip: {avg_revenue_per_trip:,.0f} UGX")
    logging.info(f"  - Revenue Share: {revenue_share:.1f}%")
    logging.info("\nGeographic Insights:")
    top_pickup = df['Pickup Location'].value_counts().index[0] if 'Pickup Location' in df.columns and not df['Pickup Location'].value_counts().empty else "N/A"
    top_dropoff = df['Dropoff Location'].value_counts().index[0] if 'Dropoff Location' in df.columns and not df['Dropoff Location'].value_counts().empty else "N/A"
    peak_hour = df['Trip Hour'].value_counts().index[0] if 'Trip Hour' in df.columns and not df['Trip Hour'].value_counts().empty else "N/A"
    logging.info(f"  - Top Pickup Location: {top_pickup}")
    logging.info(f"  - Top Dropoff Location: {top_dropoff}")
    logging.info(f"  - Peak Hour: {peak_hour}:00")
    logging.info("\nKey Insights and Recommendations:")
    if cancellation_rate and cancellation_rate > 10:
        logging.info("  - High cancellation rate detected (>10%). Consider driver incentives.")
    if timeout_rate and timeout_rate > 5:
        logging.info("  - Significant search timeouts (>5%). Increase driver availability.")
    if retention_rate < 50:
        logging.info("  - Low driver retention rate (<50%). Enhance driver support.")
    if revenue_share < 20:
        logging.info("  - Low revenue share (<20%). Review commission structure.")
    logging.info("=== End of Summary ===")

def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed, grouped_metrics=None):
    try:
        class PDF(FPDF):
            def header(self):
                try:
                    if os.path.exists(LOGO_PATH):
                        self.image(LOGO_PATH, x=5, y=4, w=19)
                except Exception as e:
                    self.set_font('Arial', 'I', 8)
                    self.cell(0, 10, f'Could not load logo: {str(e)}', 0, 1, 'L')
                self.set_font('Arial', 'B', 12)
                self.cell(0, 10, 'Union App Metrics Report', 0, 1, 'C')
                self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

            def add_section_title(self, title):
                self.set_font('Arial', 'B', 12)
                self.cell(0, 10, title, 0, 1)
                self.ln(2)

            def add_metric(self, label, value, explanation):
                self.set_font('Arial', '', 12)
                self.cell(0, 8, f"{label}: {value}", 0, 1)
                self.set_font('Arial', 'I', 10)
                self.multi_cell(0, 6, explanation)
                self.ln(2)

        pdf = PDF()
        pdf.add_page()
        pdf.set_font('Arial', '', 12)

        start_date_str = date_range[0].strftime('%Y-%m-%d') if date_range else 'N/A'
        end_date_str = date_range[1].strftime('%Y-%m-%d') if date_range else 'N/A'
        pdf.cell(0, 10, f"Date Range: {start_date_str} to {end_date_str}", 0, 1, 'C')
        pdf.ln(5)

        if grouped_metrics:
            for group_name, metrics in grouped_metrics.items():
                pdf.add_section_title(group_name)
                for metric, viz in metrics:
                    value = metric_functions[metric](df, df_passengers, df_drivers)
                    pdf.add_metric(metric, value, f"Visualization: {viz}")
        else:
            pdf.add_section_title("Trips Overview")
            total_requests = int(len(df))
            completed_trips = int(len(df[df['Trip Status'] == 'Job Completed'])) if 'Trip Status' in df.columns else 0
            avg_distance = f"{df['Distance'].mean():.1f} km" if 'Distance' in df.columns else "N/A"
            cancellation_rate = calculate_cancellation_rate(df)
            cancellation_rate_str = f"{cancellation_rate:.1f}%" if cancellation_rate is not None else "N/A"
            timeout_rate = calculate_passenger_search_timeout(df)
            timeout_rate_str = f"{timeout_rate:.1f}%" if timeout_rate is not None else "N/A"
            avg_trips_per_driver = f"{df.groupby('Driver').size().mean():.1f}" if 'Driver' in df.columns and not df.empty else "N/A"
            total_distance_covered = f"{df[df['Trip Status'] == 'Job Completed']['Distance'].sum():,.0f} km" if 'Distance' in df.columns and 'Trip Status' in df.columns else "N/A"
            avg_revenue_per_trip = f"{df['Trip Pay Amount Cleaned'].mean():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns else "N/A"
            total_commission = f"{df['Company Commission Cleaned'].sum():,.0f} UGX" if 'Company Commission Cleaned' in df.columns else "N/A"

            pdf.add_metric("Total Requests", total_requests, "Measures total demand for rides.")
            pdf.add_metric("Completed Trips", completed_trips, "Counts successful trips.")
            pdf.add_metric("Average Distance", avg_distance, "Average distance per trip.")
            pdf.add_metric("Driver Cancellation Rate", cancellation_rate_str, "Percentage of trips cancelled by drivers.")
            pdf.add_metric("Passenger Search Timeout", timeout_rate_str, "Percentage of trips expiring.")
            pdf.add_metric("Average Trips per Driver", avg_trips_per_driver, "Mean trips per driver.")
            pdf.add_metric("Passenger App Downloads", int(app_downloads), "Total app installations.")
            pdf.add_metric("Riders Onboarded", int(riders_onboarded), "Number of drivers registered.")
            pdf.add_metric("Total Distance Covered", total_distance_covered, "Sum of distances for completed trips.")
            pdf.add_metric("Average Revenue per Trip", avg_revenue_per_trip, "Mean revenue per trip.")
            pdf.add_metric("Total Commission", total_commission, "Sum of commissions earned.")

            pdf.add_section_title("Financial Performance")
            total_revenue = f"{df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else "N/A"
            gross_profit = f"{df['Company Commission Cleaned'].sum():,.0f} UGX" if 'Company Commission Cleaned' in df.columns else "N/A"
            pdf.add_metric("Total Value of Rides", total_revenue, "Total revenue from completed trips.")
            pdf.add_metric("Gross Profit", gross_profit, "Total commission earned.")

        return pdf
    except Exception as e:
        st.error(f"Error in create metrics pdf: {str(e)}")
        return FPDF()

def generate_html_report(grouped_metrics, date_range, df):
    try:
        html_content = """
        <html>
        <head>
            <title>Ride-Hailing Metrics Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { text-align: center; }
                h2 { color: #333; }
                .metric { margin: 10px 0; }
                .section { margin-bottom: 30px; }
                .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            </style>
        </head>
        <body>
            <h1>Ride-Hailing Metrics Report</h1>
            <p style="text-align: center;">Date Range: {start_date} to {end_date}</p>
        """

        start_date = date_range[0].strftime('%Y-%m-%d') if date_range else "N/A"
        end_date = date_range[1].strftime('%Y-%m-%d') if date_range else "N/A"
        html_content = html_content.format(start_date=start_date, end_date=end_date)

        for group_name, metrics in grouped_metrics.items():
            html_content += f'<div class="section"><h2>{group_name}</h2><div class="grid">'
            for metric, viz in metrics:
                html_content += '<div class="metric">'
                value = metric_functions[metric](df, df_passengers, df_drivers)
                html_content += f'<h3>{metric}</h3><p>{value}</p>'
                html_content += '</div>'
            html_content += '</div></div>'

        html_content += '</body></html>'
        return html_content
    except Exception as e:
        st.error(f"Error in generate html report: {str(e)}")
        return "<html><body>Error generating report</body></html>"

# Metric functions mapping
metric_functions = {
    "Passenger App Downloads": lambda df, df_p, df_d: f"{passenger_metrics(df_p)[0]:,}",
    "Passenger Wallet Balance": lambda df, df_p, df_d: f"{passenger_metrics(df_p)[1]:,.0f} UGX",
    "Riders Onboarded": lambda df, df_p, df_d: f"{driver_metrics(df_d)[0]:,}",
    "Driver Wallet Balance": lambda df, df_p, df_d: f"{driver_metrics(df_d)[1]:,.0f} UGX",
    "Commission Owed": lambda df, df_p, df_d: f"{driver_metrics(df_d)[2]:,.0f} UGX",
    "Driver Retention Rate": lambda df, df_p, df_d: f"{calculate_driver_retention_rate(driver_metrics(df_d)[0], passenger_metrics(df_p)[0], df['Driver'].nunique() if 'Driver' in df.columns else 0)[0]:.1f}%",
    "Passenger-to-Driver Ratio": lambda df, df_p, df_d: f"{calculate_driver_retention_rate(driver_metrics(df_d)[0], passenger_metrics(df_p)[0], df['Driver'].nunique() if 'Driver' in df.columns else 0)[1]:.1f}",
    "Total Requests": lambda df, df_p, df_d: f"{len(df):,}",
    "Completed Trips": lambda df, df_p, df_d: f"{len(df[df['Trip Status'] == 'Job Completed']) if 'Trip Status' in df.columns else 0:,}",
    "Cancellation Rate": lambda df, df_p, df_d: f"{calculate_cancellation_rate(df):.1f}%" if calculate_cancellation_rate(df) is not None else "N/A",
    "Search Timeout Rate": lambda df, df_p, df_d: f"{calculate_passenger_search_timeout(df):.1f}%" if calculate_passenger_search_timeout(df) is not None else "N/A",
    "Average Distance": lambda df, df_p, df_d: f"{df['Distance'].mean():.1f} km" if 'Distance' in df.columns else "N/A",
    "Total Distance Covered": total_distance_covered,
    "Total Revenue": lambda df, df_p, df_d: f"{df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else "N/A",
    "Total Commission": total_commission,
    "Average Revenue per Trip": avg_revenue_per_trip,
    "Average Commission per Trip": avg_commission_per_trip,
    "Revenue Share": revenue_share,
    "Average Revenue per Driver": revenue_per_driver,
    "Average Driver Earnings per Trip": driver_earnings_per_trip,
    "Average Fare per KM": fare_per_km,
    "Trip Status Distribution": total_trips_by_status,
    "Daily Trip Status Breakdown": completed_vs_cancelled_daily,
    "Daily Revenue Trend": revenue_by_day,
    "Revenue by Payment Method": payment_method_revenue,
    "Distance vs Revenue": distance_vs_revenue_scatter,
    "Weekday vs Weekend Revenue": weekday_vs_weekend_analysis,
    "Top 5 Drivers by Revenue": top_drivers_by_revenue,
    "Top 10 Drivers by Earnings": top_10_drivers_by_earnings,
    "Driver Performance Comparison": driver_performance_comparison,
    "Passenger Trip Frequency": passenger_insights,
    "Top 5 Pickup Locations": most_frequent_locations,
    "Trip Distribution by Hour": peak_hours,
    "Customer Payment Methods": customer_payment_methods,
    "Trip Status Trends": trip_status_trends
}

# Streamlit App
st.title("Ride-Hailing Metrics Dashboard")

# Sidebar for date range and file uploads
st.sidebar.header("Data Uploads")
uploaded_passengers = st.sidebar.file_uploader("Upload PASSENGERS.xlsx", type="xlsx")
uploaded_drivers = st.sidebar.file_uploader("Upload DRIVERS.xlsx", type="xlsx")
uploaded_data = st.sidebar.file_uploader("Upload BEER.xlsx", type="xlsx")
uploaded_transactions = st.sidebar.file_uploader("Upload TRANSACTIONS.xlsx", type="xlsx")
uploaded_union_staff = st.sidebar.file_uploader("Upload UNION STAFF.xlsx", type="xlsx")
uploaded_logo = st.sidebar.file_uploader("Upload TUTU.png", type="png")

# Save uploaded files
if uploaded_passengers:
    with open(PASSENGERS_FILE_PATH, "wb") as f:
        f.write(uploaded_passengers.read())
if uploaded_drivers:
    with open(DRIVERS_FILE_PATH, "wb") as f:
        f.write(uploaded_drivers.read())
if uploaded_data:
    with open(DATA_FILE_PATH, "wb") as f:
        f.write(uploaded_data.read())
if uploaded_transactions:
    with open(TRANSACTIONS_FILE_PATH, "wb") as f:
        f.write(uploaded_transactions.read())
if uploaded_union_staff:
    with open(UNION_STAFF_FILE_PATH, "wb") as f:
        f.write(uploaded_union_staff.read())
if uploaded_logo:
    with open(LOGO_PATH, "wb") as f:
        f.write(uploaded_logo.read())

st.sidebar.header("Filters")
default_end = datetime.today().date()
default_start = default_end - timedelta(days=30)
start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", default_end)
date_range = [start_date, end_date] if start_date and end_date else None

# Load data
df = load_data()
df_passengers = load_passengers_data(date_range)
df_drivers = load_drivers_data(date_range)

# Filter main dataframe by date range
if date_range and not df.empty:
    df = df[(df['Trip Date'].dt.date >= start_date) & (df['Trip Date'].dt.date <= end_date)]

# Calculate metrics
app_downloads, passenger_wallet_balance = passenger_metrics(df_passengers)
riders_onboarded, driver_wallet_balance, commission_owed = driver_metrics(df_drivers)
unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
retention_rate, passenger_ratio = calculate_driver_retention_rate(riders_onboarded, app_downloads, unique_drivers)

# Print console summary
print_console_summary(df, df_passengers, df_drivers, date_range, app_downloads, passenger_wallet_balance, riders_onboarded, driver_wallet_balance, commission_owed, retention_rate, passenger_ratio)

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Overview", "Financial Metrics", "Driver Performance", "Passenger Insights", "Geographic Analysis", "Custom Report Builder"])

with tab1:
    st.header("Overview")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Passenger App Downloads", app_downloads)
        st.metric("Riders Onboarded", riders_onboarded)
    with col2:
        st.metric("Unique Drivers", unique_drivers)
        st.metric("Driver Retention Rate", f"{retention_rate:.1f}%")
    with col3:
        st.metric("Passenger-to-Driver Ratio", f"{passenger_ratio:.1f}")
        trips_per_driver(df)
    
    st.subheader("Trip Status")
    fig = total_trips_by_status(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    fig = completed_vs_cancelled_daily(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Trip Trends")
    fig = trip_status_trends(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.header("Financial Metrics")
    col1, col2, col3 = st.columns(3)
    with col1:
        total_commission(df)
        gross_profit(df)
        avg_commission_per_trip(df)
    with col2:
        avg_revenue_per_trip(df)
        revenue_per_driver(df)
        driver_earnings_per_trip(df)
    with col3:
        fare_per_km(df)
        revenue_share(df)
        st.metric("Passenger Wallet Balance", f"{passenger_wallet_balance:,.0f} UGX")
        st.metric("Driver Wallet Balance", f"{driver_wallet_balance:,.0f} UGX")
        st.metric("Commission Owed", f"{commission_owed:,.0f} UGX")
    
    st.subheader("Revenue Trends")
    fig = revenue_by_day(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    fig = payment_method_revenue(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    fig = distance_vs_revenue_scatter(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    fig = weekday_vs_weekend_analysis(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    st.header("Driver Performance")
    col1, col2 = st.columns(2)
    with col1:
        fig = top_drivers_by_revenue(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        fig = top_10_drivers_by_earnings(df)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Driver Performance Comparison")
    fig = driver_performance_comparison(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.header("Passenger Insights")
    fig = passenger_insights(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Union Staff Trips")
    if os.path.exists(UNION_STAFF_FILE_PATH):
        union_staff = pd.read_excel(UNION_STAFF_FILE_PATH).iloc[:, 0].dropna().tolist()
        staff_trips = get_completed_trips_by_union_passengers(df, union_staff)
        if not staff_trips.empty:
            st.dataframe(staff_trips)
        else:
            st.info("No completed trips by union staff found.")
    else:
        st.warning("UNION STAFF.xlsx file not found.")

with tab5:
    st.header("Geographic Analysis")
    fig = most_frequent_locations(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Peak Hours")
    fig = peak_hours(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Payment Methods")
    fig = customer_payment_methods(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)

with tab6:
    st.header("Custom Report Builder")
    st.write("Create a personalized report by grouping metrics and selecting visualizations.")

    # Metric Grouping
    st.subheader("Metric Grouping")
    if 'metric_groups' not in st.session_state:
        st.session_state.metric_groups = {
            "Financial": [
                ("Total Revenue", "Text"),
                ("Total Commission", "Text"),
                ("Revenue Share", "Text")
            ],
            "Operational": [
                ("Total Requests", "Text"),
                ("Completed Trips", "Text"),
                ("Cancellation Rate", "Text")
            ]
        }

    group_name = st.text_input("Add/Edit Group Name")
    if st.button("Add Group"):
        if group_name and group_name not in st.session_state.metric_groups:
            st.session_state.metric_groups[group_name] = []
            st.success(f"Group '{group_name}' added.")

    selected_group = st.selectbox("Select Group to Edit", list(st.session_state.metric_groups.keys()))
    available_metrics = list(metric_functions.keys())
    selected_metrics = st.multiselect(f"Metrics for {selected_group}", available_metrics, key=f"metrics_{selected_group}")

    visualization_options = ["Text", "Bar", "Pie", "Line", "Scatter"]
    group_visualizations = []
    for metric in selected_metrics:
        default_viz = "Text" if metric in ["Passenger App Downloads", "Passenger Wallet Balance", "Riders Onboarded", "Driver Wallet Balance", "Commission Owed", "Driver Retention Rate", "Passenger-to-Driver Ratio", "Total Requests", "Completed Trips", "Cancellation Rate", "Search Timeout Rate", "Average Distance", "Total Revenue", "Average Revenue per Trip", "Average Commission per Trip", "Revenue Share", "Average Revenue per Driver", "Average Driver Earnings per Trip", "Average Fare per KM"] else "Pie"
        viz = st.selectbox(f"Visualization for {metric} in {selected_group}", visualization_options, index=visualization_options.index(default_viz), key=f"viz_{metric}_{selected_group}")
        group_visualizations.append(viz)

    if st.button("Update Group"):
        st.session_state.metric_groups[selected_group] = list(zip(selected_metrics, group_visualizations))
        st.success(f"Group '{selected_group}' updated.")

    if st.button("Delete Group"):
        if selected_group in st.session_state.metric_groups:
            del st.session_state.metric_groups[selected_group]
            st.success(f"Group '{selected_group}' deleted.")

    # Dynamic Layout
    st.subheader("Dynamic Layout")
    st.write("Select the order of metrics for the report layout.")
    sortable_items = []
    for group_name, metrics in st.session_state.metric_groups.items():
        for metric, viz in metrics:
            sortable_items.append({
                "id": f"{group_name}_{metric}",
                "title": f"{group_name}: {metric} ({viz})"
            })

    layout_order = st.multiselect(
        "Metric Order",
        [item["id"] for item in sortable_items],
        default=[item["id"] for item in sortable_items],
        key="layout_order"
    )

    # Preview
    if st.button("Preview Report"):
        st.subheader("Report Preview")
        for item_id in layout_order:
            group_name, metric = item_id.split("_", 1)
            viz = next(v for m, v in st.session_state.metric_groups[group_name] if m == metric)
            st.write(f"**{group_name}: {metric}**")
            if viz == "Text":
                value = metric_functions[metric](df, df_passengers, df_drivers)
                st.write(value)
            else:
                fig = metric_functions[metric](df, df_passengers, df_drivers)
                if fig:
                    if viz == "Bar" and fig.data[0].type != "bar":
                        fig = px.bar(x=fig.data[0].x, y=fig.data[0].y, title=metric)
                    elif viz == "Pie" and fig.data[0].type != "pie":
                        fig = px.pie(names=fig.data[0].x, values=fig.data[0].y, title=metric)
                    elif viz == "Line" and fig.data[0].type != "scatter":
                        fig = px.line(x=fig.data[0].x, y=fig.data[0].y, title=metric)
                    elif viz == "Scatter" and fig.data[0].type != "scatter":
                        fig = px.scatter(x=fig.data[0].x, y=fig.data[0].y, title=metric)
                    st.plotly_chart(fig, use_container_width=True)

    # Export Options
    st.subheader("Export Report")
    export_format = st.radio("Export Format", ["PDF", "HTML"])

    if st.button("Generate Report"):
        grouped_metrics = st.session_state.metric_groups
        if export_format == "PDF":
            pdf = create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed, grouped_metrics)
            pdf_buffer = BytesIO()
            pdf_output = pdf.output(dest='S').encode('latin1')
            pdf_buffer.write(pdf_output)
            pdf_buffer.seek(0)
            st.download_button(
                label="Download PDF Report",
                data=pdf_buffer,
                file_name="custom_metrics_report.pdf",
                mime="application/pdf"
            )
        
        elif export_format == "HTML":
            html_content = generate_html_report(grouped_metrics, date_range, df)
            html_buffer = BytesIO()
            html_buffer.write(html_content.encode('utf-8'))
            html_buffer.seek(0)
            st.download_button(
                label="Download HTML Report",
                data=html_buffer,
                file_name="custom_metrics_report.html",
                mime="text/html"
            )

# Sidebar export
st.sidebar.header("Export Data")
if not df.empty:
    daily_data = get_download_data(df, date_range)
    if not daily_data.empty:
        csv = daily_data.to_csv(index=False)
        st.sidebar.download_button(
            label="Download Daily Metrics (CSV)",
            data=csv,
            file_name="daily_metrics.csv",
            mime="text/csv"
        )

    pdf = create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed)
    pdf_buffer = BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin1')
    pdf_buffer.write(pdf_output)
    pdf_buffer.seek(0)
    st.sidebar.download_button(
        label="Download Metrics Report (PDF)",
        data=pdf_buffer,
        file_name="metrics_report.pdf",
        mime="application/pdf"
    )
else:
    st.sidebar.warning("No data available to export.")
