
import os
import io
import base64
import datetime
from datetime import datetime as dt
from pathlib import Path

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
DATA_DIR = Path("data")
LOGO_PATH = Path("TUTU.png")

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# Files expected
FILES = {
    "passengers":r"./PASSENGERS.xlsx",
    "drivers":r" ./DRIVERS.xlsx",
    "beer": r"./BEER.xlsx",
    "transactions": r"./TRANSACTIONS.xlsx",
    "union_staff": r"./UNION STAFF.xlsx",
}

# Theme CSS
LIGHT_THEME_CSS = """
<style>
    .main {
        background-color: white;
        color: black;
    }
    .stButton>button {
        background-color: #4a90e2;
        color: white;
    }
    .stMetric {
        color: black;
    }
</style>
"""

DARK_THEME_CSS = """
<style>
    .main {
        background-color: #1a1a1a;
        color: white;
    }
    .stButton>button {
        background-color: #1e90ff;
        color: white;
    }
    .stMetric {
        color: white;
    }
</style>
"""

# Utility functions for cleaning
def clean_ugx_amount(series):
    # Remove 'UGX', commas, whitespace, convert to float, handle negatives, default 0.0
    def clean_value(x):
        if pd.isna(x):
            return 0.0
        if isinstance(x, (int, float)):
            return float(x)
        try:
            s = str(x).replace("UGX", "").replace(",", "").strip()
            if s == "":
                return 0.0
            return float(s)
        except Exception:
            return 0.0
    return series.apply(clean_value)

def clean_date(series):
    return pd.to_datetime(series, errors='coerce')

def clean_distance(series):
    return pd.to_numeric(series, errors='coerce').fillna(0)

def fill_pay_mode(series):
    return series.fillna("Unknown")

@st.cache_data(show_spinner=True)
def load_excel_file(filepath):
    if not filepath.exists():
        st.error(f"Data file not found: {filepath.name}. Please ensure the Excel file is placed in the data/ directory.")
        return None
    try:
        df = pd.read_excel(filepath)
        return df
    except Exception as e:
        st.error(f"Error loading {filepath.name}: {e}")
        return None

@st.cache_data(show_spinner=True)
def load_all_data():
    passengers = load_excel_file(FILES["passengers"])
    drivers = load_excel_file(FILES["drivers"])
    beer = load_excel_file(FILES["beer"])
    transactions = load_excel_file(FILES["transactions"])
    union_staff = load_excel_file(FILES["union_staff"])
    return passengers, drivers, beer, transactions, union_staff

