import os
import urllib.request
import pandas as pd
import numpy as np

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, '..', 'SP500', 'S&P 500 Historical Components & Changes(12-10-2024).csv')

if not os.path.exists(csv_path):
    # Fallback to working directory relative path
    csv_path = 'SP500/S&P 500 Historical Components & Changes(12-10-2024).csv'

if not os.path.exists(csv_path):
    raise FileNotFoundError(f"Could not find S&P 500 historical CSV at {csv_path}. Please check your directories.")

output_dir = os.path.dirname(csv_path)
output_csv_path = os.path.join(output_dir, 'sp500_quarterly_history.csv')

print(f"Loading historical CSV from: {csv_path}")
df_csv = pd.read_csv(csv_path)
df_csv['date'] = pd.to_datetime(df_csv['date'])
df_csv = df_csv.sort_values('date').reset_index(drop=True)

# 2. Fetch recent changes from Wikipedia
sp500_url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
print(f"Fetching recent S&P 500 changes from Wikipedia: {sp500_url}")
req = urllib.request.Request(sp500_url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read()
except Exception as e:
    print(f"Error fetching Wikipedia page: {e}")
    raise

sp500_tables = pd.read_html(html)
df_wiki = sp500_tables[1]  # Selected changes table

# Flatten MultiIndex columns if present
if isinstance(df_wiki.columns, pd.MultiIndex):
    df_wiki.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df_wiki.columns]

# Rename date column to 'Date' dynamically
date_col = next((col for col in df_wiki.columns if 'date' in col.lower()), None)
if date_col:
    df_wiki['Date'] = pd.to_datetime(df_wiki[date_col])
else:
    raise KeyError("Could not find a date-like column in the Wikipedia changes table.")

# 3. Construct the unified constituents timeline
timeline = {}
for idx, row in df_csv.iterrows():
    date = row['date']
    tickers = set(row['tickers'].split(','))
    timeline[date] = tickers

# Roll forward from the last CSV date using Wikipedia changes
last_csv_date = df_csv['date'].max()
current_tickers = set(df_csv.loc[df_csv['date'] == last_csv_date, 'tickers'].iloc[0].split(','))

# Group recent wiki changes by date
df_wiki_recent = df_wiki[df_wiki['Date'] > last_csv_date].sort_values('Date')
recent_changes_by_date = {}
for idx, row in df_wiki_recent.iterrows():
    date = row['Date']
    if date not in recent_changes_by_date:
        recent_changes_by_date[date] = {'added': [], 'removed': []}
    if pd.notna(row['Added_Ticker']):
        recent_changes_by_date[date]['added'].append(row['Added_Ticker'])
    if pd.notna(row['Removed_Ticker']):
        recent_changes_by_date[date]['removed'].append(row['Removed_Ticker'])

# Apply recent changes chronologically
sorted_recent_dates = sorted(recent_changes_by_date.keys())
for date in sorted_recent_dates:
    changes = recent_changes_by_date[date]
    for ticker in changes['added']:
        current_tickers.add(ticker)
    for ticker in changes['removed']:
        current_tickers.discard(ticker)
    timeline[date] = set(current_tickers)

# 4. Track all additions and removals on each timeline date
sorted_dates = sorted(timeline.keys())
changes_by_date = {}

# Compute changes for CSV dates
for idx in range(1, len(df_csv)):
    prev_date = df_csv.loc[idx-1, 'date']
    curr_date = df_csv.loc[idx, 'date']
    prev_tkrs = timeline[prev_date]
    curr_tkrs = timeline[curr_date]
    added = curr_tkrs - prev_tkrs
    removed = prev_tkrs - curr_tkrs
    if added or removed:
        changes_by_date[curr_date] = {'added': sorted(list(added)), 'removed': sorted(list(removed))}

# Compute changes for post-CSV dates
for date in sorted_recent_dates:
    changes = recent_changes_by_date[date]
    if changes['added'] or changes['removed']:
        changes_by_date[date] = {'added': sorted(changes['added']), 'removed': sorted(changes['removed'])}

# 5. Generate calendar quarters starting from the earliest date in the CSV (1996)
start_date = df_csv['date'].min()
end_date = pd.Timestamp.now()


current_year = end_date.year
current_month = end_date.month
current_q = (current_month - 1) // 3 + 1

start_year = start_date.year
start_month = start_date.month
start_q = (start_month - 1) // 3 + 1

