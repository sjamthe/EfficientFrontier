import os
import pandas as pd
import numpy as np

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'SP500')
nasdaq20_csv = os.path.join(data_dir, 'nasdaq_20_quarterly.csv')
pkl_dir = os.path.join(data_dir, 'data_raw')
metadata_path = os.path.join(data_dir, 'ticker_metadata.csv')

df_candidates = pd.read_csv(nasdaq20_csv)
df_meta = pd.read_csv(metadata_path)
metadata = dict(zip(df_meta['Ticker'], df_meta['Shares_Outstanding']))

# Gather unique tickers
unique_tickers = set()
for idx, row in df_candidates.iterrows():
    consts = [t.strip() for t in str(row['Candidates']).split(',') if t.strip()]
    unique_tickers.update(consts)

unique_tickers = sorted(list(unique_tickers))

# Load price histories (using Adj Close for Total Return, fallback to Close)
price_dict = {}
col_to_use = 'Adj Close'
for ticker in unique_tickers:
    pkl_path = os.path.join(pkl_dir, f"{ticker}.pkl")
    if os.path.exists(pkl_path):
        try:
            df_t = pd.read_pickle(pkl_path)
            if (col_to_use, ticker) in df_t.columns:
                series = df_t[(col_to_use, ticker)]
            elif col_to_use in df_t.columns:
                series = df_t[col_to_use]
            elif ('Close', ticker) in df_t.columns:
                series = df_t[('Close', ticker)]
            elif 'Close' in df_t.columns:
                series = df_t['Close']
            else:
                continue
            price_dict[ticker] = series
        except Exception:
            pass

df_prices = pd.DataFrame(price_dict)
df_prices.index = pd.to_datetime(df_prices.index)
df_prices = df_prices.sort_index()

# Clean price data (same logic as calculate_returns)
df_prices = df_prices.mask(df_prices > 10000, np.nan)
df_prices = df_prices.ffill().bfill(limit=5)

df_stock_returns = df_prices.pct_change(fill_method=None)
bad_returns_mask = (df_stock_returns > 1.0) | (df_stock_returns < -0.9)
df_stock_returns = df_stock_returns.mask(bad_returns_mask, 0.0)

current_portfolio_value = 6000000.0
holdings_list = []

for idx, row in df_candidates.iterrows():
    q_name = row['Quarter']
    q_start = row['Start_Date']
    q_end = row['End_Date']
    
    q_constituents = [t.strip() for t in str(row['Candidates']).split(',') if t.strip()]
    q_constituents = [t for t in q_constituents if t in df_prices.columns]
    
    if not q_constituents:
        continue
        
    q_days = df_prices.index[(df_prices.index >= q_start) & (df_prices.index <= q_end)]
    if len(q_days) == 0:
        continue
        
    first_day = q_days[0]
    active_prices = df_prices.loc[first_day, q_constituents]
    valid_constituents = active_prices.dropna().index.tolist()
    
    if not valid_constituents:
        continue
        
    # Cap-weighted proxy logic
    mcap_proxies = {}
    for t in valid_constituents:
        shares = metadata.get(t, np.nan)
        if pd.isna(shares) or shares <= 0:
            shares = 1.0
        mcap_proxies[t] = active_prices[t] * shares
        
    sum_mcap = sum(mcap_proxies.values())
    if sum_mcap > 0:
        weights = pd.Series({t: mcap_proxies[t] / sum_mcap for t in valid_constituents})
    else:
        weights = pd.Series({t: 1.0 / len(valid_constituents) for t in valid_constituents})
        
    # Apply weight capping and re-normalize
    weights = weights.clip(upper=0.10)
    weights = weights / weights.sum()
    
    # Save rebalancing holdings details
    for ticker in valid_constituents:
        w = weights[ticker]
        holdings_list.append({
            'Quarter': q_name,
            'Rebalance_Date': first_day.strftime('%Y-%m-%d'),
            'Ticker': ticker,
            'Weight_Pct': w * 100.0,
            'Amount_USD': w * current_portfolio_value,
            'Total_Portfolio_Value_USD': current_portfolio_value
        })
        
    # Update running portfolio value throughout the quarter daily
    for t in q_days:
        daily_stock_ret = df_stock_returns.loc[t, valid_constituents].fillna(0.0)
        port_ret = np.sum(weights * daily_stock_ret)
        current_portfolio_value = current_portfolio_value * (1.0 + port_ret)

df_holdings = pd.DataFrame(holdings_list)
# Sort by Quarter and then Weight_Pct descending
df_holdings = df_holdings.sort_values(['Quarter', 'Weight_Pct'], ascending=[True, False]).reset_index(drop=True)

output_csv = os.path.join(data_dir, 'nasdaq20_quarterly_holdings.csv')
df_holdings.to_csv(output_csv, index=False)
print(f"Saved holdings details to {output_csv}")
print("Sample of first 15 rows:")
print(df_holdings.head(15).to_string(index=False))
print("\nSample of 2026Q3 holdings:")
print(df_holdings[df_holdings['Quarter'] == '2026Q3'].to_string(index=False))