def preprocess_data(passengers, drivers, beer, transactions, union_staff):
    # Clean passengers
    if passengers is not None:
        passengers["Created"] = clean_date(passengers.get("Created", pd.Series(dtype=str)))
        passengers["Wallet Balance"] = clean_ugx_amount(passengers.get("Wallet Balance", pd.Series(dtype=str)))
    # Clean drivers
    if drivers is not None:
        drivers["Created"] = clean_date(drivers.get("Created", pd.Series(dtype=str)))
        drivers["Wallet Balance"] = clean_ugx_amount(drivers.get("Wallet Balance", pd.Series(dtype=str)))
    # Clean beer (trips)
    if beer is not None:
        beer["Trip Date"] = clean_date(beer.get("Trip Date", pd.Series(dtype=str)))
        beer["Trip Status"] = beer.get("Trip Status", pd.Series(dtype=str)).fillna("Unknown")
        beer["Trip Pay Amount"] = clean_ugx_amount(beer.get("Trip Pay Amount", pd.Series(dtype=str)))
        beer["Trip Distance (KM/Mi)"] = clean_distance(beer.get("Trip Distance (KM/Mi)", pd.Series(dtype=str)))
        beer["Company Commission Cleaned"] = clean_ugx_amount(beer.get("Company Commission Cleaned", pd.Series(dtype=str)))
        beer["Pay Mode"] = fill_pay_mode(beer.get("Pay Mode", pd.Series(dtype=str)))
        beer["Driver"] = beer.get("Driver", pd.Series(dtype=str)).fillna("Unknown")
        beer["Passenger"] = beer.get("Passenger", pd.Series(dtype=str)).fillna("Unknown")
        beer["Pickup Location"] = beer.get("Pickup Location", pd.Series(dtype=str)).fillna("Unknown")
        beer["Dropoff Location"] = beer.get("Dropoff Location", pd.Series(dtype=str)).fillna("Unknown")
        # Merge transactions if Company Commission Cleaned or Pay Mode missing or zero
        if transactions is not None:
            transactions["Company Amt (UGX)"] = clean_ugx_amount(transactions.get("Company Amt (UGX)", pd.Series(dtype=str)))
            transactions["Pay Mode"] = fill_pay_mode(transactions.get("Pay Mode", pd.Series(dtype=str)))
            # Merge on index or a common key if available - assuming index alignment here
            if "Company Commission Cleaned" not in beer.columns or beer["Company Commission Cleaned"].sum() == 0:
                if len(transactions) == len(beer):
                    beer["Company Commission Cleaned"] = transactions["Company Amt (UGX)"]
            if "Pay Mode" not in beer.columns or beer["Pay Mode"].isnull().all():
                if len(transactions) == len(beer):
                    beer["Pay Mode"] = transactions["Pay Mode"]
    # Clean union staff
    if union_staff is not None:
        union_staff_names = union_staff.iloc[:, 0].dropna().astype(str).tolist()
    else:
        union_staff_names = []
    return passengers, drivers, beer, union_staff_names

def filter_data_by_date_and_status(beer, start_date, end_date, selected_statuses):
    if beer is None:
        return None
    df = beer.copy()
    df = df[(df["Trip Date"] >= pd.to_datetime(start_date)) & (df["Trip Date"] <= pd.to_datetime(end_date))]
    if selected_statuses:
        df = df[df["Trip Status"].isin(selected_statuses)]
    return df

def format_int(value):
    try:
        return f"{int(round(value)):,}"
    except Exception:
        return "N/A"

def format_float(value, decimals=1):
    try:
        return f"{value:.{decimals}f}"
    except Exception:
        return "N/A"

def format_percent(value, decimals=1):
    try:
        return f"{value:.{decimals}f}%"
    except Exception:
        return "N/A"

# KPI calculations for Overview tab
def calculate_overview_kpis(beer, passengers, drivers, start_date, end_date, selected_statuses):
    df = filter_data_by_date_and_status(beer, start_date, end_date, selected_statuses)
    total_requests = len(df) if df is not None else 0
    completed_trips = len(df[df["Trip Status"] == "Job Completed"]) if df is not None else 0
    avg_distance = df["Trip Distance (KM/Mi)"].mean() if df is not None and not df.empty else 0
    driver_cancellations = df["Trip Status"].str.contains("Cancel", na=False).sum() if df is not None else 0
    passenger_search_timeout = (df["Trip Status"] == "Expired").sum() if df is not None else 0
    driver_cancellation_rate = (driver_cancellations / total_requests * 100) if total_requests > 0 else None
    passenger_search_timeout_rate = (passenger_search_timeout / total_requests * 100) if total_requests > 0 else None
    avg_trips_per_driver = df.groupby("Driver").size().mean() if df is not None and not df.empty else None
    passenger_app_downloads = len(passengers[(passengers["Created"] >= pd.to_datetime(start_date)) & (passengers["Created"] <= pd.to_datetime(end_date))]) if passengers is not None else 0
    riders_onboarded = len(drivers[(drivers["Created"] >= pd.to_datetime(start_date)) & (drivers["Created"] <= pd.to_datetime(end_date))]) if drivers is not None else 0
    total_distance_covered = df[df["Trip Status"] == "Job Completed"]["Trip Distance (KM/Mi)"].sum() if df is not None else 0
    avg_revenue_per_trip = df["Trip Pay Amount"].mean() if df is not None and not df.empty else 0
    total_commission = df["Company Commission Cleaned"].sum() if df is not None else 0
    return {
        "total_requests": total_requests,
        "completed_trips": completed_trips,
        "avg_distance": avg_distance,
        "driver_cancellation_rate": driver_cancellation_rate,
        "passenger_search_timeout_rate": passenger_search_timeout_rate,
        "avg_trips_per_driver": avg_trips_per_driver,
        "passenger_app_downloads": passenger_app_downloads,
        "riders_onboarded": riders_onboarded,
        "total_distance_covered": total_distance_covered,
        "avg_revenue_per_trip": avg_revenue_per_trip,
        "total_commission": total_commission,
        "filtered_df": df,
    }

