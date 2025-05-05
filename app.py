import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import pydeck as pdk
import requests
import os
import re
from dotenv import load_dotenv
import io
from fpdf import FPDF
import base64
import uuid

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
    .stPlotlyChart, .stPydeckChart, .stDataFrame {
        background-color: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# File paths
PASSENGERS_FILE_PATH = r"./PASSENGERS.xlsx"
DRIVERS_FILE_PATH = r"./DRIVERS.xlsx"
DATA_FILE_PATH = r"./BEER.xlsx"
TRANSACTIONS_FILE_PATH = r"./TRANSACTIONS.xlsx"
UNION_STAFF_FILE_PATH = r"./UNION STAFF.xlsx"

# Enhanced function to extract UGX amounts
def extract_ugx_amount(value):
    try:
        if pd.isna(value) or value is None:
            return 0.0
        value_str = str(value).replace('UGX', '').replace(',', '').strip()
        amounts = re.findall(r'[\d]+(?:\.\d+)?', value_str)
        if amounts:
            return float(amounts[0])
        if value_str.replace('.', '').isdigit():
            return float(value_str)
        return 0.0
    except (ValueError, TypeError):
        return 0.0

# Load passengers data
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

# Load drivers data
def load_drivers_data(date_range=None):
    try:
        df = pd.read_excel(DRIVERS_FILE_PATH)
        df['Created'] = pd.to_datetime(df['Created'], errors='coerce')
        if 'Wallet Balance' in df.columns:
            df['Wallet Balance'] = df['Wallet Balance'].apply(extract_ugx_amount)
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['Created'].dt.date >= start_date) &
                    (df['Created'].dt.date <= end_date)]
        return df
    except Exception as e:
        st.error(f"Error loading drivers data: {str(e)}")
        return pd.DataFrame()

# Load transactions data
def load_transactions_data():
    try:
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

# Load main data
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
        df['Trip Pay Amount Cleaned'] = df.get('Trip Pay Amount', 0).apply(extract_ugx_amount)
        df['Distance'] = pd.to_numeric(df.get('Trip Distance (KM/Mi)', 0), errors='coerce').fillna(0)
        df['Company Commission Cleaned'] = df.get('Company Commission Cleaned', 0.0)
        df['Pay Mode'] = df.get('Pay Mode', 'Unknown')
        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()

# Metrics functions
def passenger_metrics(df_passengers):
    app_downloads = len(df_passengers)
    passenger_wallet_balance = float(df_passengers['Wallet Balance'].sum()) if 'Wallet Balance' in df_passengers.columns else 0.0
    return app_downloads, passenger_wallet_balance

def driver_metrics(df_drivers):
    riders_onboarded = len(df_drivers)
    driver_wallet_balance = float(df_drivers[df_drivers['Wallet Balance'] > 0]['Wallet Balance'].sum()) if 'Wallet Balance' in df_drivers.columns else 0.0
    commission_owed = float(df_drivers[df_drivers['Wallet Balance'] < 0]['Wallet Balance'].abs().sum()) if 'Wallet Balance' in df_drivers.columns else 0.0
    return riders_onboarded, driver_wallet_balance, commission_owed

def calculate_driver_retention_rate(riders_onboarded, app_downloads, unique_drivers):
    retention_rate = (unique_drivers / riders_onboarded * 100) if riders_onboarded > 0 else 0.0
    passenger_ratio = (app_downloads / unique_drivers) if unique_drivers > 0 else 0.0
    return float(retention_rate), float(passenger_ratio)

# Other functions
def calculate_cancellation_rate(df):
    if 'Trip Status' not in df.columns:
        return None
    total_trips = len(df)
    cancelled_trips = len(df[df['Trip Status'].str.contains('Cancel', case=False, na=False)])
    return (cancelled_trips / total_trips * 100) if total_trips > 0 else 0.0

def calculate_passenger_search_timeout(df):
    if 'Trip Status' not in df.columns:
        return None
    total_trips = len(df)
    timeout_trips = len(df[df['Trip Status'].str.contains('Timeout', case=False, na=False)])
    return (timeout_trips / total_trips * 100) if total_trips > 0 else 0.0

