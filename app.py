import os
import io
import time
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from fpdf import FPDF

# Constants
UNION_STAFF_FILE_PATH = "union_staff.xlsx"

# Data Loading Functions (Placeholder implementations - replace with your actual logic)
def load_data():
    # Replace with actual data loading logic
    return pd.DataFrame({
        'Trip Date': pd.date_range(start='2023-01-01', end='2025-05-07', freq='D'),
        'Driver': ['Driver1'] * 858,
        'Trip Status': ['Job Completed'] * 858,
        'Trip Pay Amount Cleaned': [1000] * 858,
        'Distance': [5] * 858
    })

def load_passengers_data(date_range):
    # Replace with actual data loading logic
    return pd.DataFrame()

def load_drivers_data(date_range):
    # Replace with actual data loading logic
    return pd.DataFrame()

# Placeholder Metric Functions (Replace with your actual implementations)
def passenger_metrics(df_passengers):
    return 1000, 500000  # app_downloads, passenger_wallet_balance

def driver_metrics(df_drivers):
    return 500, 300000, 100000  # riders_onboarded, driver_wallet_balance, commission_owed

def calculate_driver_retention_rate(riders_onboarded, app_downloads, unique_drivers):
    return 85.0, 2.0  # retention_rate, passenger_ratio

def calculate_cancellation_rate(df):
    return 5.0  # Placeholder

def calculate_passenger_search_timeout(df):
    return 3.0  # Placeholder

# Placeholder Chart Functions (Replace with your actual implementations)
def completed_vs_cancelled_daily(df):
    return None  # Placeholder

def trips_per_driver(df):
    st.metric("Trips per Driver", "10", help="Average number of trips per driver.")

def total_trips_by_status(df):
    st.write("Total Trips by Status Chart Placeholder")

def total_distance_covered(df):
    st.write("Total Distance Covered Chart Placeholder")

def revenue_by_day(df):
    st.write("Revenue by Day Chart Placeholder")

def avg_revenue_per_trip(df):
    st.write("Avg Revenue per Trip Chart Placeholder")

def total_commission(df):
    st.metric("Total Commission", "50,000 UGX", help="Total commission earned.")

def gross_profit(df):
    st.metric("Gross Profit", "200,000 UGX", help="Total profit after expenses.")

def avg_commission_per_trip(df):
    st.metric("Avg Commission per Trip", "100 UGX", help="Average commission per trip.")

def revenue_per_driver(df):
    st.metric("Revenue per Driver", "10,000 UGX", help="Average revenue per driver.")

def driver_earnings_per_trip(df):
    st.metric("Driver Earnings per Trip", "800 UGX", help="Average earnings per trip.")

def fare_per_km(df):
    st.write("Fare per KM Chart Placeholder")

def revenue_share(df):
    st.write("Revenue Share Chart Placeholder")

def total_trips_by_type(df):
    st.write("Total Trips by Type Chart Placeholder")

def payment_method_revenue(df):
    st.write("Payment Method Revenue Chart Placeholder")

def distance_vs_revenue_scatter(df):
    st.write("Distance vs Revenue Scatter Chart Placeholder")

def weekday_vs_weekend_analysis(df):
    st.write("Weekday vs Weekend Analysis Chart Placeholder")

def unique_driver_count(df):
    st.metric("Unique Drivers", "50", help="Number of unique drivers.")

def top_drivers_by_revenue(df):
    st.write("Top Drivers by Revenue Chart Placeholder")

def driver_performance_comparison(df):
    st.write("Driver Performance Comparison Chart Placeholder")

def passenger_insights(df):
    st.write("Passenger Insights Chart Placeholder")

def top_10_drivers_by_earnings(df):
    st.write("Top 10 Drivers by Earnings Chart Placeholder")

def get_completed_trips_by_union_passengers(df, union_staff_names):
    return pd.DataFrame()  # Placeholder

def most_frequent_locations(df):
    st.write("Most Frequent Locations Chart Placeholder")

def peak_hours(df):
    st.write("Peak Hours Chart Placeholder")

def trip_status_trends(df):
    st.write("Trip Status Trends Chart Placeholder")

def customer_payment_methods(df):
    st.write("Customer Payment Methods Chart Placeholder")

def get_download_data(df, date_range):
    return df  # Placeholder

