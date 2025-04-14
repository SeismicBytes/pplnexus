import yfinance as yf
import pandas as pd
import streamlit as st
import base64
from io import BytesIO
from PIL import Image
import math
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

def login_to_firewall():
    # Configure Chrome options to handle SSL certificate errors
    chrome_options = Options()
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--start-maximized')

    # Add this option to prevent the browser from closing
    chrome_options.add_experimental_option("detach", True)

    # Initialize the Chrome driver with options
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Navigate to the login page
        driver.get("https://10.1.1.1:4443/sonicui/7/login/#/")

        # Wait for the username field to be present using the correct class name
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username']"))
        )

        # Find password field using the correct class name
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password']")

        # Enter fixed credentials
        username_field.send_keys("ci-pteam")
        password_field.send_keys("C!-pte@m#2()22")

        # Find and click the login button using the correct class
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.sw-login__trigger"))
        )
        login_button.click()

        # Wait for and click the Continue button
        continue_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue')]"))
        )
        continue_button.click()

        # Wait for successful login
        time.sleep(5)  # Adding a fixed wait time to ensure page loads

        st.success("Successfully logged in!")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

def set_background(image_file):
    with open(image_file, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url(data:image/png;base64,{encoded_string});
            background-size: cover;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

def get_financial_data(ticker):
    try:
        # Initialize ticker object
        stock = yf.Ticker(ticker)

        # Get annual financial data
        financials = stock.financials
        if financials.empty:
            return pd.DataFrame({'Ticker': [ticker]})
        # Transpose so that rows become dates
        df = financials.T.copy()
        df['Ticker'] = ticker

        # Add date information
        df['Full_Date'] = df.index
        # We will reset Year_Index later so that annual rows start from 1

        # Get currency information from info
        info = stock.info
        df['Currency'] = info.get('currency', 'Unknown')
        df['Financial_Currency'] = info.get('financialCurrency', 'Unknown')

        # Compute TTM row from quarterly_financials if available
        q_financials = stock.quarterly_financials
        if (not q_financials.empty) and (q_financials.shape[1] >= 4):
            # Sum the first four quarters for each metric.
            # (If needed, adjust the ordering so you use the latest four quarters.)
            ttm_series = q_financials.iloc[:, :4].sum(axis=1)
            # Only include metrics that appear in the annual data
            common_metrics = [metric for metric in df.columns if metric in ttm_series.index]
            ttm_data = {metric: ttm_series[metric] for metric in common_metrics}
        else:
            # If quarterly data is not available, set financial metrics to None
            ttm_data = {metric: None for metric in df.columns if metric not in ['Ticker', 'Full_Date', 'Currency', 'Financial_Currency']}

        # Add the extra columns for TTM row
        ttm_data['Ticker'] = ticker
        ttm_data['Full_Date'] = "TTM"
        # Currency fields from the same info as above
        ttm_data['Currency'] = info.get('currency', 'Unknown')
        ttm_data['Financial_Currency'] = info.get('financialCurrency', 'Unknown')

        # Create a DataFrame for the TTM row
        ttm_df = pd.DataFrame([ttm_data])

        # Re-index the annual rows so that their Year_Index starts from 1
        df = df.reset_index(drop=True)
        df['Year_Index'] = df.index + 1

        # Set TTM row’s Year_Index to 0
        ttm_df['Year_Index'] = 0

        # Concatenate TTM row at the top
        final_df = pd.concat([ttm_df, df], ignore_index=True)

        return final_df

    except Exception as e:
        st.warning(f"Error getting financial data for {ticker}: {e}")
        return pd.DataFrame({'Ticker': [ticker]})

def get_profile_data(ticker):
    try:
        # Initialize ticker object
        stock = yf.Ticker(ticker)
        info = stock.info

        company_info = {
            'Ticker': ticker,
            'LongName': info.get('longName', ''),
            'Long_Business_Summary': info.get('longBusinessSummary', ''),
            'Country': info.get('country', 'Not Found'),
            'Sector': info.get('sector', ''),
            'Industry': info.get('industry', ''),
            'Full_Time_Employees': str(info.get('fullTimeEmployees', '')),
            'Website': info.get('website', ''),
            'Phone': info.get('phone', '')
        }

        return pd.DataFrame([company_info])
    except Exception as e:
        st.warning(f"Error getting profile data for {ticker}: {e}")
        return pd.DataFrame({'Ticker': [ticker]})
    
# Streamlit app setup
st.set_page_config(page_title="Phronesis Pulse 2.0", layout="wide")

# Set background image
set_background('wp.jpg')

# Header layout with three columns
col1, col2, col3 = st.columns([1, 4, 1])

with col1:
    try:
        logo = Image.open("ppl_logo.jpg")
        st.image(logo, width=100)
    except FileNotFoundError:
        st.error("Logo image not found. Please make sure 'ppl_logo.jpg' is in the same directory.")

with col2:
    st.markdown("<h1 style='text-align: center; color: white;'>Phronesis Pulse 2.0</h1>", unsafe_allow_html=True)

with col3:
    if st.button("Login to Firewall", key="firewall_login"):
        with st.spinner("Logging into firewall..."):
            login_to_firewall()

# Initialize session state
if 'tickers' not in st.session_state:
    st.session_state.tickers = []

# Ticker input
ticker_input = st.text_area("Enter tickers (comma-separated & without spaces)", "GOOGL,AAPL,ARTNA")

if st.button("Submit Tickers"):
    st.session_state.tickers = [ticker.strip() for ticker in ticker_input.split(',')]
    st.success(f"Tickers submitted: {len(st.session_state.tickers)}")

st.write(f"Number of tickers submitted: {len(st.session_state.tickers)}")

if st.session_state.tickers:
    max_tickers_per_batch = st.slider("Select the maximum number of tickers per batch", 
                                     1, len(st.session_state.tickers), 
                                     min(10, len(st.session_state.tickers)))

    num_batches = math.ceil(len(st.session_state.tickers) / max_tickers_per_batch)
    num_batches = min(num_batches, 3)

    if st.button("Extract Data"):
        all_financial_dfs = []
        all_profile_dfs = []

        for batch in range(num_batches):
            start_idx = batch * max_tickers_per_batch
            end_idx = min((batch + 1) * max_tickers_per_batch, len(st.session_state.tickers))
            batch_tickers = st.session_state.tickers[start_idx:end_idx]

            st.subheader(f"Processing Batch {batch + 1}")

            financial_dfs = []
            profile_dfs = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            total_tickers = len(batch_tickers)

            for i, ticker in enumerate(batch_tickers):
                status_text.text(f"Extracting data for {ticker}...")
                financial_df = get_financial_data(ticker)
                profile_df = get_profile_data(ticker)
                financial_dfs.append(financial_df)
                profile_dfs.append(profile_df)

                progress = (i + 1) / total_tickers
                progress_bar.progress(progress)
                status_text.text(f"{i+1}/{total_tickers} tickers processed ({progress*100:.0f}%)")

            combined_financial_df = pd.concat(financial_dfs, ignore_index=True)
            combined_profile_df = pd.concat(profile_dfs, ignore_index=True)

            final_df = pd.merge(combined_profile_df, combined_financial_df, on='Ticker', how='outer')

            columns_to_select = [
                'Ticker', 'Full_Date', 'Year_Index', 'LongName', 'Long_Business_Summary',
                'Currency', 'Financial_Currency', 'Sector', 'Industry',
                'Full_Time_Employees', 'Website', 'Phone', 'Country',
                'Total Revenue', 'Operating Revenue', 'Gross Profit',
                'Operating Expense', 'Selling General and Administrative',
                'EBIT', 'Normalized EBITDA', 'Operating Income',
                'Net Income','Selling General And Administration','Cost Of Revenue'

            ]

            existing_columns = [col for col in columns_to_select if col in final_df.columns]
            Final_DT = final_df[existing_columns]

            st.dataframe(Final_DT)

            # Download buttons for current batch
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                Final_DT.to_excel(writer, index=False, sheet_name='Sheet1')
            processed_data = output.getvalue()

            st.download_button(
                label=f"Download Displayed Columns (Batch {batch + 1})",
                data=processed_data,
                file_name=f'Pulse_yf_FormattedData_Batch{batch + 1}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

            all_financial_dfs.extend(financial_dfs)
            all_profile_dfs.extend(profile_dfs)

        # Consolidate all batches
# --- Consolidated Results Section ---
        st.subheader("Consolidated Results")
        combined_financial_df = pd.concat(all_financial_dfs, ignore_index=True)
        combined_profile_df = pd.concat(all_profile_dfs, ignore_index=True)

        final_df = pd.merge(combined_profile_df, combined_financial_df, on='Ticker', how='outer')

        # Use only the columns_to_select for displayed columns (unchanged)
        existing_columns = [col for col in columns_to_select if col in final_df.columns]
        Final_DT = final_df[existing_columns]
        st.dataframe(Final_DT)

        # Download consolidated displayed columns (unchanged)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            Final_DT.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()

        st.download_button(
            label="Download Consolidated Displayed Columns",
            data=processed_data,
            file_name='Pulse_yf_FormattedData_Consolidated.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # Reorder final_df columns:
        ordered_columns = [col for col in columns_to_select if col in final_df.columns] + \
                        [col for col in final_df.columns if col not in columns_to_select]
        final_df_ordered = final_df[ordered_columns]

        # Download all extracted data file with the reordered columns:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df_ordered.to_excel(writer, index=False, sheet_name='Sheet1')
        processed_data = output.getvalue()

        st.download_button(
            label="Download All Extracted Data (Consolidated)",
            data=processed_data,
            file_name='Pulse_yf_AllData_Consolidated.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        # Summary statistics
        st.subheader("Summary Statistics")
        st.write(f"Total tickers processed: {len(st.session_state.tickers)}")
        st.write(f"Successful extractions: {len(Final_DT)}")
        st.write(f"Failed extractions: {len(st.session_state.tickers) - len(Final_DT)}")