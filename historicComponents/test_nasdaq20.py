import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')
pkl_dir = os.path.join(data_dir, 'data_raw')
nasdaq_csv = os.path.join(data_dir, 'nasdaq_quarterly_history.csv')
metadata_csv = os.path.join(data_dir, 'ticker_metadata.csv')
output_ndx20_csv = os.path.join(data_dir, 'nasdaq_20_quarterly.csv')

# Load files
df_ndx = pd.read_csv(nasdaq_csv)
df_meta = pd.read_csv(metadata_csv)
metadata = {}
for idx, row in df_meta.iterrows():
    metadata[row['Ticker']] = row['Shares_Outstanding']

# Tickers to exclude from portfolio
exclude_tickers = ['META', 'PLTR']

# Determine constituents for each quarter (top 20 by market cap at start of quarter)
print("Extracting top 20 NASDAQ-100 constituents for each quarter...")
ndx20_results = []
prev_candidates = []

for idx, row in df_ndx.iterrows():
    q_name = row['Quarter']
    q_start = pd.Timestamp(row['Start_Date'])
    q_end = pd.Timestamp(row['End_Date'])
    
    q_constituents = [t.strip() for t in str(row['Constituents']).split(',') if t.strip()]
    
    # Calculate market cap for each constituent at start of quarter
    mcap_list = []
    for ticker in q_constituents:
        if ticker in exclude_tickers:
            continue
        pkl_path = os.path.join(pkl_dir, f"{ticker}.pkl")
        if os.path.exists(pkl_path):
            try:
                df_t = pd.read_pickle(pkl_path)
                col_to_use = 'Close'
                if (col_to_use, ticker) in df_t.columns:
                    prices = df_t[(col_to_use, ticker)]
                elif col_to_use in df_t.columns:
                    prices = df_t[col_to_use]
                else:
                    continue
                    
                # Find price on or closest after start date (must be within 30 days of the quarter start)
                valid_prices = prices.loc[q_start : q_start + pd.Timedelta(days=30)]
                if not valid_prices.empty:
                    start_price = valid_prices.iloc[0]
                    shares = metadata.get(ticker, 1.0)
                    if pd.isna(shares) or shares <= 0:
                        shares = 1.0
                    mcap = start_price * shares
                    mcap_list.append((ticker, mcap))
            except Exception:
                pass
                
    # Sort by market cap descending and calculate ranks
    mcap_list = sorted(mcap_list, key=lambda x: x[1], reverse=True)
    ticker_ranks = {x[0]: r + 1 for r, x in enumerate(mcap_list)}
    ticker_mcaps = {x[0]: x[1] for x in mcap_list}
    
    # Determine the top 20 candidates using hysteresis (Enter <= 20, Stay <= 30)
    # Rebalance constituents only in Q1 and Q3
    is_rebalance_q = q_name.endswith('Q1') or q_name.endswith('Q3')
    
    if not prev_candidates:
        # First quarter: select top 20 by market cap
        top20 = [x[0] for x in mcap_list[:20]]
    elif not is_rebalance_q:
        # Keep previous candidates in Q2 and Q4 (no constituent swaps)
        top20 = prev_candidates
    else:
        # Subsequent rebalance quarters: retain existing constituents if they are Rank 30 or better
        retained = []
        for ticker in prev_candidates:
            if ticker in ticker_ranks and ticker_ranks[ticker] <= 30:
                retained.append(ticker)
        
        # Fill remaining slots with new candidates only if they rank in the Top 20
        if len(retained) < 20:
            slots_needed = 20 - len(retained)
            new_candidates = []
            for ticker, mcap in mcap_list:
                if ticker not in retained:
                    # New security must rank in the Top 20 to be included
                    if ticker_ranks[ticker] <= 20:
                        new_candidates.append(ticker)
            retained.extend(new_candidates[:slots_needed])
        elif len(retained) > 20:
            # Keep top 20 of retained by current market cap
            retained = sorted(retained, key=lambda x: ticker_mcaps[x], reverse=True)[:20]
            
        top20 = retained
        
    prev_candidates = list(top20)
    
    ndx20_results.append({
        'Quarter': q_name,
        'Start_Date': row['Start_Date'],
        'End_Date': row['End_Date'],
        'Candidates': ','.join(top20) # use Candidates column name for returns script
    })

