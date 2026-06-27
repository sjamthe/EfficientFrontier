import os
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt

def main():
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, 'SP500')
    nasdaq20_path = os.path.join(data_dir, 'nasdaq_20_total_return_returns.csv')
    
    if not os.path.exists(nasdaq20_path):
        print(f"Error: NASDAQ-20 returns file not found at {nasdaq20_path}")
        return
        
    # 1. Load NASDAQ-20 returns
    df_n20 = pd.read_csv(nasdaq20_path)
    df_n20['Date'] = pd.to_datetime(df_n20['Date'])
    df_n20 = df_n20.set_index('Date')
    
    # Extract NASDAQ-20 daily returns
    n20_daily = df_n20['Daily_Return']
    start_date = n20_daily.index.min().strftime('%Y-%m-%d')
    end_date = n20_daily.index.max().strftime('%Y-%m-%d')
    
    print(f"NASDAQ-20 returns loaded: {start_date} to {end_date} ({len(n20_daily)} days)")
    
    # 2. Download ETF and benchmark data
    tickers = ['MGK', 'VGT', '^GSPC']
    print(f"Downloading historical data for {tickers} from {start_date} to {end_date}...")
    
    # Download with a bit of buffer
    download_start = (n20_daily.index.min() - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
    download_end = (n20_daily.index.max() + pd.Timedelta(days=5)).strftime('%Y-%m-%d')
    
    df_raw = yf.download(tickers, start=download_start, end=download_end, progress=False)
    
    # Extract Adj Close for ETFs and Close for GSPC
    df_prices = pd.DataFrame()
    for t in tickers:
        if ('Adj Close', t) in df_raw.columns:
            df_prices[t] = df_raw[('Adj Close', t)]
        elif ('Close', t) in df_raw.columns:
            df_prices[t] = df_raw[('Close', t)]
            
    # Calculate daily returns (without dropna so we don't truncate pre-2007 data for VGT/GSPC)
    df_returns = df_prices.pct_change(fill_method=None)
    
    # Align to NASDAQ-20 index
    # We want to match trading days
    df_all_returns = pd.DataFrame({
        'NASDAQ-20': n20_daily,
        'MGK': df_returns['MGK'],
        'VGT': df_returns['VGT'],
        'S&P 500': df_returns['^GSPC']
    })
    
    # Let's inspect when MGK started having valid data
    mgk_valid = df_all_returns['MGK'].dropna()
    common_start_date = mgk_valid.index.min()
    print(f"MGK data starts on: {common_start_date.strftime('%Y-%m-%d')}")
    
    # We will analyze two periods:
    # 1. Full period (starting when NASDAQ-20 starts, excluding MGK)
    # 2. Common period (starting when MGK starts, including all)
    
    periods = {
        'Full Period (Jan 2007 - Jun 2026)': {
            'start': n20_daily.index.min(),
            'end': n20_daily.index.max(),
            'assets': ['NASDAQ-20', 'VGT', 'S&P 500']
        },
        'Common Period (Dec 2007 - Jun 2026)': {
            'start': common_start_date,
            'end': n20_daily.index.max(),
            'assets': ['NASDAQ-20', 'MGK', 'VGT', 'S&P 500']
        }
    }
    
    for period_name, info in periods.items():
        print(f"\n======================================================================")
        print(f"ANALYSIS FOR: {period_name}")
        print(f"Date Range: {info['start'].strftime('%Y-%m-%d')} to {info['end'].strftime('%Y-%m-%d')}")
        print(f"======================================================================")
        
        # Slice data for the period
        df_period = df_all_returns.loc[info['start']:info['end'], info['assets']]
        assets = [a for a in info['assets'] if a in df_period.columns]
        
        # Metrics storage
        metrics = []
        
        for asset in assets:
            # Drop NaNs specifically for this asset and GSPC
            if asset == 'S&P 500':
                df_asset_period = df_period[['S&P 500']].dropna()
                if df_asset_period.empty:
                    continue
                daily_ret = df_asset_period['S&P 500']
                market_ret = daily_ret
            else:
                df_asset_period = df_period[[asset, 'S&P 500']].dropna()
                if df_asset_period.empty:
                    continue
                daily_ret = df_asset_period[asset]
                market_ret = df_asset_period['S&P 500']
            
            # Cumulative Return
            cum_ret = (1.0 + daily_ret).cumprod().iloc[-1] - 1.0
            
            # Annualized Return (CAGR)
            n_days = len(daily_ret)
            years = n_days / 252.0
            cagr = (1.0 + cum_ret) ** (1.0 / years) - 1.0
            
            # Annualized Volatility
            vol = daily_ret.std() * np.sqrt(252)
            
            # Sharpe Ratio (Rf = 0% and Rf = 3%)
            sharpe_0 = cagr / vol if vol > 0 else np.nan
            sharpe_3 = (cagr - 0.03) / vol if vol > 0 else np.nan
            
            # Beta relative to S&P 500
            cov = daily_ret.cov(market_ret)
            market_var = market_ret.var()
            beta = cov / market_var if market_var > 0 else np.nan
            
            # Max Drawdown
            cum_prices = (1.0 + daily_ret).cumprod()
            running_max = cum_prices.cummax()
            drawdowns = (cum_prices - running_max) / running_max
            max_dd = drawdowns.min()
            
            metrics.append({
                'Asset': asset,
                'Cumulative Return (%)': cum_ret * 100,
                'Annualized Return (CAGR) (%)': cagr * 100,
                'Annualized Volatility (%)': vol * 100,
                'Sharpe Ratio (Rf=0%)': sharpe_0,
                'Sharpe Ratio (Rf=3%)': sharpe_3,
                'Beta (vs S&P 500)': beta,
                'Max Drawdown (%)': max_dd * 100
            })
            
        df_metrics = pd.DataFrame(metrics).set_index('Asset')
        print(df_metrics.to_string())
        
        # Save CSV
        csv_filename = os.path.join(data_dir, f"etf_comparison_{period_name.split(' ')[0].lower()}.csv")
        df_metrics.to_csv(csv_filename)
        print(f"Saved metrics to: {csv_filename}")
        
        # Plotting
        if 'MGK' in assets:  # Plot for Common Period
            plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
            fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
            
            # Colors
            colors = {
                'NASDAQ-20': '#2ca02c', # Green
                'MGK': '#1f77b4',       # Blue
                'VGT': '#ff7f0e',       # Orange
                'S&P 500': '#7f7f7f'    # Gray (Dashed)
            }
            
            for asset in assets:
                cum_ret_series = (1.0 + df_period[asset]).cumprod() - 1.0
                label = f"{asset} (Final: {cum_ret_series.iloc[-1]*100:.1f}%)"
                linestyle = '--' if asset == 'S&P 500' else '-'
                linewidth = 1.5 if asset == 'S&P 500' else 2.0
                ax.plot(df_period.index, cum_ret_series * 100, 
                        color=colors.get(asset, '#1f77b4'), 
                        linestyle=linestyle, 
                        linewidth=linewidth, 
                        label=label)
                
            ax.set_title('Cumulative Total Return Comparison: NASDAQ-20 vs MGK vs VGT vs S&P 500\n(Common Period: Dec 2007 - Jun 2026)', 
                         fontsize=14, fontweight='bold', pad=15)
            ax.set_xlabel('Date', fontsize=11, fontweight='semibold', labelpad=10)
            ax.set_ylabel('Cumulative Return (%)', fontsize=11, fontweight='semibold', labelpad=10)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='none')
            
            # Format y axis with commas and percent sign
            import matplotlib.ticker as mtick
            ax.yaxis.set_major_formatter(mtick.PercentFormatter())
            
            plt.tight_layout()
            plot_path = os.path.join(data_dir, 'compare_etfs_chart.png')
            plt.savefig(plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"Saved comparison plot to: {plot_path}")
            
            # Copy to artifact folder if it exists
            artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/8e2d041a-13ae-4543-8077-93902bf9b496'
            if os.path.exists(artifact_dir):
                import shutil
                shutil.copy(plot_path, os.path.join(artifact_dir, 'compare_etfs_chart.png'))
                print(f"Copied plot to artifact folder.")

if __name__ == '__main__':
    main()