def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Union App Metrics Report", ln=True, align="C")
    return pdf

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

    # Theme toggle animation
    st.sidebar.markdown(
        f"""
        <style>
        .sidebar .stRadio {{
            transition: opacity 0.3s ease;
        }}
        .sidebar .stRadio:hover {{
            opacity: 0.7;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

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

    # Feedback Section with Enhanced Styling
    st.markdown("---")
    st.image("https://via.placeholder.com/50", width=50)  # Replace with your logo path
    st.subheader("Provide Feedback")
    st.write("Please provide your feedback below:")

    form_card_css = """
    <style>
    .form-card {
        background: linear-gradient(135deg, #ffffff, #e6f0fa);
        border-radius: 6px;
        padding: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #50c878;
    }
    iframe {
        border: none;
    }
    </style>
    """
    st.markdown(form_card_css, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="form-card">', unsafe_allow_html=True)
        form_iframe = """
        <iframe src="https://docs.google.com/forms/d/e/1FAIpQLSeM3Y8mvr74nh-g-UkEN9jNmqz7IcdLoTI2yG1sT1tlS46hVQ/viewform?embedded=true" width="500" height="450" frameborder="0" marginheight="0" marginwidth="0">Loading…</iframe>
        """
        components.html(form_iframe, height=450)
        st.markdown('</div>', unsafe_allow_html=True)

    # Animated Charts Section with Filters and Export
    st.markdown("---")
    st.markdown('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">', unsafe_allow_html=True)
    st.markdown('<h2 style="text-align: center;"><i class="fas fa-chart-bar"></i> Animated Charts (Non-Time Based)</h2>', unsafe_allow_html=True)
    st.write("Interact with the filters and slider to animate the chart.")

    # Interactive Filters
    status_filter = st.selectbox("Filter by Trip Status", options=["All"] + df['Trip Status'].dropna().unique().tolist(), index=0)
    filtered_df = df if status_filter == "All" else df[df['Trip Status'] == status_filter]
    categories = filtered_df['Trip Status'].value_counts().index[:4].tolist() if not filtered_df.empty else ['A', 'B', 'C', 'D']
    base_values = filtered_df['Trip Pay Amount Cleaned'].value_counts().values[:4] if not filtered_df.empty else np.array([10, 20, 15, 25])

    card_css = """
    <style>
    .chart-card {
        background: linear-gradient(135deg, #ffffff, #e6f0fa) !important;
        border-radius: 6px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #4a90e2;
        margin-bottom: 20px;
    }
    </style>
    """
    st.markdown(card_css, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        with st.spinner("Generating chart..."):
            time.sleep(1)  # Simulate loading
            animation_factor = st.slider("Adjust Chart Values", 0, 100, 50)

            # Exportable Chart Data
            if st.button("Download Chart Data"):
                chart_data = pd.DataFrame({'Category': categories, 'Value': base_values * (animation_factor / 50)})
                csv = chart_data.to_csv(index=False)
                st.download_button("Download CSV", csv, "chart_data.csv", "text/csv")

            fig = go.Figure(
                data=[go.Bar(
                    x=categories,
                    y=base_values * (animation_factor / 50),
                    marker_color=[f'rgb({int(255 * (1 - v/max(base_values))), 0, int(255 * (v/max(base_values)))})' 
                                  for v in base_values * (animation_factor / 50)],
                    text=base_values * (animation_factor / 50),
                    textposition='auto'
                )],
                layout=go.Layout(
                    title=f"Animated Bar Chart - {status_filter}",
                    title_font_size=20,
                    xaxis=dict(title="Categories", titlefont_size=14),
                    yaxis=dict(title="Values", titlefont_size=14, gridcolor='rgba(128, 128, 128, 0.2)'),
                    plot_bgcolor='rgba(240, 244, 248, 0.8)' if theme == "Light" else 'rgba(26, 26, 26, 0.8)',
                    paper_bgcolor='rgba(0, 0, 0, 0)',
                    font=dict(color='#333333' if theme == "Light" else '#e0e0e0'),
                    updatemenus=[dict(
                        type="buttons",
                        buttons=[dict(label="Play",
                                      method="animate",
                                      args=[None, {"frame": {"duration": 500, "redraw": True},
                                                   "fromcurrent": True}])],
                        direction="left",
                        pad={"r": 10, "t": 10},
                        showactive=False,
                        x=0.11,
                        xanchor="left",
                        y=1.1,
                        yanchor="top",
                        bgcolor='rgba(74, 144, 226, 0.2)' if theme == "Light" else 'rgba(30, 144, 255, 0.2)',
                        font=dict(color='#ffffff')
                    )],
                    frames=[go.Frame(data=[go.Bar(
                        x=categories,
                        y=base_values * (i / 50),
                        marker_color=[f'rgb({int(255 * (1 - v/max(base_values))), 0, int(255 * (v/max(base_values)))})' 
                                      for v in base_values * (i / 50)],
                        text=base_values * (i / 50),
                        textposition='auto'
                    )]) for i in range(0, 101, 10)]
                )
            )
            fig.update_layout(
                transition={'duration': 500},
                showlegend=False,
                hovermode="x unified",
                hoverlabel=dict(bgcolor="white", font_size=12, font_family="Arial")
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Additional Animated Pie Chart
    st.markdown("---")
    st.markdown('<h2 style="text-align: center;"><i class="fas fa-pie-chart"></i> Animated Pie Chart</h2>', unsafe_allow_html=True)
    st.write("Adjust the slider to animate the pie chart.")
    with st.container():
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        with st.spinner("Generating chart..."):
            time.sleep(1)
            animation_factor = st.slider("Adjust Pie Values", 0, 100, 50)
            fig_pie = go.Figure(
                data=[go.Pie(labels=categories, values=base_values * (animation_factor / 50))],
                layout=go.Layout(
                    title="Trip Status Distribution",
                    updatemenus=[dict(
                        type="buttons",
                        buttons=[dict(label="Play",
                                      method="animate",
                                      args=[None, {"frame": {"duration": 500, "redraw": True},
                                                   "fromcurrent": True}])],
                        direction="left",
                        pad={"r": 10, "t": 10},
                        showactive=False,
                        x=0.11,
                        xanchor="left",
                        y=1.1,
                        yanchor="top"
                    )],
                    frames=[go.Frame(data=[go.Pie(labels=categories, values=base_values * (i / 50))]) for i in range(0, 101, 10)]
                )
            )
            fig_pie.update_layout(transition={'duration': 500})
            st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; color: #666666; font-size: 12px; padding: 10px;">'
        'Powered by Union App | © 2025 xAI'
        '</div>',
        unsafe_allow_html=True)

if __name__ == "__main__":
    if not os.path.exists("data"):
        os.makedirs("data")
    main()
