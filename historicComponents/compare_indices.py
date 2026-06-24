import os
import pandas as pd

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')

sp500_csv = os.path.join(data_dir, 'sp500_quarterly_history.csv')
nasdaq_csv = os.path.join(data_dir, 'nasdaq_quarterly_history.csv')
output_csv = os.path.join(data_dir, 'nasdaq_not_sp500_quarterly.csv')

if not os.path.exists(sp500_csv) or not os.path.exists(nasdaq_csv):
    raise FileNotFoundError("Missing S&P 500 or NASDAQ-100 quarterly history CSV files. Please run sp500_components.py and nasdaq_components.py first.")

# Load datasets
df_sp500 = pd.read_csv(sp500_csv)
df_ndx = pd.read_csv(nasdaq_csv)

# 2. Align datasets by sorting chronologically
df_sp500['Year'] = df_sp500['Quarter'].str[:4].astype(int)
df_sp500['Q'] = df_sp500['Quarter'].str[5].astype(int)
df_sp500 = df_sp500.sort_values(['Year', 'Q']).reset_index(drop=True)

df_ndx['Year'] = df_ndx['Quarter'].str[:4].astype(int)
df_ndx['Q'] = df_ndx['Quarter'].str[5].astype(int)
df_ndx = df_ndx.sort_values(['Year', 'Q']).reset_index(drop=True)

# Find the intersection of quarters starting from NASDAQ-100's start date
available_ndx_quarters = set(df_ndx['Quarter'])
df_sp500_filtered = df_sp500[df_sp500['Quarter'].isin(available_ndx_quarters)].copy()
df_ndx_filtered = df_ndx[df_ndx['Quarter'].isin(df_sp500_filtered['Quarter'])].copy()

# Ensure chronological order and index match
df_sp500_filtered = df_sp500_filtered.sort_values(['Year', 'Q']).reset_index(drop=True)
df_ndx_filtered = df_ndx_filtered.sort_values(['Year', 'Q']).reset_index(drop=True)

# 3. Perform comparison (NDX \ S&P500)
results = []
for idx in range(len(df_ndx_filtered)):
    q_name = df_ndx_filtered.loc[idx, 'Quarter']
    q_start = df_ndx_filtered.loc[idx, 'Start_Date']
    q_end = df_ndx_filtered.loc[idx, 'End_Date']
    
    ndx_tkrs = set(str(df_ndx_filtered.loc[idx, 'Constituents']).split(','))
    sp_tkrs = set(str(df_sp500_filtered.loc[idx, 'Constituents']).split(','))
    
    # Clean tickers
    ndx_tkrs = {t.strip() for t in ndx_tkrs if t.strip()}
    sp_tkrs = {t.strip() for t in sp_tkrs if t.strip()}
    
    # Set difference: Tickers in NDX but not in S&P500
    unique_ndx = ndx_tkrs - sp_tkrs
    unique_ndx_sorted = sorted(list(unique_ndx))
    
    results.append({
        'Quarter': q_name,
        'Start_Date': q_start,
        'End_Date': q_end,
        'Nasdaq_Count': len(ndx_tkrs),
        'SP500_Count': len(sp_tkrs),
        'Unique_Nasdaq_Count': len(unique_ndx),
        'Unique_Nasdaq_Tickers': ','.join(unique_ndx_sorted)
    })

df_results = pd.DataFrame(results)
df_results.to_csv(output_csv, index=False)
print(f"\nSuccessfully generated index comparison and saved to: {output_csv}")

# Display summary of the last 8 quarters
print("\nSummary of the last 8 quarters:")
cols_to_print = ['Quarter', 'Start_Date', 'End_Date', 'Nasdaq_Count', 'SP500_Count', 'Unique_Nasdaq_Count']
print(df_results[cols_to_print].tail(8).to_string(index=False))

# 4. Plot the unique counts over time
try:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    # Set style
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)

    # Plot constituents count
    ax.plot(df_results['Quarter'], df_results['Unique_Nasdaq_Count'], marker='o', color='#ff7f0e', linewidth=2, markersize=3, label='NASDAQ-100 Tickers Not in S&P 500')

    # Labels and title
    ax.set_title('Number of NASDAQ-100 Companies Not Included in S&P 500 by Quarter', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Quarter', fontsize=11, fontweight='semibold', labelpad=10)
    ax.set_ylabel('Number of Tickers', fontsize=11, fontweight='semibold', labelpad=10)

    # Format ticks - show one tick per year (every 4th quarter)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(4))
    plt.xticks(rotation=90, fontsize=8)

    # Grid
    ax.grid(True, linestyle='--', alpha=0.6)

    # Set y limits based on data range
    y_min = df_results['Unique_Nasdaq_Count'].min() - 3
    y_max = df_results['Unique_Nasdaq_Count'].max() + 3
    ax.set_ylim(max(0, y_min), y_max)
    ax.yaxis.set_major_locator(ticker.MultipleLocator(2))

    ax.legend(loc='lower right', frameon=True, facecolor='white', edgecolor='none')

    plt.tight_layout()

    # Save to SP500 directory
    plot_img_path = os.path.join(data_dir, 'nasdaq_not_sp500_chart.png')
    plt.savefig(plot_img_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Chart updated and saved to: {plot_img_path}")

    # Copy to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(plot_img_path, os.path.join(artifact_dir, 'nasdaq_not_sp500_chart.png'))
except Exception as e:
    print(f"Could not generate plot: {e}")
