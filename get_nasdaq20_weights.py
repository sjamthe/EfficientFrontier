#!/usr/bin/env python3
import os
import argparse
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

# 1. Path configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'SP500')
metadata_csv = os.path.join(data_dir, 'ticker_metadata.csv')
nasdaq_csv = os.path.join(data_dir, 'nasdaq_quarterly_history.csv')
output_weights_csv = os.path.join(data_dir, 'nasdaq_20_current_weights.csv')

def fetch_constituents_from_wikipedia():
    """Fetch current Nasdaq-100 constituents and company names from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    print(f"Fetching current Nasdaq-100 constituents from Wikipedia: {url}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read()
        tables = pd.read_html(html)
    except Exception as e:
        print(f"Error fetching Wikipedia page: {e}")
        return None

    # Search for the table containing Ticker/Symbol
    df_const = None
    for idx, table in enumerate(tables):
        # Clean column names
        cols = [str(c).strip() for c in table.columns]
        if any(c in ['Ticker', 'Symbol'] for c in cols):
            df_const = table
            # Normalize column names
            df_const.columns = cols
            break
            
    if df_const is None:
        print("Warning: Could not find the constituents table on Wikipedia.")
        return None

    # Identify Ticker and Company columns
    ticker_col = next((c for c in df_const.columns if c in ['Ticker', 'Symbol']), None)
    company_col = next((c for c in df_const.columns if c in ['Company', 'Security', 'Name']), None)

    if not ticker_col:
        print("Warning: Could not find Ticker/Symbol column in Wikipedia table.")
        return None

    df_clean = pd.DataFrame()
    df_clean['Ticker'] = df_const[ticker_col].astype(str).str.strip()
    
    if company_col:
        df_clean['Company'] = df_const[company_col].astype(str).str.strip()
    else:
        df_clean['Company'] = df_clean['Ticker']

    return df_clean

def load_local_history_fallback():
    """Fallback to the latest quarter in our local history if Wikipedia fails."""
    if os.path.exists(nasdaq_csv):
        print(f"Using local history file as fallback: {nasdaq_csv}")
        df = pd.read_csv(nasdaq_csv)
        if not df.empty:
            # Get the latest row
            latest_row = df.iloc[-1]
            tickers = [t.strip() for t in str(latest_row['Constituents']).split(',') if t.strip()]
            df_clean = pd.DataFrame({
                'Ticker': tickers,
                'Company': tickers # Company names not in this file, use ticker as fallback
            })
            print(f"Loaded {len(tickers)} constituents from latest quarter ({latest_row['Quarter']}) in local file.")
            return df_clean
    return None

def main():
    parser = argparse.ArgumentParser(description="Calculate current weights and share allocations for the NASDAQ-20 portfolio.")
    parser.add_argument("-v", "--portfolio-value", type=float, default=None,
                        help="Total dollar value of the portfolio to calculate exact share allocations.")
    parser.add_argument("-w", "--weight-scheme", choices=["cap", "equal"], default="cap",
                        help="Weighting scheme: 'cap' for market capitalization weighted, 'equal' for equal weighted. Default is 'cap'.")
    parser.add_argument("-r", "--refresh-shares", action="store_true",
                        help="Force refresh shares outstanding from yfinance for all constituents (slower, ~1 min).")
    parser.add_argument("-d", "--date", type=str, default=None,
                        help="Query date in YYYY-MM-DD format to get historical constituents and weights.")
    args = parser.parse_args()

    # Step 1: Get constituents
    if args.date:
        query_date_str = args.date
        try:
            query_date = datetime.strptime(query_date_str, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Date format must be YYYY-MM-DD (got: {query_date_str})")
            return
            
        if not os.path.exists(nasdaq_csv):
            print(f"Error: Nasdaq quarterly history file not found at {nasdaq_csv}")
            return
            
        df_hist = pd.read_csv(nasdaq_csv)
        df_hist['Start_Date_parsed'] = pd.to_datetime(df_hist['Start_Date']).dt.date
        df_hist['End_Date_parsed'] = pd.to_datetime(df_hist['End_Date']).dt.date
        
        matching_rows = df_hist[(df_hist['Start_Date_parsed'] <= query_date) & (df_hist['End_Date_parsed'] >= query_date)]
        if not matching_rows.empty:
            matching_row = matching_rows.iloc[0]
            quarter_name = matching_row['Quarter']
            tickers = [t.strip() for t in str(matching_row['Constituents']).split(',') if t.strip()]
            df_const = pd.DataFrame({
                'Ticker': tickers,
                'Company': tickers
            })
            print(f"Found Nasdaq-100 constituents for {query_date_str} in quarter {quarter_name} ({len(tickers)} tickers).")
        else:
            latest_row = df_hist.iloc[-1]
            latest_end = pd.to_datetime(latest_row['End_Date']).date()
            if query_date > latest_end:
                print(f"Query date {query_date_str} is after the latest date in history ({latest_end}). Using latest history row.")
                tickers = [t.strip() for t in str(latest_row['Constituents']).split(',') if t.strip()]
                df_const = pd.DataFrame({
                    'Ticker': tickers,
                    'Company': tickers
                })
            else:
                first_row = df_hist.iloc[0]
                first_start = pd.to_datetime(first_row['Start_Date']).date()
                print(f"Query date {query_date_str} is before the earliest date in history ({first_start}). Using earliest history row.")
                tickers = [t.strip() for t in str(first_row['Constituents']).split(',') if t.strip()]
                df_const = pd.DataFrame({
                    'Ticker': tickers,
                    'Company': tickers
                })
    else:
        df_const = fetch_constituents_from_wikipedia()
        if df_const is None:
            df_const = load_local_history_fallback()
            if df_const is None:
                print("Error: Could not retrieve Nasdaq-100 constituents list. Exiting.")
                return

    tickers = df_const['Ticker'].tolist()
    ticker_to_company = dict(zip(df_const['Ticker'], df_const['Company']))

    # Step 2: Load metadata cache (Shares Outstanding)
    metadata_cache = {}
    if os.path.exists(metadata_csv):
        try:
            df_meta = pd.read_csv(metadata_csv)
            for idx, row in df_meta.iterrows():
                metadata_cache[row['Ticker']] = {
                    'Shares_Outstanding': row['Shares_Outstanding'],
                    'Market_Cap': row['Market_Cap']
                }
        except Exception as e:
            print(f"Warning: Could not read {metadata_csv}: {e}")

    # Step 3: Check which tickers need metadata download
    missing_tickers = []
    if args.refresh_shares:
        missing_tickers = tickers
    else:
        for ticker in tickers:
            if ticker not in metadata_cache or pd.isna(metadata_cache[ticker].get('Shares_Outstanding')):
                missing_tickers.append(ticker)

    # Fetch missing metadata
    cache_updated = False
    if missing_tickers:
        print(f"\nFetching shares outstanding for {len(missing_tickers)} tickers from yfinance...")
        for idx, ticker in enumerate(missing_tickers):
            print(f"[{idx+1}/{len(missing_tickers)}] Fetching {ticker} info...", end="\r")
            try:
                t_obj = yf.Ticker(ticker)
                info = t_obj.info
                shares = info.get('sharesOutstanding', np.nan)
                mcap = info.get('marketCap', np.nan)
                
                # Check for None values
                if shares is None: shares = np.nan
                if mcap is None: mcap = np.nan

                if ticker not in metadata_cache:
                    metadata_cache[ticker] = {}
                metadata_cache[ticker]['Shares_Outstanding'] = shares
                metadata_cache[ticker]['Market_Cap'] = mcap
                cache_updated = True
            except Exception as e:
                pass
        print(f"\nDone fetching metadata.")

    # Save metadata cache if updated
    if cache_updated:
        # Load existing metadata to update rather than overwrite completely
        df_meta_existing = pd.DataFrame()
        if os.path.exists(metadata_csv):
            try:
                df_meta_existing = pd.read_csv(metadata_csv)
            except Exception:
                pass
        
        # Merge new metadata
        new_rows = []
        for ticker, data in metadata_cache.items():
            new_rows.append({
                'Ticker': ticker,
                'Shares_Outstanding': data.get('Shares_Outstanding', np.nan),
                'Market_Cap': data.get('Market_Cap', np.nan)
            })
        df_meta_new = pd.DataFrame(new_rows)
        
        if not df_meta_existing.empty:
            # Combine, keeping the new metadata where available
            df_meta_combined = pd.concat([df_meta_new, df_meta_existing]).drop_duplicates(subset=['Ticker'], keep='first')
        else:
            df_meta_combined = df_meta_new
            
        df_meta_combined = df_meta_combined.sort_values('Ticker')
        df_meta_combined.to_csv(metadata_csv, index=False)
        print(f"Updated metadata cache saved to {metadata_csv}")

    # Step 4: Download stock prices
    if args.date:
        # end_dt is query_date + 1 day (exclusive in yfinance)
        end_dt = query_date + timedelta(days=1)
        # start_dt is query_date - 10 days to guarantee at least one trading day is captured
        start_dt = query_date - timedelta(days=10)
        start_str = start_dt.strftime('%Y-%m-%d')
        end_str = end_dt.strftime('%Y-%m-%d')
        print(f"\nDownloading historical stock prices for {len(tickers)} tickers between {start_str} and {end_str}...")
        try:
            df_prices = yf.download(tickers, start=start_str, end=end_str, progress=False)
        except Exception as e:
            print(f"Error downloading prices in bulk: {e}")
            df_prices = pd.DataFrame()
    else:
        print(f"\nDownloading current stock prices for {len(tickers)} tickers...")
        try:
            df_prices = yf.download(tickers, period='5d', progress=False)
        except Exception as e:
            print(f"Error downloading prices in bulk: {e}")
            # Try a smaller fallback or loop
            df_prices = pd.DataFrame()

    latest_prices = {}
    failed_prices = []
    
    for ticker in tickers:
        price = np.nan
        if not df_prices.empty:
            # Extract price for ticker
            # yfinance download columns are MultiIndex: (Metric, Ticker)
            col_to_use = 'Adj Close'
            if (col_to_use, ticker) in df_prices.columns:
                series = df_prices[(col_to_use, ticker)].dropna()
                if not series.empty:
                    price = series.iloc[-1]
            elif ('Close', ticker) in df_prices.columns:
                series = df_prices[('Close', ticker)].dropna()
                if not series.empty:
                    price = series.iloc[-1]
                    
        # Fallback to individual history if missing
        if pd.isna(price):
            try:
                t_obj = yf.Ticker(ticker)
                if args.date:
                    hist = t_obj.history(start=start_str, end=end_str)
                else:
                    hist = t_obj.history(period='5d')
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
            except Exception:
                pass
                
        if not pd.isna(price) and price > 0:
            latest_prices[ticker] = price
        else:
            failed_prices.append(ticker)

    if failed_prices:
        print(f"Warning: Could not fetch price for tickers: {', '.join(failed_prices)}")

    # Step 5: Compute current market capitalization and select top 20
    valid_constituents = []
    for ticker in tickers:
        price = latest_prices.get(ticker, np.nan)
        shares = metadata_cache.get(ticker, {}).get('Shares_Outstanding', np.nan)
        
        if pd.isna(price) or pd.isna(shares) or shares <= 0:
            continue
            
        mcap = price * shares
        valid_constituents.append({
            'Ticker': ticker,
            'Company': ticker_to_company.get(ticker, ticker),
            'Price': price,
            'Shares_Outstanding': shares,
            'Market_Cap_USD': mcap
        })

    df_universe = pd.DataFrame(valid_constituents)
    if df_universe.empty:
        print("Error: No constituents with valid prices and shares outstanding. Exiting.")
        return

    # Sort descending by market cap and take top 20
    df_top20 = df_universe.sort_values(by='Market_Cap_USD', ascending=False).head(20).reset_index(drop=True)

    # Step 6: Calculate weights
    if args.weight_scheme == 'cap':
        total_mcap = df_top20['Market_Cap_USD'].sum()
        df_top20['Weight'] = df_top20['Market_Cap_USD'] / total_mcap
        # Apply 10% weight ceiling to prevent extreme outlier dominance and re-normalize
        df_top20['Weight'] = df_top20['Weight'].clip(upper=0.10)
        df_top20['Weight'] = df_top20['Weight'] / df_top20['Weight'].sum()
    else:
        df_top20['Weight'] = 0.05 # 5% each

    # Step 7: Calculate allocations if portfolio value is provided
    if args.portfolio_value is not None:
        df_top20['Allocation_USD'] = args.portfolio_value * df_top20['Weight']
        df_top20['Shares_To_Buy'] = df_top20['Allocation_USD'] / df_top20['Price']
        df_top20['Shares_To_Buy_Rounded'] = df_top20['Shares_To_Buy'].round()

    # Save to CSV
    if args.date:
        output_csv_path = os.path.join(data_dir, f'nasdaq_20_weights_{query_date_str}.csv')
    else:
        output_csv_path = output_weights_csv
        
    df_top20.to_csv(output_csv_path, index=False)
    print(f"\nSaved weights to: {output_csv_path}")

    # Step 8: Print beautiful results table
    print("\n" + "=" * 105)
    if args.date:
        print(f"                      NASDAQ-20 PORTFOLIO WEIGHTS & ALLOCATIONS ({query_date_str})")
        print(f"                      Query Date: {query_date_str}")
    else:
        print(f"                      CURRENT NASDAQ-20 PORTFOLIO WEIGHTS & ALLOCATIONS")
        print(f"                      Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"                      Weighting Scheme: {args.weight_scheme.upper()}")
    if args.portfolio_value is not None:
        print(f"                      Total Portfolio Value: ${args.portfolio_value:,.2f}")
    print("=" * 105)
    
    if args.portfolio_value is not None:
        headers = f"{'Rank':<5}{'Ticker':<8}{'Company Name':<30}{'Price':<10}{'Market Cap ($B)':<18}{'Weight (%)':<12}{'Allocation ($)':<16}{'Shares to Buy':<12}"
        print(headers)
        print("-" * 105)
        for idx, row in df_top20.iterrows():
            mcap_b = row['Market_Cap_USD'] / 1e9
            weight_pct = row['Weight'] * 100
            print(f"{idx+1:<5}{row['Ticker']:<8}{row['Company'][:28]:<30}${row['Price']:>8.2f}  ${mcap_b:>13.2f}B  {weight_pct:>9.2f}%    ${row['Allocation_USD']:>12,.2f}  {int(row['Shares_To_Buy_Rounded']):>10}")
        print("-" * 105)
        total_weight_pct = df_top20['Weight'].sum() * 100
        total_allocation = df_top20['Allocation_USD'].sum()
        print(f"{'TOTAL':<43}  {df_top20['Market_Cap_USD'].sum()/1e9:>13.2f}B  {total_weight_pct:>9.2f}%    ${total_allocation:>12,.2f}")
    else:
        headers = f"{'Rank':<5}{'Ticker':<8}{'Company Name':<35}{'Price':<12}{'Market Cap ($B)':<20}{'Weight (%)':<12}"
        print(headers)
        print("-" * 105)
        for idx, row in df_top20.iterrows():
            mcap_b = row['Market_Cap_USD'] / 1e9
            weight_pct = row['Weight'] * 100
            print(f"{idx+1:<5}{row['Ticker']:<8}{row['Company'][:33]:<35}${row['Price']:>9.2f}  ${mcap_b:>15.2f}B  {weight_pct:>9.2f}%")
        print("-" * 105)
        total_weight_pct = df_top20['Weight'].sum() * 100
        print(f"{'TOTAL':<48}  {df_top20['Market_Cap_USD'].sum()/1e9:>15.2f}B  {total_weight_pct:>9.2f}%")
    print("=" * 105)
    if args.date:
        print("\nNote: Market Cap and Weight calculations are based on historical stock prices and cached shares outstanding.")
    else:
        print("\nNote: Market Cap and Weight calculations are based on current stock prices and cached shares outstanding.")
        print("Run with '--refresh-shares' to update the cached shares outstanding from yfinance.")

if __name__ == "__main__":
    main()