def calculate_financial_kpis(beer, passengers, drivers, start_date, end_date, selected_statuses):
    df = filter_data_by_date_and_status(beer, start_date, end_date, selected_statuses)
    if df is None or df.empty:
        return {}
    total_value_of_rides = df[df["Trip Status"] == "Job Completed"]["Trip Pay Amount"].sum()
    total_commission = df["Company Commission Cleaned"].sum()
    gross_profit = total_commission
    passenger_wallet_balance = passengers["Wallet Balance"].sum() if passengers is not None else 0
    driver_wallet_balance = drivers[drivers["Wallet Balance"] > 0]["Wallet Balance"].sum() if drivers is not None else 0
    commission_owed = drivers[drivers["Wallet Balance"] < 0]["Wallet Balance"].abs().sum() if drivers is not None else 0
    avg_commission_per_trip = df["Company Commission Cleaned"].mean()
    avg_revenue_per_driver = df.groupby("Driver")["Trip Pay Amount"].sum().mean()
    avg_driver_earnings_per_trip = (df["Trip Pay Amount"] - df["Company Commission Cleaned"]).mean()
    completed_trips = df[df["Trip Status"] == "Job Completed"]
    if not completed_trips.empty:
        fare_per_km = (completed_trips["Trip Pay Amount"] / completed_trips["Trip Distance (KM/Mi)"].replace(0,1)).mean()
    else:
        fare_per_km = 0
    revenue_share = (total_commission / total_value_of_rides * 100) if total_value_of_rides > 0 else 0
    return {
        "total_value_of_rides": total_value_of_rides,
        "total_commission": total_commission,
        "gross_profit": gross_profit,
        "passenger_wallet_balance": passenger_wallet_balance,
        "driver_wallet_balance": driver_wallet_balance,
        "commission_owed": commission_owed,
        "avg_commission_per_trip": avg_commission_per_trip,
        "avg_revenue_per_driver": avg_revenue_per_driver,
        "avg_driver_earnings_per_trip": avg_driver_earnings_per_trip,
        "fare_per_km": fare_per_km,
        "revenue_share": revenue_share,
        "filtered_df": df,
    }

def calculate_user_analysis_kpis(beer, passengers, drivers, union_staff_names, start_date, end_date, selected_statuses):
    df = filter_data_by_date_and_status(beer, start_date, end_date, selected_statuses)
    unique_drivers = df["Driver"].nunique() if df is not None else 0
    passenger_app_downloads = len(passengers[(passengers["Created"] >= pd.to_datetime(start_date)) & (passengers["Created"] <= pd.to_datetime(end_date))]) if passengers is not None else 0
    riders_onboarded = len(drivers[(drivers["Created"] >= pd.to_datetime(start_date)) & (drivers["Created"] <= pd.to_datetime(end_date))]) if drivers is not None else 0
    driver_retention_rate = (unique_drivers / riders_onboarded * 100) if riders_onboarded > 0 else 0
    passenger_to_driver_ratio = (passenger_app_downloads / unique_drivers) if unique_drivers > 0 else 0
    # Union staff trips table
    if df is not None and union_staff_names:
        staff_trips = df[(df["Passenger"].isin(union_staff_names)) & (df["Trip Status"] == "Job Completed")]
        staff_trips_table = staff_trips[["Passenger", "Trip Date", "Trip Pay Amount", "Trip Distance (KM/Mi)"]].copy()
        staff_trips_table.rename(columns={"Trip Pay Amount": "Trip Pay Amount (UGX)", "Trip Distance (KM/Mi)": "Distance"}, inplace=True)
    else:
        staff_trips_table = pd.DataFrame()
    return {
        "unique_drivers": unique_drivers,
        "passenger_app_downloads": passenger_app_downloads,
        "riders_onboarded": riders_onboarded,
        "driver_retention_rate": driver_retention_rate,
        "passenger_to_driver_ratio": passenger_to_driver_ratio,
        "staff_trips_table": staff_trips_table,
        "filtered_df": df,
    }

