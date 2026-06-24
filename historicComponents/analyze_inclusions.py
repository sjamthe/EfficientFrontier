import os
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')
pkl_dir = os.path.join(data_dir, 'data_raw')
csv_path = os.path.join(data_dir, 'S&P 500 Historical Components & Changes(12-10-2024).csv')
output_detail_csv = os.path.join(data_dir, 'index_additions_analysis.csv')
output_plot = os.path.join(data_dir, 'index_inclusion_comparison.png')

# Load benchmark indices to calculate relative returns
print("Downloading benchmark indices (^GSPC and ^NDX)...")
end_date_str = pd.Timestamp.now().strftime('%Y-%m-%d')
df_sp500_bench = yf.download('^GSPC', start='1995-01-01', end=end_date_str, progress=False)
df_ndx_bench = yf.download('^NDX', start='2006-01-01', end=end_date_str, progress=False)

# Clean benchmark indices
def clean_bench(df):
    if 'Close' in df.columns:
        close = df['Close']
    else:
        close = df.iloc[:, 0]
    return close.squeeze().dropna()

sp_bench_close = clean_bench(df_sp500_bench)
ndx_bench_close = clean_bench(df_ndx_bench)

# 2. Extract S&P 500 addition events
print("\nExtracting S&P 500 additions...")
df_csv = pd.read_csv(csv_path)
df_csv['date'] = pd.to_datetime(df_csv['date'])
df_csv = df_csv.sort_values('date').reset_index(drop=True)

timeline = {}
for idx, row in df_csv.iterrows():
    date = row['date']
    tickers = set(row['tickers'].split(','))
    timeline[date] = tickers

# Fetch Wikipedia changes for post-CSV dates
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
req = urllib.request.Request(sp500_url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read()
    sp500_tables = pd.read_html(html)
    df_wiki = sp500_tables[1]
    if isinstance(df_wiki.columns, pd.MultiIndex):
        df_wiki.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df_wiki.columns]
    date_col = next((col for col in df_wiki.columns if 'date' in col.lower()), None)
    df_wiki['Date'] = pd.to_datetime(df_wiki[date_col])
    
    last_csv_date = df_csv['date'].max()
    current_tickers = set(df_csv.loc[df_csv['date'] == last_csv_date, 'tickers'].iloc[0].split(','))
    
    df_wiki_recent = df_wiki[df_wiki['Date'] > last_csv_date].sort_values('Date')
    recent_changes_by_date = {}
    for idx, row in df_wiki_recent.iterrows():
        date = row['Date']
        if date not in recent_changes_by_date:
            recent_changes_by_date[date] = {'added': [], 'removed': []}
        if pd.notna(row['Added_Ticker']):
            recent_changes_by_date[date]['added'].append(row['Added_Ticker'].strip())
        if pd.notna(row['Removed_Ticker']):
            recent_changes_by_date[date]['removed'].append(row['Removed_Ticker'].strip())
            
    sorted_recent_dates = sorted(recent_changes_by_date.keys())
    for date in sorted_recent_dates:
        chg = recent_changes_by_date[date]
        for ticker in chg['added']:
            current_tickers.add(ticker)
        for ticker in chg['removed']:
            current_tickers.discard(ticker)
        timeline[date] = set(current_tickers)
except Exception as e:
    print(f"Warning: Wikipedia fetch failed or changes column structure changed: {e}. Fallback to CSV changes only.")

# Identify exact addition events
sorted_dates = sorted(timeline.keys())
sp500_additions = []
for idx in range(1, len(sorted_dates)):
    prev_date = sorted_dates[idx-1]
    curr_date = sorted_dates[idx]
    prev_tkrs = timeline[prev_date]
    curr_tkrs = timeline[curr_date]
    added = curr_tkrs - prev_tkrs
    for t in added:
        sp500_additions.append((t.strip(), curr_date, 'SP500'))

