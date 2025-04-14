import yfinance as yf
import pandas as pd
import streamlit as st
import base64
from io import BytesIO
from PIL import Image
import math
import logging # Use logging for cleaner error/info messages

# --- Configuration ---
# Use logging instead of just print/st.error for more structured output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants for file paths and default values
LOGO_PATH = "ppl_logo.jpg"
BACKGROUND_PATH = "wp.jpg"
DEFAULT_TICKERS = "GOOGL,AAPL,MSFT,AMZN" # Example default tickers
FINANCIAL_COLUMNS_TO_SELECT = [
    # Profile Info (Merged)
    'Ticker', 'LongName', 'Long_Business_Summary', 'Country', 'Sector', 'Industry',
    'Full_Time_Employees', 'Website', 'Phone',
    # Financial Info
    'Full_Date', 'Year_Index', 'Currency', 'Financial_Currency',
    # Key Financial Metrics (Ensure these match yfinance output)
    'Total Revenue', 'Operating Revenue', 'Cost Of Revenue', 'Gross Profit',
    'Operating Expense', 'Selling General and Administrative', # Often listed under Operating Expense
    'Selling General And Administration', # Check if yfinance uses this exact name
    'Operating Income', 'EBIT', 'Normalized EBITDA', # EBIT/EBITDA might not always be directly available or need calculation
    'Net Income'
]

# --- Helper Functions ---

