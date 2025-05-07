import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
import os
import re
from dotenv import load_dotenv
import io
from fpdf import FPDF

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
            df_drivers['Wallet Balance'] = pd.to_numeric(df_drivers['Wallet Balance'], errors='coerce').fillna(0.0)
            
            positive_balances = df_drivers[df_drivers['Wallet Balance'] > 0]['Wallet Balance']
            driver_wallet_balance = float(positive_balances.sum()) if not positive_balances.empty else 0.0
            
            negative_balances = df_drivers[df_drivers['Wallet Balance'] < 0]['Wallet Balance']
            commission_owed = float(negative_balances.abs().sum()) if not negative_balances.empty else 0.0
            
            st.info(f"Processed {len(positive_balances)} positive and {len(negative_balances)} negative wallet balances.")
        else:
            st.warning("No 'Wallet Balance' column found in drivers data.")
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
            st.metric("Avg. Trips per Driver", "N/A",
                      help="Average number of trips completed per driver (data unavailable).")
            return
        trips_by_driver = df.groupby('Driver').size()
        avg_trips = trips_by_driver.mean() if not trips_by_driver.empty else 0
        st.metric("Avg. Trips per Driver", f"{avg_trips:.1f}",
                  help="Average number of trips completed per driver.")
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
    except Exception as e:
        st.error(f"Error in total trips by status: {str(e)}")

def total_distance_covered(df):
    try:
        if 'Distance' not in df.columns or 'Trip Status' not in df.columns:
            st.metric("Total Distance Covered", "N/A",
                      help="Total distance covered by completed trips (data unavailable).")
            return
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        total_distance = completed_trips['Distance'].sum()
        st.metric("Total Distance Covered", f"{total_distance:,.0f} km",
                  help="Total distance covered by completed trips in kilometers.")
    except Exception as e:
        st.error(f"Error in total distance covered: {str(e)}")