print(f"Found {len(sp500_additions)} S&P 500 additions in history.")

# 3. Extract NASDAQ-100 addition events
print("\nExtracting NASDAQ-100 additions...")
nasdaq_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
req = urllib.request.Request(nasdaq_url, headers={'User-Agent': 'Mozilla/5.0'})
ndx_additions = []
try:
    with urllib.request.urlopen(req) as response:
        html_ndx = response.read()
    tables = pd.read_html(html_ndx)
    df_changes = tables[6]
    if isinstance(df_changes.columns, pd.MultiIndex):
        df_changes.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df_changes.columns]
    date_col = next((col for col in df_changes.columns if 'date' in col.lower()), None)
    df_changes['Date'] = pd.to_datetime(df_changes[date_col])
    
    # Filter to additions
    for idx, row in df_changes.iterrows():
        if pd.notna(row['Added_Ticker']):
            ndx_additions.append((row['Added_Ticker'].strip(), row['Date'], 'NASDAQ100'))
except Exception as e:
    print(f"Error fetching NASDAQ-100 changes: {e}")

print(f"Found {len(ndx_additions)} NASDAQ-100 additions in history.")

# Combine all additions
all_additions = sp500_additions + ndx_additions
print(f"\nTotal addition events to analyze: {len(all_additions)}")

# Helper to calculate returns over a specific window relative to benchmark
def calculate_window_returns(stock_prices, benchmark_prices, addition_date, window_days):
    pre_start = addition_date - pd.Timedelta(days=window_days)
    pre_end = addition_date - pd.Timedelta(days=1)
    post_start = addition_date + pd.Timedelta(days=1)
    post_end = addition_date + pd.Timedelta(days=window_days)
    
    # Pre-addition window
    pre_stock_subset = stock_prices.loc[pre_start:pre_end]
    min_days = max(15, int(window_days * 0.15)) # minimum trading days required
    
    if len(pre_stock_subset) < min_days:
        r_stock_pre = np.nan
        r_bench_pre = np.nan
    else:
        t_pre_start = pre_stock_subset.index[0]
        t_pre_end = pre_stock_subset.index[-1]
        r_stock_pre = (stock_prices.loc[t_pre_end] / stock_prices.loc[t_pre_start]) - 1.0
        r_bench_pre = (benchmark_prices.loc[t_pre_end] / benchmark_prices.loc[t_pre_start]) - 1.0
        
    # Post-addition window
    post_stock_subset = stock_prices.loc[post_start:post_end]
    if len(post_stock_subset) < min_days:
        r_stock_post = np.nan
        r_bench_post = np.nan
    else:
        t_post_start = post_stock_subset.index[0]
        t_post_end = post_stock_subset.index[-1]
        r_stock_post = (stock_prices.loc[t_post_end] / stock_prices.loc[t_post_start]) - 1.0
        r_bench_post = (benchmark_prices.loc[t_post_end] / benchmark_prices.loc[t_post_start]) - 1.0
        
    # Clean stock return anomalies
    if not pd.isna(r_stock_pre):
        if r_stock_pre > 10.0 or r_stock_pre < -0.95:  # filter extreme split/data issues
            r_stock_pre = np.nan
            r_bench_pre = np.nan
    if not pd.isna(r_stock_post):
        if r_stock_post > 10.0 or r_stock_post < -0.95:
            r_stock_post = np.nan
            r_bench_post = np.nan
            
    return r_stock_pre, r_bench_pre, r_stock_post, r_bench_post