df_ndx20 = pd.DataFrame(ndx20_results)
df_ndx20.to_csv(output_ndx20_csv, index=False)
print(f"Saved NASDAQ-20 quarterly constituents to: {output_ndx20_csv}")

# Import calculate_portfolio_returns from calculate_returns
import sys
sys.path.append(script_dir)
from calculate_returns import calculate_portfolio_returns

# Run return backtest for NASDAQ-20
print("\nCalculating returns for NASDAQ-20 Total Return portfolio...")
calculate_portfolio_returns(
    constituent_csv_name='nasdaq_20_quarterly.csv',
    weight_scheme='cap',
    return_type='total',
    benchmark_ticker='^NDXT',
    portfolio_name='nasdaq_20_total_return',
    initial_value=6000000.0
)

# Plot comparison
nasdaq100_path = os.path.join(data_dir, 'nasdaq100_total_return_returns.csv')
ndx20_path = os.path.join(data_dir, 'nasdaq_20_total_return_returns.csv')
output_plot = os.path.join(data_dir, 'nasdaq20_vs_nasdaq100_total_return.png')

df_ndx_tr = pd.read_csv(nasdaq100_path)
df_ndx20_tr = pd.read_csv(ndx20_path)

df_ndx_tr['Date'] = pd.to_datetime(df_ndx_tr['Date'])
df_ndx20_tr['Date'] = pd.to_datetime(df_ndx20_tr['Date'])

df_ndx_tr = df_ndx_tr.set_index('Date')
df_ndx20_tr = df_ndx20_tr.set_index('Date')

df_compare = pd.DataFrame({
    'Nasdaq20_Portfolio': df_ndx20_tr['Cumulative_Return'],
    'Nasdaq100_Portfolio': df_ndx_tr['Cumulative_Return'],
    'NDXT_Benchmark': df_ndx20_tr['Benchmark_Return']
}, index=df_ndx20_tr.index).dropna()

final_n20 = df_compare['Nasdaq20_Portfolio'].iloc[-1] * 100
final_ndx = df_compare['Nasdaq100_Portfolio'].iloc[-1] * 100
final_bench = df_compare['NDXT_Benchmark'].iloc[-1] * 100

print("\n==================================================")
print("NASDAQ-20 vs NASDAQ-100 Total Return Results")
print("==================================================")
print(f"NASDAQ-20 Portfolio: {final_n20:.2f}% (x{(final_n20/100 + 1):.2f})")
print(f"NASDAQ-100 Portfolio: {final_ndx:.2f}% (x{(final_ndx/100 + 1):.2f})")
print(f"Official ^NDXT Index: {final_bench:.2f}% (x{(final_bench/100 + 1):.2f})")

corr = df_ndx20_tr['Daily_Return'].corr(df_ndx_tr['Daily_Return'])
print(f"Daily return correlation (NASDAQ-20 vs NASDAQ-100): {corr * 100:.2f}%")

# Generate plot
try:
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
    ax.plot(df_compare.index, df_compare['Nasdaq20_Portfolio'] * 100, color='#2ca02c', linewidth=2.0, label=f"NASDAQ-20 (Top 20 Market Cap) (Final: {final_n20:.1f}%)")
    ax.plot(df_compare.index, df_compare['Nasdaq100_Portfolio'] * 100, color='#ff7f0e', linewidth=1.5, label=f"NASDAQ-100 Reconstructed (Final: {final_ndx:.1f}%)")
    ax.plot(df_compare.index, df_compare['NDXT_Benchmark'] * 100, color='#7f7f7f', linewidth=1.5, linestyle='--', label=f"Official NASDAQ-100 TR (^NDXT) (Final: {final_bench:.1f}%)")
    
    ax.set_title('Total Return Comparison: NASDAQ-20 vs NASDAQ-100', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Date', fontsize=11, fontweight='semibold')
    ax.set_ylabel('Cumulative Return (%)', fontsize=11, fontweight='semibold')
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='none')
    
    plt.tight_layout()
    plt.savefig(output_plot, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Plot saved to: {output_plot}")
    
    # Copy to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/278cb75b-212b-4bbd-be70-50694e134c47'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(output_plot, os.path.join(artifact_dir, 'nasdaq20_vs_nasdaq100_total_return.png'))
except Exception as e:
    print(f"Error plotting: {e}")