def set_background(image_file: str):
    """Sets the background image for the Streamlit app."""
    try:
        with open(image_file, "rb") as file:
            encoded_string = base64.b64encode(file.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url(data:image/png;base64,{encoded_string});
                background-size: cover;
                background-repeat: no-repeat;
                background-attachment: fixed; /* Keeps background fixed during scroll */
            }}
            /* Make headers slightly transparent white for better visibility */
            h1, h2, h3, h4, h5, h6 {{
                 color: white;
                 background-color: rgba(0, 0, 0, 0.3); /* Slight dark overlay */
                 padding: 5px;
                 border-radius: 5px;
            }}
             /* Style buttons */
            .stButton>button {{
                color: #4F8BF9; /* Button text color */
                background-color: #FFFFFF; /* Button background color */
                border: 1px solid #4F8BF9; /* Button border */
                border-radius: 5px;
                padding: 0.5em 1em;
            }}
            .stButton>button:hover {{
                background-color: #E6E6E6; /* Slightly darker on hover */
                color: #3F6EBD;
                border-color: #3F6EBD;
            }}
            /* Style text input/area */
            .stTextInput>div>div>input, .stTextArea>div>div>textarea {{
                background-color: rgba(255, 255, 255, 0.9); /* Slightly transparent white */
                border-radius: 5px;
            }}
             /* Style dataframes */
            .stDataFrame {{
                 background-color: rgba(255, 255, 255, 0.9);
                 border-radius: 5px;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
        logging.info(f"Background image '{image_file}' set successfully.")
    except FileNotFoundError:
        st.error(f"Background image file not found: {image_file}")
        logging.error(f"Background image file not found: {image_file}")
    except Exception as e:
        st.error(f"Error setting background: {e}")
        logging.error(f"Error setting background: {e}")

def get_financial_data(ticker: str) -> pd.DataFrame:
    """
    Fetches annual and TTM financial data for a given stock ticker using yfinance.

    Args:
        ticker: The stock ticker symbol (e.g., "AAPL").

    Returns:
        A pandas DataFrame containing financial data, including a TTM row.
        Returns a DataFrame with only the 'Ticker' column if an error occurs.
    """
    try:
        logging.info(f"Fetching financial data for {ticker}...")
        stock = yf.Ticker(ticker)
        info = stock.info # Fetch info once

        # --- Annual Data ---
        financials = stock.financials
        if financials.empty:
            st.warning(f"No annual financial data found for {ticker}.")
            return pd.DataFrame({'Ticker': [ticker]})

        df = financials.T.copy() # Transpose for years as rows
        df['Ticker'] = ticker
        df['Full_Date'] = pd.to_datetime(df.index).strftime('%Y-%m-%d') # Format date
        df = df.reset_index(drop=True)
        df['Year_Index'] = df.index + 1 # Annual rows start from 1

        # Add currency info from general info
        df['Currency'] = info.get('currency', 'N/A')
        df['Financial_Currency'] = info.get('financialCurrency', 'N/A')

        # --- TTM Data ---
        q_financials = stock.quarterly_financials
        ttm_data = {'Ticker': ticker, 'Full_Date': "TTM", 'Year_Index': 0}
        ttm_data['Currency'] = info.get('currency', 'N/A')
        ttm_data['Financial_Currency'] = info.get('financialCurrency', 'N/A')

        if not q_financials.empty and q_financials.shape[1] >= 4:
            # Sum the latest four quarters for TTM
            ttm_series = q_financials.iloc[:, :4].sum(axis=1, numeric_only=True)
            # Include only metrics present in the annual data columns
            common_metrics = df.columns.intersection(ttm_series.index)
            for metric in common_metrics:
                 if metric not in ttm_data: # Avoid overwriting Ticker, Date etc.
                    ttm_data[metric] = ttm_series.get(metric) # Use .get for safety
        else:
            st.info(f"Insufficient quarterly data to calculate TTM for {ticker}. TTM financial values set to None.")
            # Set financial metrics to None if TTM cannot be calculated
            financial_metrics = [col for col in df.columns if col not in ['Ticker', 'Full_Date', 'Year_Index', 'Currency', 'Financial_Currency']]
            for metric in financial_metrics:
                ttm_data[metric] = None

        ttm_df = pd.DataFrame([ttm_data])

        # Combine TTM and annual data
        final_df = pd.concat([ttm_df, df], ignore_index=True, sort=False) # Ensure TTM is first

        logging.info(f"Successfully fetched financial data for {ticker}.")
        return final_df

    except Exception as e:
        st.warning(f"Error getting financial data for {ticker}: {e}")
        logging.warning(f"Error getting financial data for {ticker}: {e}")
        # Return a minimal DataFrame to allow merging later
        return pd.DataFrame({'Ticker': [ticker]})

def get_profile_data(ticker: str) -> pd.DataFrame:
    """
    Fetches company profile data for a given stock ticker using yfinance.

    Args:
        ticker: The stock ticker symbol (e.g., "AAPL").

    Returns:
        A pandas DataFrame containing profile data.
        Returns a DataFrame with only the 'Ticker' column if an error occurs.
    """
    try:
        logging.info(f"Fetching profile data for {ticker}...")
        stock = yf.Ticker(ticker)
        info = stock.info

        # Use .get() with default values for robustness
        company_info = {
            'Ticker': ticker,
            'LongName': info.get('longName', 'N/A'),
            'Long_Business_Summary': info.get('longBusinessSummary', 'N/A'),
            'Country': info.get('country', 'N/A'),
            'Sector': info.get('sector', 'N/A'),
            'Industry': info.get('industry', 'N/A'),
            'Full_Time_Employees': info.get('fullTimeEmployees', 'N/A'), # Keep as is or try converting to int/str
            'Website': info.get('website', 'N/A'),
            'Phone': info.get('phone', 'N/A')
        }
        # Convert employees to string for consistent display, handling None/missing
        company_info['Full_Time_Employees'] = str(company_info['Full_Time_Employees']) if company_info['Full_Time_Employees'] != 'N/A' else 'N/A'


        logging.info(f"Successfully fetched profile data for {ticker}.")
        return pd.DataFrame([company_info])

    except Exception as e:
        st.warning(f"Error getting profile data for {ticker}: {e}")
        logging.warning(f"Error getting profile data for {ticker}: {e}")
        # Return a minimal DataFrame to allow merging later
        return pd.DataFrame({'Ticker': [ticker]})

def create_excel_download(df: pd.DataFrame, filename: str) -> bytes:
    """Creates an Excel file in memory for downloading."""
    output = BytesIO()
    # Use ExcelWriter to potentially add more sheets or formatting later
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
        # Optional: Auto-adjust column widths (can be slow for large data)
        # worksheet = writer.sheets['Data']
        # for i, col in enumerate(df.columns):
        #     column_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
        #     worksheet.set_column(i, i, column_len)
    return output.getvalue()

# --- Streamlit App ---

# Page Configuration (do this first)
st.set_page_config(
    page_title="Phronesis Pulse 2.0",
    page_icon="📊", # Add a relevant emoji icon
    layout="wide"
)

# Apply background image
set_background(BACKGROUND_PATH)

# --- Header ---
col_logo, col_title = st.columns([1, 5]) # Adjust ratio as needed

with col_logo:
    try:
        logo = Image.open(LOGO_PATH)
        st.image(logo, width=120) # Slightly larger logo
    except FileNotFoundError:
        st.error(f"Logo image not found: {LOGO_PATH}")
        logging.error(f"Logo image not found: {LOGO_PATH}")
    except Exception as e:
        st.error(f"Error loading logo: {e}")
        logging.error(f"Error loading logo: {e}")


with col_title:
    st.markdown("<h1 style='text-align: center; margin-top: 20px;'>Phronesis Pulse 2.0</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: lightgrey;'>Financial Data Extractor</p>", unsafe_allow_html=True)


st.markdown("---") # Visual separator

# --- Initialize Session State ---
if 'tickers' not in st.session_state:
    st.session_state.tickers = []
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = pd.DataFrame()
if 'all_extracted_data' not in st.session_state:
    st.session_state.all_extracted_data = pd.DataFrame()


# --- Ticker Input Area ---
st.subheader("1. Enter Stock Tickers")
ticker_input = st.text_area(
    "Enter ticker symbols separated by commas (e.g., GOOGL,AAPL,MSFT). Avoid spaces.",
    value=DEFAULT_TICKERS,
    height=100,
    key="ticker_input_area" # Unique key for the widget
)

if st.button("Load Tickers", key="load_tickers_button"):
    # Basic validation: split, strip whitespace, remove empty strings
    tickers_raw = [ticker.strip().upper() for ticker in ticker_input.split(',') if ticker.strip()]
    if tickers_raw:
        st.session_state.tickers = tickers_raw
        st.success(f"{len(st.session_state.tickers)} tickers loaded: {', '.join(st.session_state.tickers)}")
        # Clear previous results when new tickers are loaded
        st.session_state.processed_data = pd.DataFrame()
        st.session_state.all_extracted_data = pd.DataFrame()
    else:
        st.warning("Please enter valid ticker symbols.")
        st.session_state.tickers = [] # Clear if input is invalid


# --- Data Extraction Section ---
if st.session_state.tickers:
    st.markdown("---")
    st.subheader("2. Configure and Extract Data")

    # Batch size selection (optional, consider removing if not strictly needed or if ticker list is usually small)
    # max_tickers_per_batch = st.slider(
    #     "Select maximum tickers per processing batch (if needed)",
    #     1, len(st.session_state.tickers),
    #     min(10, len(st.session_state.tickers)), # Default to 10 or total, whichever is smaller
    #     key="batch_slider"
    # )
    # num_batches = math.ceil(len(st.session_state.tickers) / max_tickers_per_batch)

    if st.button("Extract Financial Data", key="extract_data_button"):
        all_financial_dfs = []
        all_profile_dfs = []
        failed_tickers = []
        total_tickers_to_process = len(st.session_state.tickers)

        st.info(f"Starting data extraction for {total_tickers_to_process} tickers...")
        progress_bar = st.progress(0)
        status_text = st.empty() # Placeholder for status updates

        # Process all tickers in one go (removed batching for simplicity unless necessary)
        for i, ticker in enumerate(st.session_state.tickers):
            status_text.text(f"Processing {ticker} ({i+1}/{total_tickers_to_process})...")

            profile_df = get_profile_data(ticker)
            financial_df = get_financial_data(ticker)

            # Check if data fetching was successful (minimal df indicates failure)
            if len(profile_df.columns) > 1: # More than just 'Ticker'
                 all_profile_dfs.append(profile_df)
            else:
                 failed_tickers.append(f"{ticker} (profile)")

            if len(financial_df.columns) > 1: # More than just 'Ticker'
                all_financial_dfs.append(financial_df)
            # No separate else for financial, as profile failure is more critical for merge
            elif f"{ticker} (profile)" not in failed_tickers: # Avoid double counting if profile also failed
                 failed_tickers.append(f"{ticker} (financial)")


            # Update progress
            progress = (i + 1) / total_tickers_to_process
            progress_bar.progress(progress)

        status_text.success(f"Data extraction complete for {total_tickers_to_process} tickers.")
        progress_bar.empty() # Remove progress bar after completion

        if failed_tickers:
            st.warning(f"Could not retrieve complete data for: {', '.join(failed_tickers)}")

        if not all_profile_dfs or not all_financial_dfs:
            st.error("No data could be extracted. Please check tickers and network connection.")
            st.session_state.processed_data = pd.DataFrame()
            st.session_state.all_extracted_data = pd.DataFrame()
        else:
            # --- Consolidate and Process Data ---
            st.markdown("---")
            st.subheader("3. Processed Results")

            # Combine all successfully fetched dataframes
            combined_profile_df = pd.concat(all_profile_dfs, ignore_index=True)
            combined_financial_df = pd.concat(all_financial_dfs, ignore_index=True)

            # Merge profile and financial data
            # Use 'outer' merge to keep tickers even if one part failed, though checks above should minimize this
            final_df = pd.merge(combined_profile_df, combined_financial_df, on='Ticker', how='inner') # Use 'inner' if both profile and financial are required

            if final_df.empty:
                st.error("Data merging resulted in an empty DataFrame. Check fetched data.")
                st.session_state.processed_data = pd.DataFrame()
                st.session_state.all_extracted_data = pd.DataFrame()

            else:
                # Store the full merged data before selecting columns
                st.session_state.all_extracted_data = final_df.copy()

                # Select and Order Display Columns
                # Get columns that actually exist in the merged dataframe
                existing_display_columns = [col for col in FINANCIAL_COLUMNS_TO_SELECT if col in final_df.columns]
                missing_display_columns = [col for col in FINANCIAL_COLUMNS_TO_SELECT if col not in final_df.columns]

                if missing_display_columns:
                     st.info(f"Note: The following requested columns were not found in the data and will be omitted: {', '.join(missing_display_columns)}")

                # Create the display dataframe
                final_display_dt = final_df[existing_display_columns]

                # Store the processed data for display
                st.session_state.processed_data = final_display_dt

# --- Display Results and Download ---
if not st.session_state.processed_data.empty:
    st.markdown("---")
    st.subheader("4. View and Download Data")

    st.dataframe(st.session_state.processed_data)

    # --- Download Buttons ---
    col_dl1, col_dl2 = st.columns(2)

    with col_dl1:
        # Download Button for Displayed/Formatted Data
        try:
            excel_display_data = create_excel_download(
                st.session_state.processed_data,
                "Pulse_yf_FormattedData.xlsx"
            )
            st.download_button(
                label="📥 Download Displayed Data (Excel)",
                data=excel_display_data,
                file_name='Pulse_yf_FormattedData.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key="download_display_button"
            )
        except Exception as e:
            st.error(f"Error creating displayed data download file: {e}")
            logging.error(f"Error creating displayed data download file: {e}")


    with col_dl2:
       # Download Button for All Extracted Data
       if not st.session_state.all_extracted_data.empty:
            try:
                # Optional: Reorder columns for the "All Data" file (display columns first)
                all_cols = st.session_state.all_extracted_data.columns.tolist()
                ordered_cols = [col for col in FINANCIAL_COLUMNS_TO_SELECT if col in all_cols] + \
                               [col for col in all_cols if col not in FINANCIAL_COLUMNS_TO_SELECT]
                all_data_ordered = st.session_state.all_extracted_data[ordered_cols]

                excel_all_data = create_excel_download(
                    all_data_ordered, # Use the reordered dataframe
                    "Pulse_yf_AllExtractedData.xlsx"
                )
                st.download_button(
                    label="📦 Download All Extracted Data (Excel)",
                    data=excel_all_data,
                    file_name='Pulse_yf_AllExtractedData.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key="download_all_button"
                )
            except Exception as e:
                 st.error(f"Error creating all data download file: {e}")
                 logging.error(f"Error creating all data download file: {e}")


    # --- Summary Statistics ---
    st.markdown("---")
    st.subheader("Extraction Summary")
    total_submitted = len(st.session_state.tickers)
    successful_tickers = st.session_state.processed_data['Ticker'].nunique() # Count unique tickers in the final display DF
    failed_count = total_submitted - successful_tickers

    st.metric("Tickers Submitted", total_submitted)
    st.metric("Tickers Successfully Processed", successful_tickers)
    st.metric("Tickers with Issues", failed_count)

elif 'tickers' in st.session_state and st.session_state.tickers:
    # Show this only if tickers are loaded but no data is processed yet
    # (or if processing failed completely)
    st.info("Click 'Extract Financial Data' to begin.")

# Optional: Footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: grey; font-size: small;'>Phronesis Pulse v2.0 - Powered by yfinance and Streamlit</p>", unsafe_allow_html=True)