def calculate_event_all_windows(ticker, addition_date, index_name, benchmark_prices):
    addition_date = pd.Timestamp(addition_date)
    
    # Load price file
    pkl_path = os.path.join(pkl_dir, f"{ticker}.pkl")
    if not os.path.exists(pkl_path):
        return None
        
    try:
        df_t = pd.read_pickle(pkl_path)
        col_to_use = 'Adj Close'
        if (col_to_use, ticker) in df_t.columns:
            stock_prices = df_t[(col_to_use, ticker)]
        elif col_to_use in df_t.columns:
            stock_prices = df_t[col_to_use]
        elif ('Close', ticker) in df_t.columns:
            stock_prices = df_t[('Close', ticker)]
        elif 'Close' in df_t.columns:
            stock_prices = df_t['Close']
        else:
            return None
            
        stock_prices = stock_prices.squeeze().dropna()
        if stock_prices.empty:
            return None
            
        # Clean price series
        stock_prices = stock_prices.mask(stock_prices > 10000, np.nan).ffill().bfill()
        
        event_dict = {
            'Index': index_name,
            'Ticker': ticker,
            'Addition_Date': addition_date.strftime('%Y-%m-%d')
        }
        
        # Calculate returns for 90, 180, 270, 365 days
        windows = [90, 180, 270, 365]
        valid_any = False
        
        for w in windows:
            r_stock_pre, r_bench_pre, r_stock_post, r_bench_post = calculate_window_returns(stock_prices, benchmark_prices, addition_date, w)
            
            event_dict[f'Stock_Pre_{w}'] = r_stock_pre
            event_dict[f'Index_Pre_{w}'] = r_bench_pre
            event_dict[f'Relative_Pre_{w}'] = r_stock_pre - r_bench_pre if not pd.isna(r_stock_pre) else np.nan
            
            event_dict[f'Stock_Post_{w}'] = r_stock_post
            event_dict[f'Index_Post_{w}'] = r_bench_post
            event_dict[f'Relative_Post_{w}'] = r_stock_post - r_bench_post if not pd.isna(r_stock_post) else np.nan
            
            if not pd.isna(r_stock_pre) or not pd.isna(r_stock_post):
                valid_any = True
                
        if not valid_any:
            return None
            
        return event_dict
    except Exception as e:
        return None

# Process all additions
processed_results = []
print("\nProcessing returns across 4 horizons (90d, 180d, 270d, 365d)...")
for idx, (ticker, addition_date, index_name) in enumerate(all_additions):
    bench = sp_bench_close if index_name == 'SP500' else ndx_bench_close
    res = calculate_event_all_windows(ticker, addition_date, index_name, bench)
    if res:
        processed_results.append(res)

df_analysis = pd.DataFrame(processed_results)
df_analysis.to_csv(output_detail_csv, index=False)
print(f"Successfully processed {len(df_analysis)} events and saved details to: {output_detail_csv}")

# 4. Generate Averages Table for all horizons
summary_stats = {}
indices = ['SP500', 'NASDAQ100']
windows = [90, 180, 270, 365]

print("\n=========================================================================")
print("Index Inclusion Effect Summary Across 4 Horizons (Decay Analysis)")
print("=========================================================================")

for idx_name in indices:
    df_sub = df_analysis[df_analysis['Index'] == idx_name]
    if df_sub.empty:
        continue
        
    summary_stats[idx_name] = {}
    print(f"\n{idx_name} Inclusions Analysis:")
    
    # We will compute averages and medians for each window size
    for w in windows:
        # Filter to events that have valid returns for this window
        valid_pre = df_sub[df_sub[f'Relative_Pre_{w}'].notna()]
        valid_post = df_sub[df_sub[f'Relative_Post_{w}'].notna()]
        
        avg_rel_pre = valid_pre[f'Relative_Pre_{w}'].mean() * 100
        med_rel_pre = valid_pre[f'Relative_Pre_{w}'].median() * 100
        win_rate_pre = (valid_pre[f'Relative_Pre_{w}'] > 0).mean() * 100
        
        avg_rel_post = valid_post[f'Relative_Post_{w}'].mean() * 100
        med_rel_post = valid_post[f'Relative_Post_{w}'].median() * 100
        win_rate_post = (valid_post[f'Relative_Post_{w}'] > 0).mean() * 100
        
        print(f"  Horizon {w:3d} Days (Pre: N={len(valid_pre)}, Post: N={len(valid_post)}):")
        print(f"    Pre-Addition  Relative Return: Average = {avg_rel_pre:6.2f}%, Median = {med_rel_pre:6.2f}%, Win Rate = {win_rate_pre:5.1f}%")
        print(f"    Post-Addition Relative Return: Average = {avg_rel_post:6.2f}%, Median = {med_rel_post:6.2f}%, Win Rate = {win_rate_post:5.1f}%")
        
        summary_stats[idx_name][w] = {
            'avg_rel_pre': avg_rel_pre,
            'med_rel_pre': med_rel_pre,
            'win_rate_pre': win_rate_pre,
            'avg_rel_post': avg_rel_post,
            'med_rel_post': med_rel_post,
            'win_rate_post': win_rate_post,
            'n_pre': len(valid_pre),
            'n_post': len(valid_post)
        }

