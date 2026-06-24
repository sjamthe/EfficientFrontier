import os
import urllib.request
import pandas as pd
import numpy as np

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(script_dir, '..', 'SP500')
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

output_csv_path = os.path.join(output_dir, 'nasdaq_quarterly_history.csv')

# 2. Fetch Nasdaq-100 data from Wikipedia
nasdaq_url = "https://en.wikipedia.org/wiki/Nasdaq-100"
print(f"Fetching Nasdaq-100 constituents and changes from Wikipedia: {nasdaq_url}")
req = urllib.request.Request(nasdaq_url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as response:
        html = response.read()
except Exception as e:
    print(f"Error fetching Wikipedia page: {e}")
    raise

tables = pd.read_html(html)
# Table 5 is Current Constituents, Table 6 is Component Changes
df_current = tables[5]
df_changes = tables[6]

# Flatten MultiIndex columns if present in changes
if isinstance(df_changes.columns, pd.MultiIndex):
    df_changes.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in df_changes.columns]

# Rename date column to 'Date' dynamically
date_col = next((col for col in df_changes.columns if 'date' in col.lower()), None)
if date_col:
    df_changes['Date'] = pd.to_datetime(df_changes[date_col])
else:
    raise KeyError("Could not find a date-like column in the Wikipedia changes table.")

# Sort changes descending for backward roll
df_changes = df_changes.sort_values('Date', ascending=False)

# 3. Construct the timeline by rolling backward from current constituents
current_tickers = set(df_current['Ticker'].dropna().str.strip().tolist())
timeline = {}
now_date = pd.Timestamp.now().normalize()
timeline[now_date] = set(current_tickers)

# Group changes by Date
changes_by_date = {}
for idx, row in df_changes.iterrows():
    date = row['Date']
    if date not in changes_by_date:
        changes_by_date[date] = {'added': [], 'removed': []}
    if pd.notna(row['Added_Ticker']):
        changes_by_date[date]['added'].append(row['Added_Ticker'].strip())
    if pd.notna(row['Removed_Ticker']):
        changes_by_date[date]['removed'].append(row['Removed_Ticker'].strip())

# Perform backward roll
sorted_change_dates_desc = sorted(changes_by_date.keys(), reverse=True)
for date in sorted_change_dates_desc:
    chg = changes_by_date[date]
    # Roll backward: remove what was added, add what was removed
    for ticker in chg['added']:
        current_tickers.discard(ticker)
    for ticker in chg['removed']:
        current_tickers.add(ticker)
    timeline[date] = set(current_tickers)

# Sort timeline dates ascending
sorted_timeline_dates = sorted(timeline.keys())

# 4. Generate calendar quarters starting from the earliest change date (2007)
start_date = df_changes['Date'].min()
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
        # Skip quarters before the earliest date
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

# 5. Aggregate constituents, additions, and removals for each quarter
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
    
    # Get constituents at the end of the quarter
    timeline_dates_before_end = [d for d in sorted_timeline_dates if d <= q_end]
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

# 6. Plot the constituents count over time and save the chart
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
    ax.plot(df_plot['Quarter'], df_plot['Constituents_Count'], marker='o', color='#2ca02c', linewidth=1.8, markersize=2.5, label='Constituents Count')

    # Labels and title
    ax.set_title('NASDAQ-100 Constituents Count by Quarter (2007 - Present)', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Quarter', fontsize=11, fontweight='semibold', labelpad=10)
    ax.set_ylabel('Number of Tickers', fontsize=11, fontweight='semibold', labelpad=10)

    # Format ticks - show one tick per year (every 4th quarter)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(4))
    plt.xticks(rotation=90, fontsize=8)

    # Adjust y limits to focus on the range (e.g., 95 to 110)
    ax.set_ylim(95, 110)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(2))

    # Grid
    ax.grid(True, linestyle='--', alpha=0.6)

    # Highlight standard 100 level
    ax.axhline(y=100, color='#d62728', linestyle=':', linewidth=1.5, label='Standard (100)')

    ax.legend(loc='lower right', frameon=True, facecolor='white', edgecolor='none')

    plt.tight_layout()

    # Save to SP500 directory
    plot_img_path = os.path.join(output_dir, 'nasdaq_constituents_chart.png')
    plt.savefig(plot_img_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Chart updated and saved to: {plot_img_path}")

    # Copy to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(plot_img_path, os.path.join(artifact_dir, 'nasdaq_constituents_chart.png'))
except Exception as e:
    print(f"Could not generate plot: {e}")