quarters = []
for y in range(start_year, current_year + 1):
    for q in [1, 2, 3, 4]:
        # Skip quarters before 15 years ago
        if y == start_year and q < start_q:
            continue
        # Skip quarters in the future
        if y == current_year and q > current_q:
            continue
            
        # Quarter dates
        if q == 1:
            q_start = pd.Timestamp(f"{y}-01-01")
            q_end = pd.Timestamp(f"{y}-03-31")
        elif q == 2:
            q_start = pd.Timestamp(f"{y}-04-01")
            q_end = pd.Timestamp(f"{y}-06-30")
        elif q == 3:
            q_start = pd.Timestamp(f"{y}-07-01")
            q_end = pd.Timestamp(f"{y}-09-30")
        else:
            q_start = pd.Timestamp(f"{y}-10-01")
            q_end = pd.Timestamp(f"{y}-12-31")
            
        # Cap end date at current date if it's the current in-progress quarter
        if q_end > end_date:
            q_end = end_date
            
        quarters.append((f"{y}Q{q}", q_start, q_end))

# 6. Aggregate constituents, additions, and removals for each quarter
quarter_results = []
for q_name, q_start, q_end in quarters:
    # Find all changes during this quarter
    q_added = []
    q_removed = []
    for c_date, chg in changes_by_date.items():
        if q_start <= c_date <= q_end:
            q_added.extend(chg['added'])
            q_removed.extend(chg['removed'])
            
    # Deduplicate and sort
    q_added = sorted(list(set(q_added)))
    q_removed = sorted(list(set(q_removed)))
    
    # Get constituents at the end of the quarter (closest preceding timeline date)
    timeline_dates_before_end = [d for d in sorted_dates if d <= q_end]
    if timeline_dates_before_end:
        closest_date = max(timeline_dates_before_end)
        constituents = sorted(list(timeline[closest_date]))
    else:
        constituents = []
        
    quarter_results.append({
        'Quarter': q_name,
        'Start_Date': q_start.strftime('%Y-%m-%d'),
        'End_Date': q_end.strftime('%Y-%m-%d'),
        'Additions_Count': len(q_added),
        'Removals_Count': len(q_removed),
        'Constituents_Count': len(constituents),
        'Additions': ','.join(q_added),
        'Removals': ','.join(q_removed),
        'Constituents': ','.join(constituents)
    })

df_quarters = pd.DataFrame(quarter_results)
df_quarters.to_csv(output_csv_path, index=False)
print(f"\nSuccessfully generated quarterly history and saved to: {output_csv_path}")

# Display summary table for the last 8 quarters
print("\nSummary of the last 8 quarters:")
cols_to_print = ['Quarter', 'Start_Date', 'End_Date', 'Constituents_Count', 'Additions_Count', 'Removals_Count']
print(df_quarters[cols_to_print].tail(8).to_string(index=False))

# 7. Plot the constituents count over time and save the chart
try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    # Set style
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)

    # Sort chronologically by Quarter
    df_plot = df_quarters.copy()
    df_plot['Year'] = df_plot['Quarter'].str[:4].astype(int)
    df_plot['Q'] = df_plot['Quarter'].str[5].astype(int)
    df_plot = df_plot.sort_values(['Year', 'Q']).reset_index(drop=True)

    # Plot constituents count
    ax.plot(df_plot['Quarter'], df_plot['Constituents_Count'], marker='o', color='#1f77b4', linewidth=1.8, markersize=2.5, label='Constituents Count')

    # Labels and title
    ax.set_title('S&P 500 Constituents Count by Quarter (1996 - Present)', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Quarter', fontsize=11, fontweight='semibold', labelpad=10)
    ax.set_ylabel('Number of Companies', fontsize=11, fontweight='semibold', labelpad=10)

    # Format ticks - show one tick per year (every 4th quarter)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(4))
    plt.xticks(rotation=90, fontsize=8)

    # Adjust y limits to focus on the range (e.g., 480 to 510)
    ax.set_ylim(480, 510)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(5))

    # Grid
    ax.grid(True, linestyle='--', alpha=0.6)

    # Highlight standard 500 level
    ax.axhline(y=500, color='#d62728', linestyle=':', linewidth=1.5, label='Standard (500)')

    ax.legend(loc='lower right', frameon=True, facecolor='white', edgecolor='none')

    plt.tight_layout()

    # Save to SP500 directory
    plot_img_path = os.path.join(output_dir, 'sp500_constituents_chart.png')
    plt.savefig(plot_img_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Chart updated and saved to: {plot_img_path}")

    # Copy to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(plot_img_path, os.path.join(artifact_dir, 'sp500_constituents_chart.png'))
except Exception as e:
    print(f"Could not generate plot: {e}")