def completed_vs_cancelled_daily(df):
    if 'Trip Status' not in df.columns or 'Trip Date' not in df.columns:
        return None
    status_df = df.groupby([df['Trip Date'].dt.date, 'Trip Status']).size().unstack(fill_value=0)
    fig = go.Figure()
    for status in status_df.columns:
        fig.add_trace(go.Scatter(
            x=status_df.index,
            y=status_df[status],
            name=status,
            mode='lines+markers'
        ))
    fig.update_layout(
        title="Daily Trip Status Breakdown",
        xaxis_title="Date",
        yaxis_title="Number of Trips",
        template="plotly_white"
    )
    return fig

def trips_per_driver(df):
    if 'Driver' not in df.columns:
        st.metric("Trips per Driver", "N/A")
        return
    trips_by_driver = df.groupby('Driver').size()
    avg_trips = trips_by_driver.mean() if not trips_by_driver.empty else 0
    st.metric("Avg. Trips per Driver", f"{avg_trips:.1f}", help="Average number of trips completed per driver. Higher values indicate active drivers, typical in urban ride-hailing markets.")

def total_trips_by_status(df):
    if 'Trip Status' not in df.columns:
        return
    status_counts = df['Trip Status'].value_counts()
    fig = px.pie(
        values=status_counts.values,
        names=status_counts.index,
        title="Trip Status Distribution"
    )
    st.plotly_chart(fig, use_container_width=True)

def total_distance_covered(df):
    if 'Distance' not in df.columns:
        return
    total_distance = df['Distance'].sum()
    st.metric("Total Distance Covered", f"{total_distance:,.0f} km", help="Total kilometers traveled across all trips. Useful for assessing operational scale and fuel efficiency.")

def revenue_by_day(df):
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

def avg_revenue_per_trip(df):
    if 'Trip Pay Amount Cleaned' not in df.columns:
        return
    avg_revenue = df['Trip Pay Amount Cleaned'].mean()
    st.metric("Avg. Revenue per Trip", f"{avg_revenue:,.0f} UGX", help="Average revenue per trip. Compare with previous periods to assess pricing strategy effectiveness.")

def total_commission(df):
    if 'Company Commission Cleaned' not in df.columns:
        st.metric("Total Commission", "N/A")
        return
    total_comm = df['Company Commission Cleaned'].sum()
    st.metric("Total Commission", f"{total_comm:,.0f} UGX", help="Total commission earned by the platform. Indicates platform profitability per trip.")

def avg_commission_per_trip(df):
    if 'Company Commission Cleaned' not in df.columns:
        return
    avg_comm = df['Company Commission Cleaned'].mean()
    st.metric("Avg. Commission per Trip", f"{avg_comm:,.0f} UGX", help="Average commission per trip. Higher values suggest better monetization per ride.")

def revenue_per_driver(df):
    if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
        return
    revenue_by_driver = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum()
    avg_revenue = revenue_by_driver.mean() if not revenue_by_driver.empty else 0
    st.metric("Avg. Revenue per Driver", f"{avg_revenue:,.0f} UGX", help="Average revenue generated per driver. Indicates driver productivity and market demand.")

def driver_earnings_per_trip(df):
    if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
        return
    df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
    avg_earnings = df['Driver Earnings'].mean()
    st.metric("Avg. Driver Earnings per Trip", f"{avg_earnings:,.0f} UGX", help="Average earnings per trip for drivers after commission. Critical for driver satisfaction and retention.")

def fare_per_km(df):
    if 'Trip Pay Amount Cleaned' not in df.columns or 'Distance' not in df.columns:
        return
    completed_trips = df[df['Trip Status'] == 'Job Completed']
    completed_trips['Fare per KM'] = completed_trips['Trip Pay Amount Cleaned'] / completed_trips['Distance'].replace(0, 1)
    avg_fare_per_km = completed_trips['Fare per KM'].mean()
    st.metric("Avg. Fare per KM", f"{avg_fare_per_km:,.0f} UGX", help="Average fare per kilometer for completed trips. Reflects pricing efficiency and market competitiveness.")

