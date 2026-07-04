import os
import pandas as pd
import glob

DEFAULT_ETFS = ["VAW", "VB", "VBK", "VBR", "VCR", "VGT", "VHT", "VIS", "VO", "VONG", "VPU", "VUG", "VXF"]
DEFAULT_ETF_AMOUNTS = [
    425331,  # VAW
    283342,  # VB
    712273,  # VBK
    129509,  # VBR
    845418,  # VCR
    894772,  # VGT
    1013540, # VHT
    170146,  # VIS
    1206701, # VO
    72360,   # VONG
    1317410, # VPU
    243335,  # VUG
    1290522  # VXF
]

etf_to_amount = dict(zip(DEFAULT_ETFS, DEFAULT_ETF_AMOUNTS))
total_portfolio_value = sum(DEFAULT_ETF_AMOUNTS)

holdings_dir = "/Users/sjamthe/Documents/GithubRepos/EfficientFrontier/holdings"

def calculate_combined():
    combined_data = []
    
    for ticker, amount in etf_to_amount.items():
        # Find the latest holdings CSV file for this ETF
        pattern = os.path.join(holdings_dir, f"{ticker}_holdings_*.csv")
        files = glob.glob(pattern)
        if not files:
            print(f"Warning: No files found for {ticker}")
            continue
            
        # Get the latest file by modification time or alphabetical (since dated YYYY-MM-DD)
        latest_file = sorted(files)[-1]
        
        df = pd.read_csv(latest_file)
        # Handle cases where ticker is missing or null (some cash items have no ticker)
        df['ticker'] = df['ticker'].fillna('CASH_OR_OTHER')
        df['name'] = df['name'].fillna('Cash / Other / Unclassified')
        
        # Calculate dollar value of each holding
        # weight is in percentage (e.g. 16.78), so divide by 100
        df['holding_value'] = (df['weight'] / 100.0) * amount
        
        for _, row in df.iterrows():
            combined_data.append({
                'ticker': row['ticker'],
                'name': row['name'],
                'value': row['holding_value']
            })
            
    # Create combined DataFrame
    df_all = pd.DataFrame(combined_data)
    
    # Group by ticker and name and sum
    # To keep names consistent, we group by ticker and select the first/most common name
    grouped = df_all.groupby('ticker').agg({
        'name': 'first',
        'value': 'sum'
    }).reset_index()
    
    # Calculate percentage weight in total portfolio
    grouped['portfolio_weight'] = (grouped['value'] / total_portfolio_value) * 100.0
    
    # Sort descending by value
    grouped = grouped.sort_values(by='value', ascending=False)
    
    print(f"Total Portfolio Value: ${total_portfolio_value:,.2f}\n")
    print(f"{'No.':<4} {'Ticker':<8} {'Company Name':<35} {'Value ($)':<15} {'Weight (%)':<10}")
    print("-" * 76)
    
    top_50 = grouped.head(50)
    for idx, (_, row) in enumerate(top_50.iterrows(), 1):
        ticker_str = row['ticker']
        if ticker_str == 'CASH_OR_OTHER':
            ticker_str = '-'
        print(f"{idx:<4} {ticker_str:<8} {row['name'][:33]:<35} ${row['value']:<14,.2f} {row['portfolio_weight']:<9.4f}%")
        
    # Save the full combined list to a CSV in holdings/ directory
    output_path = os.path.join(holdings_dir, "combined_portfolio_holdings.csv")
    grouped.to_csv(output_path, index=False)
    print(f"\nFull list of {len(grouped)} holdings saved to: {output_path}")

if __name__ == "__main__":
    calculate_combined()
