import os
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')
sp500_quarters_csv = os.path.join(data_dir, 'sp500_quarterly_history.csv')
nasdaq_quarters_csv = os.path.join(data_dir, 'nasdaq_quarterly_history.csv')
classification_csv = os.path.join(data_dir, 'ticker_classification.csv')
output_candidates_csv = os.path.join(data_dir, 'nasdaq_candidate_queue.csv')

if not os.path.exists(sp500_quarters_csv) or not os.path.exists(nasdaq_quarters_csv):
    raise FileNotFoundError("Missing required index history files. Please run components scripts first.")

# Load histories
df_sp500 = pd.read_csv(sp500_quarters_csv)
df_ndx = pd.read_csv(nasdaq_quarters_csv)

# Align date parsing
df_sp500['Year'] = df_sp500['Quarter'].str[:4].astype(int)
df_sp500['Q'] = df_sp500['Quarter'].str[5].astype(int)
df_sp500 = df_sp500.sort_values(['Year', 'Q']).reset_index(drop=True)

df_ndx['Year'] = df_ndx['Quarter'].str[:4].astype(int)
df_ndx['Q'] = df_ndx['Quarter'].str[5].astype(int)
df_ndx = df_ndx.sort_values(['Year', 'Q']).reset_index(drop=True)

# 2. Identify all unique tickers in the datasets (focusing from 2006 onwards)
unique_tickers = set()
for df in [df_sp500, df_ndx]:
    for col in ['Constituents', 'Additions', 'Removals']:
        if col in df.columns:
            for val in df[col]:
                if pd.notna(val):
                    unique_tickers.update([t.strip() for t in str(val).split(',') if t.strip()])

unique_tickers = sorted(list(unique_tickers))
print(f"Total unique tickers to classify: {len(unique_tickers)}")

# 3. Load or build ticker classifications (exchange and sector)
classification_map = {}
if os.path.exists(classification_csv):
    print(f"Loading existing classifications from: {classification_csv}")
    df_class = pd.read_csv(classification_csv)
    for idx, row in df_class.iterrows():
        classification_map[row['Ticker']] = {
            'Exchange': row['Exchange'],
            'Sector': row['Sector'],
            'Source': row['Source']
        }
else:
    print("No classification cache found. We will build one.")

# Set of known delisted financials to assist the heuristic fallback
known_delisted_financials = {
    'LEH', 'BSC', 'WM', 'CFC', 'MER', 'FNMA', 'FMCC', 'AEGON', 'AGE',
    'AMTD', 'ASO', 'AV', 'AXA', 'BEE', 'BK', 'CB', 'CMA', 'FAF', 'FHN',
    'FITB', 'GGP', 'HCBK', 'KEY', 'L', 'LFC', 'LM', 'MET', 'MBI', 'MTG',
    'NCC', 'NTRS', 'NYB', 'PBCT', 'PGR', 'PNC', 'RF', 'SLM', 'SOV', 'STT',
    'SYF', 'USB', 'WFC', 'ZION', 'AIG', 'BAC', 'C', 'GS', 'MS', 'JPM',
    'MCO', 'SPGI', 'SCHW', 'TROW', 'BEN', 'AMP', 'AXP', 'COF', 'DFS',
    'Capital One', 'Bear Stearns', 'Lehman', 'Merrill'
}

# Nasdaq symbol length rule holds true for >99% of historical stocks in our database
# 4+ letters = Nasdaq, 3 or less letters = NYSE
def classify_ticker_heuristic(ticker):
    is_nasdaq = len(ticker) >= 4
    is_financial = ticker in known_delisted_financials
    return {
        'Exchange': 'NASDAQ' if is_nasdaq else 'NYSE',
        'Sector': 'Financial' if is_financial else 'Non-Financial',
        'Source': 'heuristic'
    }

