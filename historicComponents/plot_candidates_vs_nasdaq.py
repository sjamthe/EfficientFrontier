import os
import pandas as pd
import matplotlib.pyplot as plt

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')

nasdaq100_path = os.path.join(data_dir, 'nasdaq100_total_return_returns.csv')
candidates_path = os.path.join(data_dir, 'nasdaq_candidate_queue_total_return_returns.csv')
output_plot = os.path.join(data_dir, 'candidates_vs_nasdaq100_total_return.png')

if not os.path.exists(nasdaq100_path) or not os.path.exists(candidates_path):
    raise FileNotFoundError("Missing total return CSV files.")

df_ndx = pd.read_csv(nasdaq100_path)
df_cand = pd.read_csv(candidates_path)

df_ndx['Date'] = pd.to_datetime(df_ndx['Date'])
df_cand['Date'] = pd.to_datetime(df_cand['Date'])

df_ndx = df_ndx.set_index('Date')
df_cand = df_cand.set_index('Date')

# Join datasets
df_compare = pd.DataFrame({
    'Candidates_Portfolio': df_cand['Cumulative_Return'],
    'Nasdaq100_Portfolio': df_ndx['Cumulative_Return'],
    'NDXT_Benchmark': df_cand['Benchmark_Return'] # ^NDXT
}, index=df_cand.index).dropna()

print("\n==================================================")
print("Candidates Queue vs NASDAQ-100 Total Return Comparison")
print("==================================================")
print("Data Range:", df_compare.index.min().strftime('%Y-%m-%d'), "to", df_compare.index.max().strftime('%Y-%m-%d'))

# Final cumulative returns
final_cand = df_compare['Candidates_Portfolio'].iloc[-1] * 100
final_ndx = df_compare['Nasdaq100_Portfolio'].iloc[-1] * 100
final_bench = df_compare['NDXT_Benchmark'].iloc[-1] * 100

print(f"\nFinal Cumulative Returns:")
print(f"  NASDAQ-100 Candidates Portfolio (Cap-Weighted): {final_cand:.2f}% (x{(final_cand/100 + 1):.2f})")
print(f"  NASDAQ-100 Reconstructed Portfolio: {final_ndx:.2f}% (x{(final_ndx/100 + 1):.2f})")
print(f"  ^NDXT Benchmark: {final_bench:.2f}% (x{(final_bench/100 + 1):.2f})")

# Daily return correlations
df_daily_compare = pd.DataFrame({
    'Candidates_Daily': df_cand['Daily_Return'],
    'Nasdaq100_Daily': df_ndx['Daily_Return']
}, index=df_cand.index).dropna()

corr = df_daily_compare['Candidates_Daily'].corr(df_daily_compare['Nasdaq100_Daily'])
print(f"\nDaily Return Correlation (Candidates vs NASDAQ-100): {corr * 100:.2f}%")

# Save a comparison summary CSV
df_compare.to_csv(os.path.join(data_dir, 'candidates_vs_nasdaq100_total_return.csv'))
print(f"Saved comparison summary CSV to: {os.path.join(data_dir, 'candidates_vs_nasdaq100_total_return.csv')}")

# Plotting
try:
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)

    # Plot lines
    ax.plot(df_compare.index, df_compare['Candidates_Portfolio'] * 100, color='#8a2be2', linewidth=2.0, label=f"NASDAQ-100 Candidates Portfolio (Final: {final_cand:.1f}%)")
    ax.plot(df_compare.index, df_compare['Nasdaq100_Portfolio'] * 100, color='#ff7f0e', linewidth=1.5, linestyle='-', label=f"NASDAQ-100 Reconstructed Total Return (Final: {final_ndx:.1f}%)")
    ax.plot(df_compare.index, df_compare['NDXT_Benchmark'] * 100, color='#7f7f7f', linewidth=1.5, linestyle='--', label=f"Official NASDAQ-100 TR Index (^NDXT) (Final: {final_bench:.1f}%)")

    ax.set_title('Total Return Comparison (with Dividends): NASDAQ-100 Candidates vs NASDAQ-100', fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Date', fontsize=11, fontweight='semibold', labelpad=10)
    ax.set_ylabel('Cumulative Return (%)', fontsize=11, fontweight='semibold', labelpad=10)

    ax.grid(True, linestyle='--', alpha=0.6)
    ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='none')

    plt.tight_layout()
    plt.savefig(output_plot, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Plot saved to: {output_plot}")

    # Copy to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(output_plot, os.path.join(artifact_dir, 'candidates_vs_nasdaq100_total_return.png'))
except Exception as e:
    print(f"Error plotting: {e}")