# 5. Plotting decay profile
try:
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
    
    # Horizontally, X-axis represents time relative to inclusion (Day 0)
    # Windows: -365d, -270d, -180d, -90d, +90d, +180d, +270d, +365d
    x_labels = ['-365 Days', '-270 Days', '-180 Days', '-90 Days', '+90 Days', '+180 Days', '+270 Days', '+365 Days']
    x_indices = np.arange(len(x_labels))
    
    colors = {'SP500': '#1f77b4', 'NASDAQ100': '#ff7f0e'}
    markers = {'SP500': 'o', 'NASDAQ100': 's'}
    
    for idx_name in indices:
        if idx_name not in summary_stats:
            continue
        
        # Build y values (pre-addition goes from -365 to -90, post-addition goes from 90 to 365)
        stats = summary_stats[idx_name]
        
        y_values = [
            stats[365]['avg_rel_pre'],
            stats[270]['avg_rel_pre'],
            stats[180]['avg_rel_pre'],
            stats[90]['avg_rel_pre'],
            stats[90]['avg_rel_post'],
            stats[180]['avg_rel_post'],
            stats[270]['avg_rel_post'],
            stats[365]['avg_rel_post']
        ]
        
        ax.plot(x_indices, y_values, marker=markers[idx_name], color=colors[idx_name], linewidth=2.5, markersize=6,
                label=f"{idx_name} Average Relative Return")
        
        # Add labels to points
        for x, y in zip(x_indices, y_values):
            ax.annotate(f"{y:.1f}%", xy=(x, y), xytext=(0, 8 if y >= 0 else -15),
                        textcoords="offset points", ha='center', fontsize=9, fontweight='semibold')
            
    # Vertical line showing Addition Event (Day 0)
    # The line is between index 3 (-90d) and index 4 (+90d)
    ax.axvline(x=3.5, color='#d62728', linestyle='--', linewidth=2.0, label='Index Addition Event (Day 0)')
    
    # Format axes
    ax.set_title("Index Inclusion Performance Horizon & Decay Curve", fontsize=14, fontweight='bold', pad=15)
    ax.set_xticks(x_indices)
    ax.set_xticklabels(x_labels, fontsize=10, fontweight='semibold')
    ax.set_ylabel('Average Relative Return vs Benchmark (%)', fontsize=11, fontweight='semibold', labelpad=10)
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Add a horizontal line at 0% relative return
    ax.axhline(y=0.0, color='black', linestyle='-', linewidth=1.0, alpha=0.5)
    
    ax.legend(loc='upper right', frameon=True, facecolor='white', edgecolor='none')
    
    plt.tight_layout()
    plt.savefig(output_plot, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\nDecay plot saved to: {output_plot}")
    
    # Copy to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(output_plot, os.path.join(artifact_dir, 'index_inclusion_comparison.png'))
except Exception as e:
    print(f"Error generating plot: {e}")