def revenue_share(df):
    if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
        return
    total_revenue = df['Trip Pay Amount Cleaned'].sum()
    total_commission = df['Company Commission Cleaned'].sum()
    revenue_share = (total_commission / total_revenue * 100) if total_revenue > 0 else 0
    st.metric("Revenue Share", f"{revenue_share:.1f}%", help="Percentage of revenue retained as commission. A key metric for platform sustainability.")

def total_trips_by_type(df):
    if 'Trip Type' not in df.columns:
        return
    type_counts = df['Trip Type'].value_counts()
    fig = px.bar(
        x=type_counts.index,
        y=type_counts.values,
        title="Trips by Type",
        labels={'x': 'Trip Type', 'y': 'Number of Trips'}
    )
    st.plotly_chart(fig, use_container_width=True)

def payment_method_revenue(df):
    if 'Pay Mode' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
        return
    completed_trips = df[df['Trip Status'] == 'Job Completed']
    revenue_by_payment = completed_trips.groupby('Pay Mode')['Trip Pay Amount Cleaned'].sum()
    fig = px.pie(
        values=revenue_by_payment.values,
        names=revenue_by_payment.index,
        title="Revenue by Payment Method (Completed Trips)"
    )
    st.plotly_chart(fig, use_container_width=True)

def distance_vs_revenue_scatter(df):
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

def weekday_vs_weekend_analysis(df):
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

def unique_driver_count(df):
    if 'Driver' not in df.columns:
        return
    unique_drivers = df['Driver'].nunique()
    st.metric("Unique Drivers", unique_drivers, help="Number of distinct drivers who completed trips. Indicates active driver base.")

def top_drivers_by_revenue(df):
    if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
        return
    top_drivers = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().nlargest(10).reset_index()
    top_drivers.columns = ['Driver', 'Total Revenue (UGX)']
    top_drivers['Total Revenue (UGX)'] = top_drivers['Total Revenue (UGX)'].apply(lambda x: f"{x:,.0f}")
    st.subheader("Top 10 Drivers by Revenue")
    st.dataframe(top_drivers, use_container_width=True)

def driver_performance_comparison(df):
    if 'Driver' not in df.columns:
        return
    driver_stats = df.groupby('Driver').agg({
        'Trip Pay Amount Cleaned': 'sum',
        'Distance': 'sum',
        'Trip Date': 'count'
    }).rename(columns={'Trip Date': 'Trip Count'}).reset_index()
    driver_stats.columns = ['Driver', 'Total Revenue (UGX)', 'Total Distance (km)', 'Trip Count']
    driver_stats['Total Revenue (UGX)'] = driver_stats['Total Revenue (UGX)'].apply(lambda x: f"{x:,.0f}")
    driver_stats['Total Distance (km)'] = driver_stats['Total Distance (km)'].apply(lambda x: f"{x:,.0f}")
    st.subheader("Driver Performance Comparison")
    st.dataframe(driver_stats, use_container_width=True)

def passenger_insights(df):
    if 'Passenger' not in df.columns:
        return
    passenger_trips = df.groupby('Passenger').size().value_counts().reset_index()
    passenger_trips.columns = ['Number of Trips', 'Number of Passengers']
    st.subheader("Passenger Trip Frequency")
    st.dataframe(passenger_trips, use_container_width=True)

def passenger_value_segmentation(df):
    if 'Passenger' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
        return
    passenger_revenue = df.groupby('Passenger')['Trip Pay Amount Cleaned'].sum()
    bins = pd.qcut(passenger_revenue, q=3, labels=['Low', 'Medium', 'High'], duplicates='drop')
    segment_counts = bins.value_counts().reset_index()
    segment_counts.columns = ['Segment', 'Number of Passengers']
    fig = px.pie(
        values=segment_counts['Number of Passengers'],
        names=segment_counts['Segment'],
        title="Passenger Value Segmentation"
    )
    st.plotly_chart(fig, use_container_width=True)