def calculate_geographic_kpis(beer, start_date, end_date, selected_statuses):
    df = filter_data_by_date_and_status(beer, start_date, end_date, selected_statuses)
    if df is None or df.empty:
        return {}
    top_pickup = df["Pickup Location"].value_counts().head(5)
    top_dropoff = df["Dropoff Location"].value_counts().head(5)
    df["Trip Hour"] = df["Trip Date"].dt.hour
    peak_hours = df["Trip Hour"].value_counts().sort_index()
    trip_status_trends = df.groupby([df["Trip Date"].dt.date, "Trip Status"]).size().unstack(fill_value=0)
    customer_payment_methods = df["Pay Mode"].value_counts()
    return {
        "top_pickup": top_pickup,
        "top_dropoff": top_dropoff,
        "peak_hours": peak_hours,
        "trip_status_trends": trip_status_trends,
        "customer_payment_methods": customer_payment_methods,
        "filtered_df": df,
    }

def generate_excel_export(df):
    # Generate daily metrics DataFrame as specified
    if df is None or df.empty:
        return None
    df["Trip Date Only"] = df["Trip Date"].dt.date
    completed = df[df["Trip Status"] == "Job Completed"]
    daily_metrics = pd.DataFrame()
    daily_metrics["Total Value of Rides"] = completed.groupby("Trip Date Only")["Trip Pay Amount"].sum()
    daily_metrics["Total Rider Commissions"] = df.groupby("Trip Date Only")["Company Commission Cleaned"].sum()
    daily_metrics["Total # of Rides Completed"] = completed.groupby("Trip Date Only").size()
    daily_metrics["Total Requests"] = df.groupby("Trip Date Only").size()
    daily_metrics["Average Trip Distance"] = completed.groupby("Trip Date Only")["Trip Distance (KM/Mi)"].mean()
    # Cancellation rate = count cancellations / total requests
    cancellations = df[df["Trip Status"].str.contains("Cancel", na=False)]
    cancellation_rate = 1 - (cancellations.groupby("Trip Date Only").size() / daily_metrics["Total Requests"])
    daily_metrics["Completion Rate"] = cancellation_rate.fillna(1) * 100
    daily_metrics["Average Customer Price per Ride"] = completed.groupby("Trip Date Only")["Trip Pay Amount"].mean()
    daily_metrics["Average Customer Price per Kilometer"] = (completed["Trip Pay Amount"] / completed["Trip Distance (KM/Mi)"].replace(0,1)).groupby(completed["Trip Date Only"]).mean()
    daily_metrics["Daily Active Drivers"] = df.groupby("Trip Date Only")["Driver"].nunique()
    # Total Cumulative Riders: cumulative sum of unique passengers up to each day
    unique_passengers_per_day = df.groupby("Trip Date Only")["Passenger"].nunique()
    daily_metrics["Total Cumulative Riders"] = unique_passengers_per_day.cumsum()
    # Order per Rider: mean number of trips per passenger per day
    trips_per_passenger_per_day = df.groupby(["Trip Date Only", "Passenger"]).size()
    order_per_rider = trips_per_passenger_per_day.groupby("Trip Date Only").mean()
    daily_metrics["Order per Rider"] = order_per_rider
    # Placeholder columns
    placeholders = ["Total Rider Subscriptions", "Average Trip Time", "% of Riders Engaged", "% of Suspended Riders",
                    "Average Rider Earnings", "Daily Online Riders", "Bike Riders Acceptance Rate", "Total Passenger app Downloads Per"]
    for col in placeholders:
        daily_metrics[col] = 0
    daily_metrics = daily_metrics.fillna(0)
    return daily_metrics.reset_index()

