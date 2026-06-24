import os
import urllib.request
import pandas as pd
import yfinance as yf
from datetime import datetime

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')
pkl_dir = os.path.join(data_dir, 'data_raw')


if not os.path.exists(pkl_dir):
    os.makedirs(pkl_dir)

metadata_csv = os.path.join(data_dir, 'ticker_metadata.csv')
sp500_csv = os.path.join(data_dir, 'sp500_quarterly_history.csv')
nasdaq_csv = os.path.join(data_dir, 'nasdaq_quarterly_history.csv')
comparison_csv = os.path.join(data_dir, 'nasdaq_not_sp500_quarterly.csv')

# 2. Extract all unique tickers
print("Scanning constituent CSV files for unique tickers...")
all_tickers = set()

for path in [sp500_csv, nasdaq_csv, comparison_csv]:
    if os.path.exists(path):
        df = pd.read_csv(path)
        # Parse constituents column
        cols_to_check = ['Constituents', 'Unique_Nasdaq_Tickers']
        for col in cols_to_check:
            if col in df.columns:
                for val in df[col]:
                    if pd.notna(val):
                        all_tickers.update([t.strip() for t in str(val).split(',') if t.strip()])

all_tickers = sorted(list(all_tickers))
print(f"Total unique tickers identified across indices: {len(all_tickers)}")

# 3. Load metadata cache
metadata_cache = {}
if os.path.exists(metadata_csv):
    try:
        df_meta = pd.read_csv(metadata_csv)
        for idx, row in df_meta.iterrows():
            ticker = row['Ticker']
            metadata_cache[ticker] = {
                'Shares_Outstanding': row['Shares_Outstanding'],
                'Market_Cap': row['Market_Cap']
            }
        print(f"Loaded {len(metadata_cache)} tickers from metadata cache.")
    except Exception as e:
        print(f"Error reading metadata cache: {e}")

# 4. Check for missing PKL price files and metadata
missing_pkls = []
missing_metadata = []

for ticker in all_tickers:
    pkl_file = os.path.join(pkl_dir, f"{ticker}.pkl")
    if not os.path.exists(pkl_file):
        missing_pkls.append(ticker)
    if ticker not in metadata_cache:
        missing_metadata.append(ticker)

print(f"Missing price PKL files: {len(missing_pkls)}")
print(f"Missing metadata: {len(missing_metadata)}")

# 5. Fetch missing price histories
if missing_pkls:
    print(f"\nStarting download of {len(missing_pkls)} missing price histories...")
    # yfinance has automatic auto_adjust, download individually or in small batches
    for idx, ticker in enumerate(missing_pkls):
        pkl_file = os.path.join(pkl_dir, f"{ticker}.pkl")
        print(f"[{idx+1}/{len(missing_pkls)}] Downloading {ticker}...")
        try:
            # Fetch maximum available history
            df_price = yf.download(ticker, start='1996-01-01', auto_adjust=False, progress=False)

            if not df_price.empty:
                df_price.to_pickle(pkl_file)
            else:
                print(f"  Warning: No price data returned for {ticker}.")
        except Exception as e:
            print(f"  Error downloading {ticker}: {e}")

# 6. Fetch missing metadata (current shares outstanding and market cap)
if missing_metadata:
    print(f"\nStarting download of {len(missing_metadata)} missing ticker metadata...")
    for idx, ticker in enumerate(missing_metadata):
        print(f"[{idx+1}/{len(missing_metadata)}] Fetching metadata for {ticker}...")
        try:
            t_obj = yf.Ticker(ticker)
            info = t_obj.info
            shares = info.get('sharesOutstanding', np.nan if 'np' in globals() else float('nan'))
            mcap = info.get('marketCap', np.nan if 'np' in globals() else float('nan'))
            
            # fallback if yfinance returns None
            if shares is None: shares = float('nan')
            if mcap is None: mcap = float('nan')
            
            metadata_cache[ticker] = {
                'Shares_Outstanding': shares,
                'Market_Cap': mcap
            }
        except Exception as e:
            print(f"  Error fetching metadata for {ticker}: {e}")
            metadata_cache[ticker] = {
                'Shares_Outstanding': float('nan'),
                'Market_Cap': float('nan')
            }
            
    # Save updated metadata file
    meta_rows = []
    for ticker, data in metadata_cache.items():
        meta_rows.append({
            'Ticker': ticker,
            'Shares_Outstanding': data['Shares_Outstanding'],
            'Market_Cap': data['Market_Cap']
        })
    df_meta_new = pd.DataFrame(meta_rows)
    df_meta_new.to_csv(metadata_csv, index=False)
    print(f"Saved updated metadata to: {metadata_csv}")

print("\nData check complete!")