def top_10_drivers_by_earnings(df):
    if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
        return
    df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
    top_drivers = df.groupby('Driver')['Driver Earnings'].sum().nlargest(10).reset_index()
    top_drivers.columns = ['Driver', 'Total Earnings (UGX)']
    top_drivers['Total Earnings (UGX)'] = top_drivers['Total Earnings (UGX)'].apply(lambda x: f"{x:,.0f}")
    st.subheader("Top 10 Drivers by Earnings")
    st.dataframe(top_drivers, use_container_width=True)

def get_completed_trips_by_union_passengers(df, union_staff_names):
    if 'Passenger' not in df.columns or 'Trip Status' not in df.columns:
        return pd.DataFrame()
    staff_trips = df[
        (df['Passenger'].isin(union_staff_names)) &
        (df['Trip Status'] == 'Job Completed')
    ][['Passenger', 'Trip Date', 'Trip Pay Amount Cleaned', 'Distance']]
    staff_summary = staff_trips.groupby('Passenger').agg({
        'Trip Date': ['count', 'max'],
        'Trip Pay Amount Cleaned': 'sum',
        'Distance': 'sum'
    }).reset_index()
    staff_summary.columns = ['Passenger', 'Number of Trips', 'Last Trip Date', 'Total Revenue (UGX)', 'Total Distance (km)']
    staff_summary['Total Revenue (UGX)'] = staff_summary['Total Revenue (UGX)'].apply(lambda x: f"{x:,.0f}")
    staff_summary['Total Distance (km)'] = staff_summary['Total Distance (km)'].apply(lambda x: f"{x:,.0f}")
    staff_summary['Last Trip Date'] = staff_summary['Last Trip Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    return staff_summary

def most_frequent_locations(df):
    if 'Pickup Location' not in df.columns or 'Dropoff Location' not in df.columns:
        return
    col1, col2 = st.columns(2)
    with col1:
        pickup_counts = df['Pickup Location'].value_counts().head(10).reset_index()
        pickup_counts.columns = ['Pickup Location', 'Number of Trips']
        st.subheader("Top 10 Pickup Locations")
        st.dataframe(pickup_counts, use_container_width=True)
    with col2:
        dropoff_counts = df['Dropoff Location'].value_counts().head(5).reset_index()
        dropoff_counts.columns = ['Dropoff Location', 'Number of Trips']
        fig = px.bar(
            x=dropoff_counts['Number of Trips'],
            y=dropoff_counts['Dropoff Location'],
            orientation='h',
            title="Top 5 Dropoff Locations",
            labels={'x': 'Number of Trips', 'y': 'Location'}
        )
        st.plotly_chart(fig, use_container_width=True)

def peak_hours(df):
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

def trip_status_trends(df):
    if 'Trip Status' not in df.columns or 'Trip Date' not in df.columns:
        return
    status_trends = df.groupby([df['Trip Date'].dt.date, 'Trip Status']).size().unstack(fill_value=0).reset_index()
    fig = go.Figure()
    for status in status_trends.columns[1:]:
        fig.add_trace(go.Bar(
            x=status_trends['Trip Date'],
            y=status_trends[status],
            name=status
        ))
    fig.update_layout(
        title="Trip Status Trends Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Trips",
        barmode='stack',
        template="plotly_white"
    )
    st.plotly_chart(fig, use_container_width=True)

def customer_payment_methods(df):
    if 'Pay Mode' not in df.columns:
        return
    completed_trips = df[df['Trip Status'] == 'Job Completed']
    payment_counts = completed_trips['Pay Mode'].value_counts()
    fig = px.pie(
        values=payment_counts.values,
        names=payment_counts.index,
        title="Customer Payment Methods (Completed Trips)"
    )
    st.plotly_chart(fig, use_container_width=True)

def get_download_data(df):
    download_df = df[['Trip Date', 'Trip Status', 'Driver', 'Passenger', 'Trip Pay Amount Cleaned', 'Company Commission Cleaned', 'Distance', 'Pay Mode']].copy()
    download_df['Trip Date'] = download_df['Trip Date'].dt.strftime('%Y-%m-%d')
    return download_df

def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed):
    try:
        class PDF(FPDF):
            def header(self):
                self.image(r"./your_image.png", x=10, y=8, w=30)
                self.set_font('Arial', 'B', 12)
                self.cell(0, 10, 'Union App Metrics Report', 0, 1, 'C')
                self.ln(5)

            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 8)
                self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

        pdf = PDF()
        pdf.add_page()
        pdf.set_font('Arial', '', 12)

        start_date_str = date_range[0].strftime('%Y-%m-%d') if date_range and len(date_range) == 2 else 'N/A'
        end_date_str = date_range[1].strftime('%Y-%m-%d') if date_range and len(date_range) == 2 else 'N/A'
        pdf.cell(0, 10, f"Date Range: {start_date_str} to {end_date_str}", 0, 1)
        pdf.ln(5)

        total_trips = int(len(df))
        completed_trips = int(len(df[df['Trip Status'] == 'Job Completed'])) if 'Trip Status' in df.columns else 0
        total_revenue = float(df['Trip Pay Amount Cleaned'].sum()) if 'Trip Pay Amount Cleaned' in df.columns else 0.0
        total_commission = float(df['Company Commission Cleaned'].sum()) if 'Company Commission Cleaned' in df.columns else 0.0
        avg_distance = float(df['Distance'].mean()) if 'Distance' in df.columns else 0.0
        cancellation_rate = calculate_cancellation_rate(df) or 0.0
        timeout_rate = calculate_passenger_search_timeout(df) or 0.0
        avg_trips_per_driver = float(df.groupby('Driver').size().mean()) if 'Driver' in df.columns else 0.0
        avg_revenue_per_trip = float(df['Trip Pay Amount Cleaned'].mean()) if 'Trip Pay Amount Cleaned' in df.columns else 0.0
        avg_commission_per_trip = float(df['Company Commission Cleaned'].mean()) if 'Company Commission Cleaned' in df.columns else 0.0
        avg_revenue_per_driver = float(df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().mean()) if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns else 0.0
        df['Driver Earnings'] = df[' Lily Pay Amount Cleaned'] - df['Company Commission Cleaned'] if 'Trip Pay Amount Cleaned' in df.columns and 'Company Commission Cleaned' in df.columns else 0
        avg_driver_earnings = float(df['Driver Earnings'].mean()) if 'Driver Earnings' in df else 0.0
        completed_trips_df = df[df['Trip Status'] == 'Job Completed'] if 'Trip Status' in df.columns else df
        completed_trips_df['Fare per KM'] = completed_trips_df['Trip Pay Amount Cleaned'] / completed_trips_df['Distance'].replace(0, 1) if 'Trip Pay Amount Cleaned' in completed_trips_df.columns and 'Distance' in completed_trips_df.columns else 0
        avg_fare_per_km = float(completed_trips_df['Fare per KM'].mean()) if 'Fare per KM' in completed_trips_df else 0.0
        revenue_share = float((total_commission / total_revenue * 100) if total_revenue > 0 else 0)
        unique_drivers = int(df['Driver'].nunique()) if 'Driver' in df.columns else 0

        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Key Metrics", 0, 1)
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, f"Total Requests: {total_trips}", 0, 1)
        pdf.cell(0, 10, f"Completed Trips: {completed_trips}", 0, 1)
        pdf.cell(0, 10, f"Avg. Distance: {avg_distance:.1f} km", 0, 1)
        pdf.cell(0, 10, f"Driver Cancellation Rate: {cancellation_rate:.1f}%", 0, 1)
        pdf.cell(0, 10, f"Passenger Search Timeout: {timeout_rate:.1f}%", 0, 1)
        pdf.cell(0, 10, f"Avg. Trips per Driver: {avg_trips_per_driver:.1f}", 0, 1)
        pdf.cell(0, 10, f"Passenger App Downloads: {int(app_downloads)}", 0, 1)
        pdf.cell(0, 10, f"Riders Onboarded: {int(riders_onboarded)}", 0, 1)
        pdf.cell(0, 10, f"Total Value Of Rides: {total_revenue:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Total Commission: {total_commission:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Passenger Wallet Balance: {float(passenger_wallet_balance):,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Driver Wallet Balance: {float(driver_wallet_balance):,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Commission Owed: {float(commission_owed):,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Revenue per Trip: {avg_revenue_per_trip:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Commission per Trip: {avg_commission_per_trip:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Revenue per Driver: {avg_revenue_per_driver:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Driver Earnings per Trip: {avg_driver_earnings:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Avg. Fare per KM: {avg_fare_per_km:,.0f} UGX", 0, 1)
        pdf.cell(0, 10, f"Revenue Share: {revenue_share:.1f}%", 0, 1)
        pdf.cell(0, 10, f"Unique Drivers: {unique_drivers}", 0, 1)
        pdf.cell(0, 10, f"Driver Retention Rate: {float(retention_rate):,.1f}%", 0, 1)
        pdf.cell(0, 10, f"Passenger-to-Driver Ratio: {float(passenger_ratio):,.1f}", 0, 1)

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

        df = load_data()
        if not df.empty and 'Trip Date' in df.columns:
            min_date = df['Trip Date'].min().date()
            max_date = df['Trip Date'].max().date()

        # Custom date filters
        st.sidebar.subheader("Date Filter")
        filter_option = st.sidebar.selectbox(
            "Select Date Range",
            ["Today", "Yesterday", "Last 3 Days", "Last Week", "Custom Range", "Overall"]
        )

        today = datetime.now().date()
        if filter_option == "Today":
            date_range = [today, today]
        elif filter_option == "Yesterday":
            date_range = [today - timedelta(days=1), today - timedelta(days=1)]
        elif filter_option == "Last 3 Days":
            date_range = [today - timedelta(days=2), today]
        elif filter_option == "Last Week":
            date_range = [today - timedelta(days=6), today]
        elif filter_option == "Overall":
            date_range = [min_date, max_date]
        else:  # Custom Range
            date_range = st.sidebar.date_input(
                "Custom Date Range",
                value=[min_date, max_date],
                min_value=min_date,
                max_value=max_date
            )

        # Apply date filter
        if len(date_range) == 2:
            df = df[(df['Trip Date'].dt.date >= date_range[0]) &
                    (df['Trip Date'].dt.date <= date_range[1])]
            df_passengers = load_passengers_data(date_range)
            df_drivers = load_drivers_data(date_range)
        else:
            df_passengers = load_passengers_data()
            df_drivers = load_drivers_data()

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

        # Export data
        st.sidebar.markdown("---")
        st.sidebar.subheader("Export Data")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            get_download_data(df).to_excel(writer, sheet_name='Dashboard Data', index=False)
            load_passengers_data().to_excel(writer, sheet_name='Passengers', index=False)
            load_drivers_data().to_excel(writer, sheet_name='Drivers', index=False)
            load_transactions_data().to_excel(writer, sheet_name='Transactions', index=False)
            if os.path.exists(UNION_STAFF_FILE_PATH):
                pd.read_excel(UNION_STAFF_FILE_PATH).to_excel(writer, sheet_name='Union Staff', index=False)
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
                st.metric("Total Requests", len(df), help="Total trip requests made by passengers. Compare with previous periods to gauge demand growth.")
            with col2:
                completed_trips = len(df[df['Trip Status'] == 'Job Completed'])
                st.metric("Completed Trips", completed_trips, help="Number of trips successfully completed. High completion rates indicate reliable service.")
            with col3:
                st.metric("Avg. Distance", f"{df['Distance'].mean():.1f} km" if 'Distance' in df.columns else "N/A", help="Average trip distance. Longer trips may indicate inter-city travel or higher fares.")
            with col4:
                cancellation_rate = calculate_cancellation_rate(df)
                if cancellation_rate is not None:
                    st.metric("Driver Cancellation Rate", f"{cancellation_rate:.1f}%", help="Percentage of trips cancelled by drivers. High rates may signal driver dissatisfaction or operational issues.")
                else:
                    st.metric("Driver Cancellation Rate", "N/A")
            with col5:
                timeout_rate = calculate_passenger_search_timeout(df)
                if timeout_rate is not None:
                    st.metric("Passenger Search Timeout", f"{timeout_rate:.1f}%", help="Percentage of trips where no driver was found. Indicates supply-demand mismatch.")
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
                st.metric("Passenger App Downloads", app_downloads, help="Total passenger app downloads. Reflects market penetration and user acquisition.")
            with col8:
                st.metric("Riders Onboarded", riders_onboarded, help="Number of drivers onboarded. Indicates driver supply growth.")

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
                st.metric("Total Value Of Rides", f"{total_revenue:,.0f} UGX", help="Total revenue from all trips. Key indicator of business scale.")
            with col2:
                total_commission(df)
            with col3:
                st.metric("Passenger Wallet Balance", f"{passenger_wallet_balance:,.0f} UGX", help="Total balance in passenger wallets. Indicates potential for future rides.")

            col4, col5, col6 = st.columns(3)
            with col4:
                st.metric("Driver Wallet Balance", f"{driver_wallet_balance:,.0f} UGX", help="Sum of positive wallet balances for drivers. Reflects driver liquidity.")
            with col5:
                st.metric("Commission Owed", f"{commission_owed:,.0f} UGX", help="Sum of negative wallet balances, indicating amounts owed by drivers to the platform.")
            with col6:
                avg_commission_per_trip(df)

            col7, col8 = st.columns(2)
            with col7:
                revenue_per_driver(df)
            with col8:
                driver_earnings_per_trip(df)

            col9, col10 = st.columns(2)
            with col9:
                fare_per_km(df)
            with col10:
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
                st.metric("Passenger App Downloads", app_downloads, help="Total passenger app downloads. Compare with prior periods to track growth.")
            with col3:
                st.metric("Riders Onboarded", riders_onboarded, help="Total drivers onboarded. Indicates driver acquisition efforts.")

            col4, col5 = st.columns(2)
            with col4:
                st.metric("Driver Retention Rate", f"{retention_rate:.1f}%", help="Percentage of onboarded drivers who are active. High retention is critical for service reliability.")
            with col5:
                st.metric("Passenger-to-Driver Ratio", f"{passenger_ratio:.1f}", help="Ratio of passengers to active drivers. A balanced ratio ensures service availability.")

            top_drivers_by_revenue(df)
            driver_performance_comparison(df)
            passenger_insights(df)
            passenger_value_segmentation(df)
            top_10_drivers_by_earnings(df)

            st.markdown("---")
            st.subheader("Union Staff Trip Completion")
            if os.path.exists(UNION_STAFF_FILE_PATH):
                union_staff_df = pd.read_excel(UNION_STAFF_FILE_PATH)
                if union_staff_df.empty or union_staff_df.shape[1] == 0:
                    st.warning("Union Staff file is empty or does not contain columns.")
                else:
                    union_staff_names = union_staff_df.iloc[:, 0].dropna().astype(str).tolist()
                    st.metric("Total Union Staff Members", len(union_staff_names), help="Number of staff members in the Union Staff list.")
                    staff_trips_df = get_completed_trips_by_union_passengers(df, union_staff_names)
                    if not staff_trips_df.empty:
                        st.dataframe(staff_trips_df, use_container_width=True)
                    else:
                        st.info("No matching completed trips found for Union Staff members.")
            else:
                st.info(f"Union Staff file not found at: {UNION_STAFF_FILE_PATH}")

        with tab4:
            st.header("Geographic Analysis")
            most_frequent_locations(df)
            peak_hours(df)
            trip_status_trends(df)
            customer_payment_methods(df)

    except FileNotFoundError:
        st.error("Data file not found. Please ensure the Excel files are placed in the data/ directory.")
    except Exception as e:
        st.error(f"Error: {e}")

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    main()