def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Daily Metrics')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

def generate_pdf_report(overview_kpis, financial_kpis, user_kpis, geographic_kpis):
    pdf = FPDF()
    pdf.add_page()
    # Add logo
    if LOGO_PATH.exists():
        pdf.image(str(LOGO_PATH), x=10, y=8, w=33)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Union App Metrics Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 12)
    # Overview Section
    pdf.cell(0, 10, "Trips Overview", ln=True)
    for k, v in overview_kpis.items():
        if k == "filtered_df":
            continue
        pdf.cell(0, 8, f"{k.replace('_', ' ').title()}: {format_float(v) if isinstance(v, float) else format_int(v)}", ln=True)
    pdf.ln(5)
    # Financial Section
    pdf.cell(0, 10, "Financial Metrics", ln=True)
    for k, v in financial_kpis.items():
        if k == "filtered_df":
            continue
        pdf.cell(0, 8, f"{k.replace('_', ' ').title()}: {format_float(v) if isinstance(v, float) else format_int(v)}", ln=True)
    pdf.ln(5)
    # User Analysis Section
    pdf.cell(0, 10, "User Analysis", ln=True)
    for k, v in user_kpis.items():
        if k == "filtered_df" or k == "staff_trips_table":
            continue
        pdf.cell(0, 8, f"{k.replace('_', ' ').title()}: {format_float(v) if isinstance(v, float) else format_int(v)}", ln=True)
    pdf.ln(5)
    # Geographic Section
    pdf.cell(0, 10, "Geographic Metrics", ln=True)
    top_pickup = geographic_kpis.get("top_pickup")
    if top_pickup is not None:
        pdf.cell(0, 8, "Top 5 Pickup Locations:", ln=True)
        for loc, count in top_pickup.items():
            pdf.cell(0, 8, f"  {loc}: {count}", ln=True)
    top_dropoff = geographic_kpis.get("top_dropoff")
    if top_dropoff is not None:
        pdf.cell(0, 8, "Top 5 Dropoff Locations:", ln=True)
        for loc, count in top_dropoff.items():
            pdf.cell(0, 8, f"  {loc}: {count}", ln=True)
    pdf.ln(10)
    # Footer
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, f"Generated on {dt.now().strftime('%Y-%m-%d %H:%M:%S')}", align='C')
    return pdf.output(dest='S').encode('latin1')