def revenue_by_day(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Trip Date' not in df.columns:
            return
        daily_revenue = df.groupby(df['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].sum().reset_index()
        daily_revenue['Trip Date'] = daily_revenue['Trip Date'].astype(str)  # Ensure Trip Date is string for animation
        fig = px.line(
            daily_revenue,
            x='Trip Date',
            y='Trip Pay Amount Cleaned',
            title="Daily Revenue Trend",
            labels={'Trip Date': 'Date', 'Trip Pay Amount Cleaned': 'Revenue (UGX)'},
            animation_frame='Trip Date'  # Add animation
        )
        fig.update_traces(mode='lines+markers')
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error in revenue by day: {str(e)}")

def avg_revenue_per_trip(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns:
            st.metric("Avg. Revenue per Trip", "N/A",
                      help="Average revenue generated per trip (data unavailable).")
            return
        avg_revenue = df['Trip Pay Amount Cleaned'].mean()
        st.metric("Avg. Revenue per Trip", f"{avg_revenue:,.0f} UGX",
                  help="Average revenue generated per trip in UGX.")
    except Exception as e:
        st.error(f"Error in avg revenue per trip: {str(e)}")

def total_commission(df):
    try:
        if 'Company Commission Cleaned' not in df.columns:
            st.metric("Total Commission", "N/A",
                      help="Total commission earned by the company (data unavailable).")
            return
        total_comm = df['Company Commission Cleaned'].sum()
        st.metric("Total Commission", f"{total_comm:,.0f} UGX",
                  help="Total commission earned by the company from trips.")
    except Exception as e:
        st.error(f"Error in total commission: {str(e)}")

def gross_profit(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            st.metric("Gross Profit", "N/A",
                      help="Total commission earned, representing profit before expenses (data unavailable).")
            return
        gross_profit = df['Company Commission Cleaned'].sum()
        st.metric("Gross Profit", f"{gross_profit:,.0f} UGX",
                  help="Total commission earned, representing profit before expenses.")
    except Exception as e:
        st.error(f"Error in gross profit: {str(e)}")

def avg_commission_per_trip(df):
    try:
        if 'Company Commission Cleaned' not in df.columns:
            st.metric("Avg. Commission per Trip", "N/A",
                      help="Average commission earned per trip (data unavailable).")
            return
        avg_comm = df['Company Commission Cleaned'].mean()
        st.metric("Avg. Commission per Trip", f"{avg_comm:,.0f} UGX",
                  help="Average commission earned per trip in UGX.")
    except Exception as e:
        st.error(f"Error in avg commission per trip: {str(e)}")

def revenue_per_driver(df):
    try:
        if 'Driver' not in df.columns or 'Trip Pay Amount Cleaned' not in df.columns:
            st.metric("Avg. Revenue per Driver", "N/A",
                      help="Average revenue generated per driver (data unavailable).")
            return
        revenue_by_driver = df.groupby('Driver')['Trip Pay Amount Cleaned'].sum()
        avg_revenue = revenue_by_driver.mean() if not revenue_by_driver.empty else 0
        st.metric("Avg. Revenue per Driver", f"{avg_revenue:,.0f} UGX",
                  help="Average revenue generated per driver in UGX.")
    except Exception as e:
        st.error(f"Error in revenue per driver: {str(e)}")

def driver_earnings_per_trip(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            st.metric("Avg. Driver Earnings per Trip", "N/A",
                      help="Average earnings per trip for drivers after commission (data unavailable).")
            return
        df['Driver Earnings'] = df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']
        avg_earnings = df['Driver Earnings'].mean()
        st.metric("Avg. Driver Earnings per Trip", f"{avg_earnings:,.0f} UGX",
                  help="Average earnings per trip for drivers after commission in UGX.")
    except Exception as e:
        st.error(f"Error in driver earnings per trip: {str(e)}")

def fare_per_km(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Distance' not in df.columns or 'Trip Status' not in df.columns:
            st.metric("Avg. Fare per KM", "N/A",
                      help="Average revenue per kilometer for completed trips (data unavailable).")
            return
        completed_trips = df[df['Trip Status'] == 'Job Completed']
        completed_trips['Fare per KM'] = completed_trips['Trip Pay Amount Cleaned'] / completed_trips['Distance'].replace(0, 1)
        avg_fare_per_km = completed_trips['Fare per KM'].mean()
        st.metric("Avg. Fare per KM", f"{avg_fare_per_km:,.0f} UGX",
                  help="Average revenue per kilometer for completed trips in UGX.")
    except Exception as e:
        st.error(f"Error in fare per km: {str(e)}")

def revenue_share(df):
    try:
        if 'Trip Pay Amount Cleaned' not in df.columns or 'Company Commission Cleaned' not in df.columns:
            st.metric("Revenue Share", "N/A",
                      help="Percentage of revenue retained as commission (data unavailable).")
            return
        total_revenue = df['Trip Pay Amount Cleaned'].sum()
        total_commission = df['Company Commission Cleaned'].sum()
        revenue_share = (total_commission / total_revenue * 100) if total_revenue > 0 else 0
        st.metric("Revenue Share", f"{revenue_share:.1f}%",
                  help="Percentage of revenue retained as commission.")
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
    except Exception as e:
        st.error(f"Error in total trips by type: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in payment method revenue: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in distance vs revenue scatter: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in weekday vs weekend analysis: {str(e)}")

def unique_driver_count(df):
    try:
        if 'Driver' not in df.columns:
            st.metric("Unique Drivers", "N/A",
                      help="Number of distinct drivers who completed trips (data unavailable).")
            return
        unique_drivers = df['Driver'].nunique()
        st.metric("Unique Drivers", unique_drivers,
                  help="Number of distinct drivers who completed trips.")
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
    except Exception as e:
        st.error(f"Error in top drivers by revenue: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in driver performance comparison: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in passenger insights: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in top 10 drivers by earnings: {str(e)}")

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
        with col2:
            fig2 = px.bar(
                x=dropoff_counts.values,
                y=dropoff_counts.index,
                orientation='h',
                title="Top 5 Dropoff Locations",
                labels={'x': 'Number of Trips', 'y': 'Location'}
            )
            st.plotly_chart(fig2, use_container_width=True)
    except Exception as e:
        st.error(f"Error in most frequent locations: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in peak hours: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in trip status trends: {str(e)}")

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
    except Exception as e:
        st.error(f"Error in customer payment methods: {str(e)}")

def get_download_data(df, date_range):
    try:
        if df.empty or 'Trip Date' not in df.columns:
            return pd.DataFrame()

        start_date = date_range[0]
        end_date = date_range[1]
        date_list = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]

        daily_data = pd.DataFrame(index=date_list)
        daily_data.index.name = 'Date'

        if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns:
            completed_trips = df[df['Trip Status'] == 'Job Completed']
            daily_value = completed_trips.groupby(completed_trips['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].sum()
            for date in date_list:
                daily_data.loc[date, 'Total Value of Rides (local currency)'] = daily_value.get(date, 0.0)

        for date in date_list:
            daily_data.loc[date, 'Total Rider Subscriptions Made per Day'] = 0

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

        for date in date_list:
            daily_data.loc[date, 'Average Trip Time (minutes)'] = 0

        if 'Trip Status' in df.columns:
            daily_completion = df.groupby(df['Trip Date'].dt.date).apply(lambda x: calculate_cancellation_rate(x) if calculate_cancellation_rate(x) is not None else 0)
            for date in date_list:
                daily_data.loc[date, 'Completion Rate (ungrouped)'] = 100 - daily_completion.get(date, 0.0) if not pd.isna(daily_completion.get(date, 0.0)) else 0.0

        if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns:
            completed_trips = df[df['Trip Status'] == 'Job Completed']
            daily_price = completed_trips.groupby(completed_trips['Trip Date'].dt.date)['Trip Pay Amount Cleaned'].mean()
            for date in date_list:
                daily_data.loc[date, 'Average Customer Price per Ride'] = daily_price.get(date, 0.0)

        if 'Trip Pay Amount Cleaned' in df.columns and 'Distance' in df.columns and 'Trip Status' in df.columns:
            completed_trips = df[df['Trip Status'] == 'Job Completed']
            completed_trips['Fare per KM'] = completed_trips['Trip Pay Amount Cleaned'] / completed_trips['Distance'].replace(0, 1)
            daily_fare_per_km = completed_trips.groupby(completed_trips['Trip Date'].dt.date)['Fare per KM'].mean()
            for date in date_list:
                daily_data.loc[date, 'Average Customer Price per Kilometer'] = daily_fare_per_km.get(date, 0.0)

        for date in date_list:
            daily_data.loc[date, 'Average Price per Kilometer'] = daily_data.loc[date, 'Average Customer Price per Kilometer']

        if 'Driver' in df.columns:
            daily_drivers = df.groupby(df['Trip Date'].dt.date)['Driver'].nunique()
            for date in date_list:
                daily_data.loc[date, 'Daily Active Drivers'] = daily_drivers.get(date, 0)

        for date in date_list:
            daily_data.loc[date, 'First Time Active Riders'] = 0

        if 'Passenger' in df.columns:
            cumulative_riders = df.groupby(df['Trip Date'].dt.date)['Passenger'].nunique().cumsum()
            for date in date_list:
                daily_data.loc[date, 'Total Cumulative Riders'] = cumulative_riders.get(date, 0)

        for date in date_list:
            daily_data.loc[date, '% of Riders Engaged'] = 0

        for date in date_list:
            daily_data.loc[date, '% of Suspended Riders'] = 0

        if 'Passenger' in df.columns:
            daily_orders = df.groupby([df['Trip Date'].dt.date, 'Passenger']).size().groupby(level=0).mean()
            for date in date_list:
                daily_data.loc[date, 'Order per Rider'] = daily_orders.get(date, 0.0)

        for date in date_list:
            daily_data.loc[date, 'Average Rider Earnings per Day'] = 0

        for date in date_list:
            daily_data.loc[date, 'Daily Online Riders'] = 0

        for date in date_list:
            daily_data.loc[date, 'Bike Riders Acceptance Rate'] = 0

        for date in date_list:
            daily_data.loc[date, 'Total Passenger app Downloads Per'] = 0

        return daily_data.reset_index()

    except Exception as e:
        st.error(f"Error in get download data: {str(e)}")
        return pd.DataFrame()

def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed):
    try:
        class PDF(FPDF):
            def header(self):
                try:
                    self.image(r"./TUTU.png", x=5, y=4, w=19)
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

        start_date_str = 'N/A'
        end_date_str = 'N/A'
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            try:
                start_date_str = start_date.strftime('%Y-%m-%d') if hasattr(start_date, 'strftime') else str(start_date)
                end_date_str = end_date.strftime('%Y-%m-%d') if hasattr(end_date, 'strftime') else str(end_date)
            except (AttributeError, TypeError):
                pass
        pdf.cell(0, 10, f"Date Range: {start_date_str} to {end_date_str}", 0, 1, 'C')
        pdf.ln(5)

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

        pdf.add_metric("Total Requests", total_requests, 
                       "Measures total demand for rides, including all trip requests.")
        pdf.add_metric("Completed Trips", completed_trips, 
                       "Counts successful trips from pickup to dropoff.")
        pdf.add_metric("Average Distance", avg_distance, 
                       "Average distance per trip.")
        pdf.add_metric("Driver Cancellation Rate", cancellation_rate_str, 
                       "Percentage of trips cancelled by drivers.")
        pdf.add_metric("Passenger Search Timeout", timeout_rate_str, 
                       "Percentage of trips expiring due to no driver acceptance.")
        pdf.add_metric("Average Trips per Driver", avg_trips_per_driver, 
                       "Mean trips per driver.")
        pdf.add_metric("Passenger App Downloads", int(app_downloads), 
                       "Total app installations.")
        pdf.add_metric("Riders Onboarded", int(riders_onboarded), 
                       "Number of drivers registered.")
        pdf.add_metric("Total Distance Covered", total_distance_covered, 
                       "Sum of distances for completed trips.")
        pdf.add_metric("Average Revenue per Trip", avg_revenue_per_trip, 
                       "Mean revenue per trip.")
        pdf.add_metric("Total Commission", total_commission, 
                       "Sum of commissions earned.")

        pdf.add_section_title("Financial Performance")
        total_revenue = f"{df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else "N/A"
        gross_profit = f"{df['Company Commission Cleaned'].sum():,.0f} UGX" if 'Company Commission Cleaned' in df.columns else "N/A"
        avg_commission_per_trip = f"{df['Company Commission Cleaned'].mean():,.0f} UGX" if 'Company Commission Cleaned' in df.columns else "N/A"
        avg_revenue_per_driver = f"{df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().mean():,.0f} UGX" if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns else "N/A"
        driver_earnings_per_trip = f"{(df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']).mean():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Company Commission Cleaned' in df.columns else "N/A"
        fare_per_km = f"{(df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'] / df[df['Trip Status'] == 'Job Completed']['Distance'].replace(0, 1)).mean():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Distance' in df.columns and 'Trip Status' in df.columns else "N/A"
        revenue_share = f"{(df['Company Commission Cleaned'].sum() / df['Trip Pay Amount Cleaned'].sum() * 100):.1f}%" if 'Trip Pay Amount Cleaned' in df.columns and 'Company Commission Cleaned' in df.columns and df['Trip Pay Amount Cleaned'].sum() > 0 else "N/A"

        pdf.add_metric("Total Value of Rides", total_revenue, 
                       "Total revenue from completed trips.")
        pdf.add_metric("Total Commission", total_commission, 
                       "Sum of commissions earned.")
        pdf.add_metric("Gross Profit", gross_profit, 
                       "Total commission earned.")
        pdf.add_metric("Passenger Wallet Balance", f"{float(passenger_wallet_balance):,.0f} UGX", 
                       "Total funds in passenger wallets.")
        pdf.add_metric("Driver Wallet Balance", f"{float(driver_wallet_balance):,.0f} UGX", 
                       "Total positive balances owed to drivers.")
        pdf.add_metric("Commission Owed", f"{float(commission_owed):,.0f} UGX", 
                       "Total negative driver balances.")
        pdf.add_metric("Average Commission per Trip", avg_commission_per_trip, 
                       "Mean commission per trip.")
        pdf.add_metric("Average Revenue per Driver", avg_revenue_per_driver, 
                       "Mean revenue per driver.")
        pdf.add_metric("Average Driver Earnings per Trip", driver_earnings_per_trip, 
                       "Mean driver earnings after commission.")
        pdf.add_metric("Average Fare per KM", fare_per_km, 
                       "Mean revenue per kilometer.")
        pdf.add_metric("Revenue Share", revenue_share, 
                       "Percentage of revenue retained as commission.")

        pdf.add_section_title("User Performance")
        unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
        retention_rate_str = f"{float(retention_rate):.1f}%" if retention_rate is not None else "N/A"
        passenger_ratio_str = f"{float(passenger_ratio):.1f}" if passenger_ratio is not None else "N/A"
        total_union_staff = len(pd.read_excel(UNION_STAFF_FILE_PATH).iloc[:, 0].dropna()) if os.path.exists(UNION_STAFF_FILE_PATH) else 0

        pdf.add_metric("Unique Drivers", unique_drivers, 
                       "Number of distinct drivers completing trips.")
        pdf.add_metric("Passenger App Downloads", int(app_downloads), 
                       "Total app installations.")
        pdf.add_metric("Riders Onboarded", int(riders_onboarded), 
                       "Number of drivers registered.")
        pdf.add_metric("Driver Retention Rate", retention_rate_str, 
                       "Percentage of onboarded drivers who are active.")
        pdf.add_metric("Passenger-to-Driver Ratio", passenger_ratio_str, 
                       "Number of passengers per active driver.")
        pdf.add_metric("Total Union Staff Members", total_union_staff, 
                       "Number of staff listed.")

        pdf.add_section_title("Geographic Analysis")
        top_pickup_location = df['Pickup Location'].value_counts().index[0] if 'Pickup Location' in df.columns and not df['Pickup Location'].value_counts().empty else "N/A"
        top_dropoff_location = df['Dropoff Location'].value_counts().index[0] if 'Dropoff Location' in df.columns and not df['Dropoff Location'].value_counts().empty else "N/A"
        peak_hour = f"{df['Trip Hour'].value_counts().index[0]}:00" if 'Trip Hour' in df.columns and not df['Trip Hour'].value_counts().empty else "N/A"
        primary_payment_method = df['Pay Mode'].value_counts().index[0] if 'Pay Mode' in df.columns and not df['Pay Mode'].value_counts().empty else "N/A"

        pdf.add_metric("Top Pickup Location", top_pickup_location, 
                       "Most frequent pickup location.")
        pdf.add_metric("Top Dropoff Location", top_dropoff_location, 
                       "Most frequent dropoff location.")
        pdf.add_metric("Peak Hour", peak_hour, 
                       "Hour with the most trips.")
        pdf.add_metric("Primary Payment Method", primary_payment_method, 
                       "Most common payment method.")

        return pdf
    except Exception as e:
        st.error(f"Error in create metrics pdf: {str(e)}")
        return PDF()

def main():
    st.image(r"./TUTU.png", width=80)
    st.markdown("<h1>Union App Metrics Dashboard</h1>", unsafe_allow_html=True)
    
    # Theme switcher
    theme = st.sidebar.radio("Theme", ["Light", "Dark"], index=0)
    theme_css = """
    <style>
        .main { background-color: #f0f4f8; color: #333333; }
        .stMetric { background: linear-gradient(135deg, #ffffff, #e6f0fa); border-radius: 6px; padding: 5px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1); border-left: 2px solid #4a90e2; position: relative; padding-left: 20px; height: 45px; width: 100%; display: flex; align-items: center; }
        .stMetric:before { content: url('path/to/icon.png'); position: absolute; left: 5px; top: 50%; transform: translateY(-50%); width: 12px; height: 12px; }
        .stMetric label, .stMetric div { color: #333333 !important; font-size: 0.75em; margin: 0; }
        .stMetric div { font-size: 1em; font-weight: 600; }
        .stPlotlyChart, .stPydeckChart { background-color: #ffffff; border-radius: 6px; padding: 8px; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1); border-left: 2px solid #50c878; }
        .stTabs [data-baseweb="tab-list"] { background-color: #e6f0fa; border-radius: 4px; }
        .stTabs [data-baseweb="tab"] { background-color: #e6f0fa; color: #333333; padding: 6px 12px; transition: all 0.3s; }
        .stTabs [data-baseweb="tab"]:hover { background-color: #4a90e2; color: white; }
        .stTabs [data-baseweb="tab--selected"] { background-color: #4a90e2; color: white; border-radius: 4px; }
        body, .stApp { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        h1 { font-size: 1.8em; color: #4a90e2; font-weight: 600; text-align: center; }
        h2 { font-size: 1.3em; color: #333333; font-weight: 500; margin-bottom: 6px; }
        @media (max-width: 768px) { .stColumns > div { width: 100% !important; margin-bottom: 6px; } h1 { font-size: 1.5em; } h2 { font-size: 1.1em; } }
    </style>
    """
    dark_theme_css = """
    <style>
        .main { background-color: #1a1a1a; color: #e0e0e0; }
        .stMetric { background: linear-gradient(135deg, #2a2a2a, #404040); border-radius: 6px; padding: 5px; box-shadow: 0 1px 2px rgba(255, 255, 255, 0.1); border-left: 2px solid #1e90ff; position: relative; padding-left: 20px; height: 45px; width: 100%; display: flex; align-items: center; }
        .stMetric:before { content: url('path/to/icon.png'); position: absolute; left: 5px; top: 50%; transform: translateY(-50%); width: 12px; height: 12px; filter: brightness(0) invert(1); }
        .stMetric label, .stMetric div { color: #e0e0e0 !important; font-size: 0.75em; margin: 0; }
        .stMetric div { font-size: 1em; font-weight: 600; }
        .stPlotlyChart, .stPydeckChart { background-color: #2a2a2a; border-radius: 6px; padding: 8px; box-shadow: 0 1px 2px rgba(255, 255, 255, 0.1); border-left: 2px solid #50c878; }
        .stTabs [data-baseweb="tab-list"] { background-color: #404040; border-radius: 4px; }
        .stTabs [data-baseweb="tab"] { background-color: #404040; color: #e0e0e0; padding: 6px 12px; transition: all 0.3s; }
        .stTabs [data-baseweb="tab"]:hover { background-color: #1e90ff; color: white; }
        .stTabs [data-baseweb="tab--selected"] { background-color: #1e90ff; color: white; border-radius: 4px; }
        body, .stApp { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        h1 { font-size: 1.8em; color: #1e90ff; font-weight: 600; text-align: center; }
        h2 { font-size: 1.3em; color: #e0e0e0; font-weight: 500; margin-bottom: 6px; }
        @media (max-width: 768px) { .stColumns > div { width: 100% !important; margin-bottom: 6px; } h1 { font-size: 1.5em; } h2 { font-size: 1.1em; } }
    </style>
    """
    st.markdown(theme_css if theme == "Light" else dark_theme_css, unsafe_allow_html=True)

    try:
        with st.spinner("Loading data... 🎉"):
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
            trip_status_filter = st.sidebar.multiselect(
                "Filter by Trip Status",
                options=df['Trip Status'].dropna().unique().tolist() if 'Trip Status' in df.columns else [],
                default=df['Trip Status'].dropna().unique().tolist() if 'Trip Status' in df.columns else []
            )

            df = load_data()
            if len(date_range) == 2:
                df = df[(df['Trip Date'].dt.date >= date_range[0]) &
                        (df['Trip Date'].dt.date <= date_range[1])]
            if trip_status_filter:
                df = df[df['Trip Status'].isin(trip_status_filter)]

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
            get_download_data(df, date_range).to_excel(writer, sheet_name='Daily Metrics', index=True)
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

        # KPI Summary
        st.markdown("<h2 style='text-align: center; color: #4a90e2;'>Key Performance Indicators</h2>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Revenue", f"{df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum():,.0f} UGX",
                      help="Total revenue from completed trips.")
        with col2:
            st.metric("Total Drivers", unique_drivers,
                      help="Number of unique active drivers.")
        with col3:
            st.metric("Completion Rate", f"{100 - calculate_cancellation_rate(df):.1f}%" if calculate_cancellation_rate(df) is not None else "N/A",
                      help="Percentage of trips successfully completed.")

        st.markdown("<div style='padding: 10px;'></div>", unsafe_allow_html=True)

        tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Financial", "User Analysis", "Geographic"])

        with tab1:
            st.header("Trips Overview")
            st.markdown("<div style='padding: 5px;'></div>", unsafe_allow_html=True)
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Requests", len(df),
                          help="Total number of trip requests, including completed, cancelled, and expired trips.")
            with col2:
                completed_trips = len(df[df['Trip Status'] == 'Job Completed'])
                st.metric("Completed Trips", completed_trips,
                          help="Number of trips successfully completed from pickup to dropoff.")
            with col3:
                st.metric("Avg. Distance", f"{df['Distance'].mean():.1f} km" if 'Distance' in df.columns else "N/A",
                          help="Average distance per trip in kilometers, based on completed trips.")
            with col4:
                cancellation_rate = calculate_cancellation_rate(df)
                if cancellation_rate is not None:
                    st.metric("Driver Cancellation Rate", f"{cancellation_rate:.1f}%",
                              help="Percentage of trips cancelled by drivers, indicating driver reliability.")
                else:
                    st.metric("Driver Cancellation Rate", "N/A",
                              help="Percentage of trips cancelled by drivers (data unavailable).")
            with col5:
                timeout_rate = calculate_passenger_search_timeout(df)
                if timeout_rate is not None:
                    st.metric("Passenger Search Timeout", f"{timeout_rate:.1f}%",
                              help="Percentage of trips that expired due to no driver acceptance.")
                else:
                    st.metric("Passenger Search Timeout", "N/A",
                              help="Percentage of trips that expired due to no driver acceptance (data unavailable).")

            with st.expander("Detailed Trip Status Breakdown"):
                status_breakdown_fig = completed_vs_cancelled_daily(df)
                if status_breakdown_fig:
                    st.plotly_chart(status_breakdown_fig, use_container_width=True)
                else:
                    st.warning("Could not generate trip status breakdown chart - missing required data")

            col6, col7, col8 = st.columns(3)
            with col6:
                trips_per_driver(df)
            with col7:
                st.metric("Passenger App Downloads", app_downloads,
                          help="Total number of passenger app installations.")
            with col8:
                st.metric("Riders Onboarded", riders_onboarded,
                          help="Total number of drivers registered on the platform.")

            total_trips_by_status(df)
            total_distance_covered(df)
            revenue_by_day(df)
            avg_revenue_per_trip(df)
            total_commission(df)

        with tab2:
            st.header("Financial Performance")
            st.markdown("<div style='padding: 5px;'></div>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                total_revenue = df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum()
                st.metric("Total Value Of Rides", f"{total_revenue:,.0f} UGX",
                          help="Total revenue generated from completed trips.")
            with col2:
                total_commission(df)
            with col3:
                gross_profit(df)

            col4, col5, col6 = st.columns(3)
            with col4:
                st.metric("Passenger Wallet Balance", f"{passenger_wallet_balance:,.0f} UGX",
                          help="Total funds held in passenger wallet accounts.")
            with col5:
                st.metric("Driver Wallet Balance", f"{driver_wallet_balance:,.0f} UGX",
                          help="Total positive balances owed to drivers.")
            with col6:
                st.metric("Commission Owed", f"{commission_owed:,.0f} UGX",
                          help="Total negative balances, representing commissions owed by drivers.")

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
            st.markdown("<div style='padding: 5px;'></div>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                unique_driver_count(df)
            with col2:
                st.metric("Passenger App Downloads", app_downloads,
                          help="Total number of passenger app installations.")
            with col3:
                st.metric("Riders Onboarded", riders_onboarded,
                          help="Total number of drivers registered on the platform.")

            col4, col5 = st.columns(2)
            with col4:
                st.metric("Driver Retention Rate", f"{retention_rate:.1f}%",
                          help="Percentage of onboarded drivers who are active, indicating driver loyalty.")
            with col5:
                st.metric("Passenger-to-Driver Ratio", f"{passenger_ratio:.1f}",
                          help="Number of passengers per active driver, showing supply-demand balance.")

            top_drivers_by_revenue(df)
            driver_performance_comparison(df)
            passenger_insights(df)
            top_10_drivers_by_earnings(df)

            st.markdown("---")
            st.subheader("Union Staff Trip Completion")
            st.markdown("<div style='padding: 3px;'></div>", unsafe_allow_html=True)

            try:
                if os.path.exists(UNION_STAFF_FILE_PATH):
                    union_staff_df = pd.read_excel(UNION_STAFF_FILE_PATH)
                    if union_staff_df.empty or union_staff_df.shape[1] == 0:
                        st.warning("Union Staff file is empty or does not contain columns.")
                    else:
                        union_staff_names = union_staff_df.iloc[:, 0].dropna().astype(str).tolist()
                        st.metric("Total Union's Staff Members", len(union_staff_names),
                                  help="Total number of Union staff members listed in the staff file.")
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
            st.markdown("<div style='padding: 5px;'></div>", unsafe_allow_html=True)
            most_frequent_locations(df)
            peak_hours(df)
            trip_status_trends(df)
            customer_payment_methods(df)

    except FileNotFoundError:
        st.error("Data file not found. Please ensure the Excel file is placed in the data/ directory.")
    except Exception as e:
        st.error(f"Error: {e}")

    # Feedback Section
    st.markdown("---")
    st.subheader("Provide Feedback")
    feedback = st.text_area("Your feedback helps us improve!")
    if st.button("Submit Feedback"):
        st.success("Thank you for your feedback!")

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    main()
