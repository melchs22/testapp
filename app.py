def create_metrics_pdf(df, date_range, retention_rate, passenger_ratio, app_downloads, riders_onboarded, passenger_wallet_balance, driver_wallet_balance, commission_owed):
    try:
        class PDF(FPDF):
            def header(self):
                # Add logo
                try:
                    self.image(r"./TUTU.png", x=10, y=8, w=30)
                except Exception as e:
                    self.set_font('Arial', 'I', 8)
                    self.cell(0, 10, f'Could not load logo: {str(e)}', 0, 1, 'L')
                # Title
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

        # Date Range
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

        # Overview Metrics
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

        pdf.add_metric("Total Requests", total_requests, "Total number of trip requests made within the selected date range.")
        pdf.add_metric("Completed Trips", completed_trips, "Number of trips successfully completed.")
        pdf.add_metric("Average Distance", avg_distance, "Average distance traveled per trip.")
        pdf.add_metric("Driver Cancellation Rate", cancellation_rate_str, "Percentage of trips cancelled by drivers.")
        pdf.add_metric("Passenger Search Timeout", timeout_rate_str, "Percentage of trips that expired due to no driver acceptance.")
        pdf.add_metric("Average Trips per Driver", avg_trips_per_driver, "Average number of trips completed per driver.")
        pdf.add_metric("Passenger App Downloads", int(app_downloads), "Total number of passenger app downloads.")
        pdf.add_metric("Riders Onboarded", int(riders_onboarded), "Total number of drivers onboarded.")
        pdf.add_metric("Total Distance Covered", total_distance_covered, "Total distance covered by all completed trips.")
        pdf.add_metric("Average Revenue per Trip", avg_revenue_per_trip, "Average revenue generated per trip.")
        pdf.add_metric("Total Commission", total_commission, "Total commission earned by the company.")

        # Financial Metrics
        pdf.add_section_title("Financial Performance")
        total_revenue = f"{df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'].sum():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Trip Status' in df.columns else "N/A"
        gross_profit = f"{df['Company Commission Cleaned'].sum():,.0f} UGX" if 'Company Commission Cleaned' in df.columns else "N/A"
        avg_commission_per_trip = f"{df['Company Commission Cleaned'].mean():,.0f} UGX" if 'Company Commission Cleaned' in df.columns else "N/A"
        avg_revenue_per_driver = f"{df.groupby('Driver')['Trip Pay Amount Cleaned'].sum().mean():,.0f} UGX" if 'Driver' in df.columns and 'Trip Pay Amount Cleaned' in df.columns else "N/A"
        driver_earnings_per_trip = f"{(df['Trip Pay Amount Cleaned'] - df['Company Commission Cleaned']).mean():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Company Commission Cleaned' in df.columns else "N/A"
        fare_per_km = f"{(df[df['Trip Status'] == 'Job Completed']['Trip Pay Amount Cleaned'] / df[df['Trip Status'] == 'Job Completed']['Distance'].replace(0, 1)).mean():,.0f} UGX" if 'Trip Pay Amount Cleaned' in df.columns and 'Distance' in df.columns and 'Trip Status' in df.columns else "N/A"
        revenue_share = f"{(df['Company Commission Cleaned'].sum() / df['Trip Pay Amount Cleaned'].sum() * 100):.1f}%" if 'Trip Pay Amount Cleaned' in df.columns and 'Company Commission Cleaned' in df.columns and df['Trip Pay Amount Cleaned'].sum() > 0 else "N/A"

        pdf.add_metric("Total Value of Rides", total_revenue, "Total revenue from all completed trips.")
        pdf.add_metric("Total Commission", total_commission, "Total commission earned by the company.")
        pdf.add_metric("Gross Profit", gross_profit, "Total profit after accounting for commissions.")
        pdf.add_metric("Passenger Wallet Balance", f"{float(passenger_wallet_balance):,.0f} UGX", "Total balance in passenger wallets.")
        pdf.add_metric("Driver Wallet Balance", f"{float(driver_wallet_balance):,.0f} UGX", "Total balance in driver wallets (positive values).")
        pdf.add_metric("Commission Owed", f"{float(commission_owed):,.0f} UGX", "Total commission owed by drivers (negative wallet balances).")
        pdf.add_metric("Average Commission per Trip", avg_commission_per_trip, "Average commission earned per trip.")
        pdf.add_metric("Average Revenue per Driver", avg_revenue_per_driver, "Average revenue generated per driver.")
        pdf.add_metric("Average Driver Earnings per Trip", driver_earnings_per_trip, "Average earnings per trip for drivers after commission.")
        pdf.add_metric("Average Fare per KM", fare_per_km, "Average revenue per kilometer for completed trips.")
        pdf.add_metric("Revenue Share", revenue_share, "Percentage of total revenue retained as commission.")

        # User Analysis Metrics
        pdf.add_section_title("User Performance")
        unique_drivers = df['Driver'].nunique() if 'Driver' in df.columns else 0
        retention_rate_str = f"{float(retention_rate):.1f}%" if retention_rate is not None else "N/A"
        passenger_ratio_str = f"{float(passenger_ratio):.1f}" if passenger_ratio is not None else "N/A"
        total_union_staff = len(pd.read_excel(UNION_STAFF_FILE_PATH).iloc[:, 0].dropna()) if os.path.exists(UNION_STAFF_FILE_PATH) else 0

        pdf.add_metric("Unique Drivers", unique_drivers, "Number of unique drivers who completed at least one trip.")
        pdf.add_metric("Passenger App Downloads", int(app_downloads), "Total number of passenger app downloads.")
        pdf.add_metric("Riders Onboarded", int(riders_onboarded), "Total number of drivers onboarded.")
        pdf.add_metric("Driver Retention Rate", retention_rate_str, "Percentage of onboarded riders who are active drivers.")
        pdf.add_metric("Passenger-to-Driver Ratio", passenger_ratio_str, "Number of passengers per active driver.")
        pdf.add_metric("Total Union's Staff Members", total_union_staff, "Number of Union staff members listed in the staff file.")

        # Geographic Analysis Metrics
        pdf.add_section_title("Geographic Analysis")
        top_pickup_location = df['Pickup Location'].value_counts().index[0] if 'Pickup Location' in df.columns and not df['Pickup Location'].value_counts().empty else "N/A"
        top_dropoff_location = df['Dropoff Location'].value_counts().index[0] if 'Dropoff Location' in df.columns and not df['Dropoff Location'].value_counts().empty else "N/A"
        peak_hour = f"{df['Trip Hour'].value_counts().index[0]}:00" if 'Trip Hour' in df.columns and not df['Trip Hour'].value_counts().empty else "N/A"
        primary_payment_method = df['Pay Mode'].value_counts().index[0] if 'Pay Mode' in df.columns and not df['Pay Mode'].value_counts().empty else "N/A"

        pdf.add_metric("Top Pickup Location", top_pickup_location, "Most frequent pickup location for trips.")
        pdf.add_metric("Top Dropoff Location", top_dropoff_location, "Most frequent dropoff location for trips.")
        pdf.add_metric("Peak Hour", peak_hour, "Hour of the day with the highest number of trips.")
        pdf.add_metric("Primary Payment Method", primary_payment_method, "Most commonly used payment method by customers.")

        return pdf
    except Exception as e:
        st.error(f"Error in create metrics pdf: {str(e)}")
        return PDF()