# Helper function for parallel querying
def fetch_classification(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        exchange = info.get('exchange', 'UNKNOWN').upper()
        sector = info.get('sector', 'UNKNOWN')
        
        is_nasdaq = any(x in exchange for x in ['NASDAQ', 'NMS', 'NGS', 'NCM'])
        is_financial = any(x in str(sector).lower() for x in ['financial', 'bank', 'insurance', 'capital market'])
        
        return ticker, {
            'Exchange': 'NASDAQ' if is_nasdaq else 'NYSE',
            'Sector': 'Financial' if is_financial or ticker in known_delisted_financials else 'Non-Financial',
            'Source': 'yfinance'
        }
    except Exception:
        # Fallback to heuristic
        is_nasdaq = len(ticker) >= 4
        is_financial = ticker in known_delisted_financials
        return ticker, {
            'Exchange': 'NASDAQ' if is_nasdaq else 'NYSE',
            'Sector': 'Financial' if is_financial else 'Non-Financial',
            'Source': 'heuristic'
        }

# Query classifications for missing tickers in parallel
missing_tickers = [t for t in unique_tickers if t not in classification_map]
if missing_tickers:
    print(f"Querying Yahoo Finance in parallel for {len(missing_tickers)} missing classifications...")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_classification, t): t for t in missing_tickers}
        for i, future in enumerate(as_completed(futures)):
            ticker, res = future.result()
            classification_map[ticker] = res
            if i % 100 == 0 and i > 0:
                print(f"  Processed {i}/{len(missing_tickers)} classifications...")

    # Save cache
    rows_to_save = []
    for ticker, info in sorted(classification_map.items()):
        rows_to_save.append({
            'Ticker': ticker,
            'Exchange': info['Exchange'],
            'Sector': info['Sector'],
            'Source': info['Source']
        })
    df_save = pd.DataFrame(rows_to_save)
    df_save.to_csv(classification_csv, index=False)
    print(f"Saved updated classifications to: {classification_csv}")

# 4. Generate Candidate Queue history quarter-by-quarter
print("\nExtracting candidate queues quarter-by-quarter...")
results = []

# Find common quarters starting from 2007 (matching NASDAQ-100 start in our dataset)
sp500_quarters = set(df_sp500['Quarter'])
ndx_quarters = set(df_ndx['Quarter'])
common_quarters = sorted(list(sp500_quarters.intersection(ndx_quarters)))

for q_name in common_quarters:
    row_sp = df_sp500[df_sp500['Quarter'] == q_name].iloc[0]
    row_ndx = df_ndx[df_ndx['Quarter'] == q_name].iloc[0]
    
    # Parse constituents
    sp_tkrs = {t.strip() for t in str(row_sp['Constituents']).split(',') if t.strip()}
    ndx_tkrs = {t.strip() for t in str(row_ndx['Constituents']).split(',') if t.strip()}
    
    # Filter S&P 500 constituents to only U.S. Nasdaq-listed non-financials
    eligible_sp = []
    for t in sp_tkrs:
        info = classification_map.get(t)
        if info:
            if info['Exchange'] == 'NASDAQ' and info['Sector'] == 'Non-Financial':
                eligible_sp.append(t)
                
    eligible_sp = set(eligible_sp)
    
    # Candidate queue is: eligible S&P 500 stocks not yet in NASDAQ-100
    candidates = eligible_sp - ndx_tkrs
    candidates_sorted = sorted(list(candidates))
    
    # We want to identify if any candidate was added in the next quarter (lead indicator for label)
    # Find next quarter name
    curr_idx = common_quarters.index(q_name)
    added_next_q = []
    if curr_idx < len(common_quarters) - 1:
        next_q_name = common_quarters[curr_idx + 1]
        next_row_ndx = df_ndx[df_ndx['Quarter'] == next_q_name].iloc[0]
        next_ndx_additions = {t.strip() for t in str(next_row_ndx['Additions']).split(',') if t.strip()}
        added_next_q = [t for t in candidates_sorted if t in next_ndx_additions]
        
    results.append({
        'Quarter': q_name,
        'Start_Date': row_sp['Start_Date'],
        'End_Date': row_sp['End_Date'],
        'SP500_Nasdaq_NonFin_Count': len(eligible_sp),
        'Candidate_Queue_Count': len(candidates),
        'Candidates': ','.join(candidates_sorted),
        'Added_Next_Quarter_Count': len(added_next_q),
        'Added_Next_Quarter_Tickers': ','.join(added_next_q)
    })

df_queue = pd.DataFrame(results)
df_queue.to_csv(output_candidates_csv, index=False)
print(f"\nSuccessfully generated candidate queue history and saved to: {output_candidates_csv}")

# Print summary of the last 8 quarters
print("\nSummary of the last 8 quarters:")
cols_to_print = ['Quarter', 'SP500_Nasdaq_NonFin_Count', 'Candidate_Queue_Count', 'Added_Next_Quarter_Count', 'Added_Next_Quarter_Tickers']
print(df_queue[cols_to_print].tail(8).to_string(index=False))