def main():
    st.set_page_config(page_title="Union App Metrics Dashboard", layout="wide", page_icon="🚖")
    # Theme selection
    theme = st.sidebar.selectbox("Select Theme", options=["Light", "Dark"], index=0)
    if theme == "Light":
        st.markdown(LIGHT_THEME_CSS, unsafe_allow_html=True)
    else:
        st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

    # Load data
    passengers, drivers, beer, transactions, union_staff_names = load_all_data()
    passengers, drivers, beer, union_staff_names = preprocess_data(passengers, drivers, beer, transactions, union_staff_names)

    # Sidebar filters
    st.sidebar.header("Filters")
    min_date = beer["Trip Date"].min() if beer is not None else dt(2020,1,1)
    max_date = beer["Trip Date"].max() if beer is not None else dt.today()
    date_range = st.sidebar.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    if len(date_range) != 2:
        st.sidebar.error("Please select a start and end date.")
        return
    start_date, end_date = date_range
    trip_statuses = beer["Trip Status"].unique().tolist() if beer is not None else []
    selected_statuses = st.sidebar.multiselect("Select Trip Status", options=trip_statuses, default=trip_statuses)

    # Tabs
    tabs = st.tabs(["Overview", "Financial", "User Analysis", "Geographic", "Export", "Feedback"])

    with tabs[0]:
        st.header("Trips Overview")
        overview = calculate_overview_kpis(beer, passengers, drivers, start_date, end_date, selected_statuses)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Requests", format_int(overview["total_requests"]))
        col2.metric("Completed Trips", format_int(overview["completed_trips"]))
        col3.metric("Avg Trip Distance (KM/Mi)", format_float(overview["avg_distance"]))
        col4.metric("Driver Cancellation Rate", format_percent(overview["driver_cancellation_rate"] or 0))
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Passenger Search Timeout Rate", format_percent(overview["passenger_search_timeout_rate"] or 0))
        col2.metric("Avg Trips per Driver", format_float(overview["avg_trips_per_driver"] or 0))
        col3.metric("Passenger App Downloads", format_int(overview["passenger_app_downloads"]))
        col4.metric("Riders Onboarded", format_int(overview["riders_onboarded"]))
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Distance Covered", format_float(overview["total_distance_covered"]))
        col2.metric("Avg Revenue per Trip", format_float(overview["avg_revenue_per_trip"]))
        col3.metric("Total Commission", format_float(overview["total_commission"]))

        # Visualizations
        df = overview["filtered_df"]
        if df is not None and not df.empty:
            st.subheader("Trip Status Distribution")
            fig = px.pie(df, names="Trip Status", title="Trip Status Distribution")
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Trips Over Time")
            trips_over_time = df.groupby(df["Trip Date"].dt.date).size()
            fig2 = px.line(trips_over_time, title="Trips Over Time", labels={"index": "Date", 0: "Number of Trips"})
            st.plotly_chart(fig2, use_container_width=True)

    with tabs[1]:
        st.header("Financial Metrics")
        financial = calculate_financial_kpis(beer, passengers, drivers, start_date, end_date, selected_statuses)
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Value of Rides", format_float(financial.get("total_value_of_rides", 0)))
        col2.metric("Total Commission", format_float(financial.get("total_commission", 0)))
        col3.metric("Gross Profit", format_float(financial.get("gross_profit", 0)))
        col1, col2, col3 = st.columns(3)
        col1.metric("Passenger Wallet Balance", format_float(financial.get("passenger_wallet_balance", 0)))
        col2.metric("Driver Wallet Balance", format_float(financial.get("driver_wallet_balance", 0)))
        col3.metric("Commission Owed", format_float(financial.get("commission_owed", 0)))
        col1, col2, col3 = st.columns(3)
        col1.metric("Avg Commission per Trip", format_float(financial.get("avg_commission_per_trip", 0)))
        col2.metric("Avg Revenue per Driver", format_float(financial.get("avg_revenue_per_driver", 0)))
        col3.metric("Avg Driver Earnings per Trip", format_float(financial.get("avg_driver_earnings_per_trip", 0)))
        col1, col2, col3 = st.columns(3)
        col1.metric("Fare per KM", format_float(financial.get("fare_per_km", 0)))
        col2.metric("Revenue Share (%)", format_percent(financial.get("revenue_share", 0)))

        # Visualizations
        df = financial.get("filtered_df")
        if df is not None and not df.empty:
            st.subheader("Revenue Share by Payment Mode")
            rev_by_paymode = df.groupby("Pay Mode")["Company Commission Cleaned"].sum().reset_index()
            fig = px.pie(rev_by_paymode, names="Pay Mode", values="Company Commission Cleaned", title="Revenue Share by Payment Mode")
            st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        st.header("User Analysis")
        user = calculate_user_analysis_kpis(beer, passengers, drivers, union_staff_names, start_date, end_date, selected_statuses)
        col1, col2, col3 = st.columns(3)
        col1.metric("Unique Drivers", format_int(user["unique_drivers"]))
        col2.metric("Passenger App Downloads", format_int(user["passenger_app_downloads"]))
        col3.metric("Riders Onboarded", format_int(user["riders_onboarded"]))
        col1, col2 = st.columns(2)
        col1.metric("Driver Retention Rate", format_percent(user["driver_retention_rate"]))
        col2.metric("Passenger to Driver Ratio", format_float(user["passenger_to_driver_ratio"]))

        st.subheader("Union Staff Trips")
        if not user["staff_trips_table"].empty:
            st.dataframe(user["staff_trips_table"])
        else:
            st.info("No completed trips found for Union staff in the selected date range.")

        # Visualizations
        df = user["filtered_df"]
        if df is not None and not df.empty:
            st.subheader("Trips per Driver Distribution")
            trips_per_driver = df.groupby("Driver").size()
            fig = px.histogram(trips_per_driver, nbins=30, title="Trips per Driver Distribution")
            st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        st.header("Geographic Metrics")
       geo = calculate_geographic_kpis(beer, start_date, end_date, selected_statuses)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Top 5 Pickup Locations")
            if geo.get("top_pickup") is not None:
                st.bar_chart(geo["top_pickup"])
            else:
                st.info("No data available for pickup locations.")
        with col2:
            st.subheader("Top 5 Dropoff Locations")
            if geo.get("top_dropoff") is not None:
                st.bar_chart(geo["top_dropoff"])
            else:
                st.info("No data available for dropoff locations.")

        st.subheader("Peak Trip Hours")
        if geo.get("peak_hours") is not None:
            fig = px.bar(x=geo["peak_hours"].index, y=geo["peak_hours"].values, labels={"x": "Hour of Day", "y": "Number of Trips"}, title="Peak Trip Hours")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for peak hours.")

        st.subheader("Trip Status Trends Over Time")
        if geo.get("trip_status_trends") is not None and not geo["trip_status_trends"].empty:
            fig = px.line(geo["trip_status_trends"], title="Trip Status Trends Over Time")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for trip status trends.")

        st.subheader("Customer Payment Methods")
        if geo.get("customer_payment_methods") is not None:
            fig = px.pie(values=geo["customer_payment_methods"].values, names=geo["customer_payment_methods"].index, title="Customer Payment Methods")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available for payment methods.")

    with tabs[4]:
        st.header("Export Data")
        df = filter_data_by_date_and_status(beer, start_date, end_date, selected_statuses)
        daily_metrics = generate_excel_export(df)
        if daily_metrics is not None and not daily_metrics.empty:
            excel_data = to_excel_bytes(daily_metrics)
            st.download_button(label="Download Daily Metrics Excel", data=excel_data, file_name="daily_metrics.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.info("No data available to export.")

        # PDF export of summary report
        overview = calculate_overview_kpis(beer, passengers, drivers, start_date, end_date, selected_statuses)
        financial = calculate_financial_kpis(beer, passengers, drivers, start_date, end_date, selected_statuses)
        user = calculate_user_analysis_kpis(beer, passengers, drivers, union_staff_names, start_date, end_date, selected_statuses)
        geographic = calculate_geographic_kpis(beer, start_date, end_date, selected_statuses)
        pdf_bytes = generate_pdf_report(overview, financial, user, geographic)
        st.download_button(label="Download Summary Report PDF", data=pdf_bytes, file_name="union_metrics_report.pdf", mime="application/pdf")

    with tabs[5]:
        st.header("Feedback")
        with st.form("feedback_form"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            feedback = st.text_area("Feedback or Suggestions")
            submitted = st.form_submit_button("Submit")
            if submitted:
                # Here you would handle feedback submission, e.g., save to file or send email
                st.success("Thank you for your feedback!")

if __name__ == "__main__":
    main()


