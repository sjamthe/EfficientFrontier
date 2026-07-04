#!/usr/bin/env python3
import os
import json
import subprocess
import argparse
from datetime import datetime
import pandas as pd

# List of Vanguard ETFs requested by the user
DEFAULT_ETFS = [
    "VAW",   # Vanguard Materials ETF
    "VB",    # Vanguard Small-Cap ETF
    "VBK",   # Vanguard Small-Cap Growth ETF
    "VBR",   # Vanguard Small-Cap Value ETF
    "VCR",   # Vanguard Consumer Discretionary ETF
    "VGT",   # Vanguard Information Technology ETF
    "VHT",   # Vanguard Health Care ETF
    "VIS",   # Vanguard Industrials ETF
    "VO",    # Vanguard Mid-Cap ETF
    "VONG",  # Vanguard Russell 1000 Growth ETF
    "VPU",   # Vanguard Utilities ETF
    "VUG",   # Vanguard Growth ETF
    "VXF"    # Vanguard Extended Market ETF
]

def fetch_etf_holdings(ticker):
    """
    Fetch the complete list of holdings for a given Vanguard ETF ticker
    using Vanguard's internal API via subprocess curl.
    """
    url = f"https://api.vanguard.com/rs/ire/01/ind/fund/{ticker.lower()}/portfolio-holding/stock.json"
    
    headers = [
        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Referer: https://investor.vanguard.com/",
        "-H", "Accept: application/json"
    ]
    
    cmd = ["curl", "-s"] + headers + [url]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if not result.stdout:
            print(f"Error: Empty response received for {ticker}.")
            return None
            
        data = json.loads(result.stdout)
        
        # Navigate the JSON structure to get the list of holdings
        # The structure is data -> fund -> entity
        fund = data.get("fund", {})
        holdings = fund.get("entity", [])
        
        if not holdings:
            print(f"Warning: No holdings found in the response for {ticker}.")
            print("Response structure keys:", list(data.keys()))
            if fund:
                print("fund keys:", list(fund.keys()))
            return None
            
        return holdings
        
    except subprocess.CalledProcessError as e:
        print(f"Error fetching {ticker} (curl failed): {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON for {ticker}: {e}")
        if 'result' in locals() and result.stdout:
            print("Response snippet:", result.stdout[:200])
        return None
    except Exception as e:
        print(f"Unexpected error fetching {ticker}: {e}")
        return None

def clean_str(val):
    if val is None:
        return ""
    return str(val).strip()

def clean_float(val):
    if val is None:
        return 0.0
    try:
        return float(val)
    except ValueError:
        return 0.0

def parse_and_save_holdings(ticker, holdings, output_dir):
    """
    Parse the raw holdings list into a Pandas DataFrame and save it as a CSV file.
    """
    records = []
    
    # Try to extract the data date from the first holding record
    as_of_date_str = datetime.today().strftime('%Y-%m-%d')
    if holdings:
        first_holding = holdings[0]
        raw_as_of_date = first_holding.get("asOfDate") # e.g. "2026-05-31T00:00:00-04:00"
        if raw_as_of_date:
            try:
                # Extract YYYY-MM-DD
                as_of_date_str = raw_as_of_date.split("T")[0]
            except Exception:
                pass

    for holding in holdings:
        records.append({
            "ticker": clean_str(holding.get("ticker")),
            "name": clean_str(holding.get("longName")),
            "weight": clean_float(holding.get("percentWeight")),
            "shares_held": clean_str(holding.get("sharesHeld")),
            "market_value": clean_float(holding.get("marketValue")),
            "isin": clean_str(holding.get("isin")),
            "cusip": clean_str(holding.get("cusip")),
            "sedol": clean_str(holding.get("sedol"))
        })
        
    df = pd.DataFrame(records)
    
    # Sort by market value/weight descending
    if "market_value" in df.columns:
        df = df.sort_values(by="market_value", ascending=False)
        
    # Generate CSV filename
    filename = f"{ticker.upper()}_holdings_{as_of_date_str}.csv"
    filepath = os.path.join(output_dir, filename)
    
    try:
        df.to_csv(filepath, index=False)
        print(f"Successfully saved {len(records)} holdings for {ticker} to {filepath}")
        return True
    except Exception as e:
        print(f"Error saving CSV for {ticker}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Download holdings for Vanguard ETFs quarterly.")
    parser.add_argument("-t", "--tickers", type=str, default=None,
                        help="Comma-separated list of ETF tickers to download (e.g. VGT,VOO). Defaults to standard 13 Vanguard ETFs.")
    parser.add_argument("-o", "--output-dir", type=str, default=None,
                        help="Output directory to save CSV files. Defaults to a 'holdings' folder in the script directory.")
    args = parser.parse_args()

    # Determine tickers to process
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        tickers = DEFAULT_ETFS

    # Determine output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.output_dir:
        output_dir = os.path.abspath(args.output_dir)
    else:
        output_dir = os.path.join(script_dir, "holdings")

    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")
    print(f"Processing {len(tickers)} ETFs: {', '.join(tickers)}")
    print("-" * 50)

    success_count = 0
    for ticker in tickers:
        print(f"Fetching holdings for {ticker}...")
        holdings = fetch_etf_holdings(ticker)
        if holdings:
            if parse_and_save_holdings(ticker, holdings, output_dir):
                success_count += 1
        print("-" * 50)

    print(f"\nExecution Complete! Successfully processed {success_count}/{len(tickers)} ETFs.")

if __name__ == "__main__":
    main()
