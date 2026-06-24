import os
import urllib.request
import pandas as pd
import numpy as np
import yfinance as yf

# 1. Paths configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, '..', 'SP500')
pkl_dir = os.path.join(data_dir, 'data_raw')

def calculate_portfolio_returns(constituent_csv_name, weight_scheme='equal', return_type='price', benchmark_ticker=None, portfolio_name='custom_portfolio'):
    print(f"\n==================================================")
    print(f"Calculating returns for {portfolio_name}")
    print(f"Constituent CSV: {constituent_csv_name}")
    print(f"Weighting Scheme: {weight_scheme}")
    print(f"Return Type: {return_type}")
    print(f"Benchmark: {benchmark_ticker}")
    print(f"==================================================")
    
    constituent_csv_path = os.path.join(data_dir, constituent_csv_name)
    metadata_csv_path = os.path.join(data_dir, 'ticker_metadata.csv')
    output_csv_path = os.path.join(data_dir, f"{portfolio_name}_returns.csv")
    output_plot_path = os.path.join(data_dir, f"{portfolio_name}_returns_chart.png")
    
    # Check if files exist
    if not os.path.exists(constituent_csv_path):
        raise FileNotFoundError(f"Missing constituent CSV: {constituent_csv_path}")
        
    df_quarters = pd.read_csv(constituent_csv_path)
    df_quarters['Start_Date'] = pd.to_datetime(df_quarters['Start_Date'])
    df_quarters['End_Date'] = pd.to_datetime(df_quarters['End_Date'])
    
    # Sort chronologically by Quarter
    df_quarters['Year'] = df_quarters['Quarter'].str[:4].astype(int)
    df_quarters['Q'] = df_quarters['Quarter'].str[5].astype(int)
    df_quarters = df_quarters.sort_values(['Year', 'Q']).reset_index(drop=True)
    
    # Load metadata if capitalization weighting is used
    metadata = {}
    if weight_scheme == 'cap':
        if os.path.exists(metadata_csv_path):
            df_meta = pd.read_csv(metadata_csv_path)
            for idx, row in df_meta.iterrows():
                metadata[row['Ticker']] = row['Shares_Outstanding']
        else:
            print("Warning: ticker_metadata.csv not found. Capitalization weighting will fall back to Equal weighting.")
            weight_scheme = 'equal'
            
    # Load all unique tickers in this dataset
    unique_tickers = set()
    col_name = 'Candidates' if 'Candidates' in df_quarters.columns else ('Constituents' if 'Constituents' in df_quarters.columns else 'Unique_Nasdaq_Tickers')
    for val in df_quarters[col_name]:
        if pd.notna(val):
            unique_tickers.update([t.strip() for t in str(val).split(',') if t.strip()])
            
    unique_tickers = sorted(list(unique_tickers))
    print(f"Loading prices for {len(unique_tickers)} unique tickers...")
    
    # Load daily prices
    price_dict = {}
    col_to_use = 'Close' if return_type == 'price' else 'Adj Close'
    
    for ticker in unique_tickers:
        pkl_path = os.path.join(pkl_dir, f"{ticker}.pkl")
        if os.path.exists(pkl_path):
            try:
                df_t = pd.read_pickle(pkl_path)
                # Check for target column in MultiIndex
                if (col_to_use, ticker) in df_t.columns:
                    price_dict[ticker] = df_t[(col_to_use, ticker)]
                elif col_to_use in df_t.columns:
                    price_dict[ticker] = df_t[col_to_use]
                # Fallback to standard Close
                elif ('Close', ticker) in df_t.columns:
                    price_dict[ticker] = df_t[('Close', ticker)]
                elif 'Close' in df_t.columns:
                    price_dict[ticker] = df_t['Close']
            except Exception as e:
                print(f"  Error reading price file for {ticker}: {e}")
                
    df_prices = pd.DataFrame(price_dict)
    df_prices.index = pd.to_datetime(df_prices.index)
    df_prices = df_prices.sort_index()
    
    # Clean price data: if price > 10000, set to NaN and forward-fill (handles delisted outliers)
    df_prices = df_prices.mask(df_prices > 10000, np.nan)
    df_prices = df_prices.ffill().bfill()
    
    # Daily returns for all stocks
    df_stock_returns = df_prices.pct_change(fill_method=None)
    
    # Clean stock returns: if return > 1.0 or < -0.9, replace with 0.0 (handles delisted spikes)
    bad_returns_mask = (df_stock_returns > 1.0) | (df_stock_returns < -0.9)
    df_stock_returns = df_stock_returns.mask(bad_returns_mask, 0.0)

    
    # Set up portfolio returns tracking
    portfolio_daily_returns = pd.Series(index=df_prices.index, dtype=float)
    
    # Run backtest quarter by quarter
    for idx, row in df_quarters.iterrows():
        q_name = row['Quarter']
        q_start = row['Start_Date']
        q_end = row['End_Date']
        
        # Get active constituents in this quarter
        q_constituents = [t.strip() for t in str(row[col_name]).split(',') if t.strip()]
        # Filter to constituents that actually have price data
        q_constituents = [t for t in q_constituents if t in df_prices.columns]
        
        if not q_constituents:
            continue
            
        # Get trading days in this quarter
        q_days = df_prices.index[(df_prices.index >= q_start) & (df_prices.index <= q_end)]
        if len(q_days) == 0:
            continue
            
        # Calculate initial weights at the start of the quarter
        first_day = q_days[0]
        active_prices = df_prices.loc[first_day, q_constituents]
        
        # Drop tickers that are NaN on the first day
        valid_constituents = active_prices.dropna().index.tolist()
        if not valid_constituents:
            continue
            
        N = len(valid_constituents)
        
        # Weighting schemes
        if weight_scheme == 'equal':
            weights = pd.Series({t: 1.0 / N for t in valid_constituents})
        elif weight_scheme == 'price':
            sum_prices = active_prices[valid_constituents].sum()
            weights = pd.Series({t: active_prices[t] / sum_prices if sum_prices > 0 else 1.0 / N for t in valid_constituents})
        elif weight_scheme == 'cap':
            mcap_proxies = {}
            for t in valid_constituents:
                shares = metadata.get(t, np.nan)
                if pd.isna(shares) or shares <= 0:
                    shares = 1.0 # fallback
                mcap_proxies[t] = active_prices[t] * shares
                
            sum_mcap = sum(mcap_proxies.values())
            if sum_mcap > 0:
                weights = pd.Series({t: mcap_proxies[t] / sum_mcap for t in valid_constituents})
            else:
                weights = pd.Series({t: 1.0 / N for t in valid_constituents})
            
            # Apply 10% weight ceiling to prevent extreme outlier dominance and re-normalize
            weights = weights.clip(upper=0.10)
            weights = weights / weights.sum()
            
        current_weights = pd.Series(weights)

        
        for t in q_days:
            # Check if we have stock returns for this day
            daily_stock_ret = df_stock_returns.loc[t, valid_constituents].fillna(0.0)
            
            # Portfolio return is weighted sum of stock returns
            port_ret = np.sum(current_weights * daily_stock_ret)
            portfolio_daily_returns.loc[t] = port_ret
            
            # Drift weights based on daily return
            drift_factor = (1.0 + daily_stock_ret) / (1.0 + port_ret)
            current_weights = current_weights * drift_factor
            
            # Re-normalize
            sum_w = current_weights.sum()
            if sum_w > 0:
                current_weights = current_weights / sum_w

    # Clean returns series
    portfolio_daily_returns = portfolio_daily_returns.dropna()
    if portfolio_daily_returns.empty:
        print("  Error: Portfolio returns series is empty.")
        return
        
    start_trade_date = portfolio_daily_returns.index.min()
    end_trade_date = portfolio_daily_returns.index.max()
    
    # Calculate cumulative returns
    cum_returns = (1.0 + portfolio_daily_returns).cumprod() - 1.0
    
    # 5. Fetch benchmark daily prices if provided
    df_bench_cum = None
    if benchmark_ticker:
        print(f"Fetching benchmark {benchmark_ticker} price history...")
        try:
            df_bench = yf.download(benchmark_ticker, start=start_trade_date.strftime('%Y-%m-%d'), end=end_trade_date.strftime('%Y-%m-%d'), progress=False)
            if not df_bench.empty:
                if 'Close' in df_bench.columns:
                    bench_close = df_bench['Close']
                else:
                    bench_close = df_bench.iloc[:, 0]
                    
                if hasattr(bench_close, 'squeeze'):
                    bench_close = bench_close.squeeze()
                    
                bench_close = bench_close.dropna()
                bench_returns = bench_close.pct_change(fill_method=None).dropna()
                bench_returns = bench_returns[bench_returns.index.isin(portfolio_daily_returns.index)]
                df_bench_cum = (1.0 + bench_returns).cumprod() - 1.0
                
                if hasattr(df_bench_cum, 'squeeze'):
                    df_bench_cum = df_bench_cum.squeeze()
        except Exception as e:
            print(f"  Error fetching benchmark returns: {e}")
            
    # Save returns CSV
    df_output = pd.DataFrame({'Daily_Return': portfolio_daily_returns, 'Cumulative_Return': cum_returns})
    if df_bench_cum is not None:
        df_output = df_output.join(pd.DataFrame({'Benchmark_Return': df_bench_cum}), how='left')
    df_output.to_csv(output_csv_path)
    print(f"Saved returns to: {output_csv_path}")
    
    # 6. Plot the comparison
    try:
        import matplotlib.pyplot as plt
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
        
        # Plot portfolio returns (percentage)
        ax.plot(cum_returns.index, cum_returns * 100, color='#1f77b4', linewidth=1.8, label=f"{portfolio_name} ({weight_scheme.upper()}-Weight)")
        
        if df_bench_cum is not None:
            ax.plot(df_bench_cum.index, df_bench_cum * 100, color='#7f7f7f', linewidth=1.5, linestyle='--', label=f"Benchmark {benchmark_ticker}")
            
        ax.set_title(f"Index Return Comparison ({return_type.upper()} Return): {portfolio_name} vs Benchmark", fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Date', fontsize=11, fontweight='semibold', labelpad=10)
        ax.set_ylabel('Cumulative Return (%)', fontsize=11, fontweight='semibold', labelpad=10)
        
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(loc='upper left', frameon=True, facecolor='white', edgecolor='none')
        
        plt.tight_layout()
        plt.savefig(output_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Plot saved to: {output_plot_path}")
        
        # Copy to artifact folder if it exists
        artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
        if os.path.exists(artifact_dir):
            import shutil
            shutil.copy(output_plot_path, os.path.join(artifact_dir, f"{portfolio_name}_returns_chart.png"))
    except Exception as e:
        print(f"  Error generating return comparison plot: {e}")

# If run directly, run calculations for all portfolios
if __name__ == '__main__':
    # 1. S&P 500 Price Return (Raw Close vs ^GSPC price benchmark)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='sp500_quarterly_history.csv',
            weight_scheme='cap',
            return_type='price',
            benchmark_ticker='^GSPC',
            portfolio_name='sp500_price_return'
        )
    except Exception as e:
        print(f"S&P 500 price return reconstruction failed: {e}")

    # 2. S&P 500 Total Return (Adj Close vs ^SP500TR total return benchmark)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='sp500_quarterly_history.csv',
            weight_scheme='cap',
            return_type='total',
            benchmark_ticker='^SP500TR',
            portfolio_name='sp500_total_return'
        )
    except Exception as e:
        print(f"S&P 500 total return reconstruction failed: {e}")
        
    # 3. NASDAQ-100 Price Return (Raw Close vs ^NDX price benchmark)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='nasdaq_quarterly_history.csv',
            weight_scheme='cap',
            return_type='price',
            benchmark_ticker='^NDX',
            portfolio_name='nasdaq100_price_return'
        )
    except Exception as e:
        print(f"NASDAQ-100 price return reconstruction failed: {e}")

    # 4. NASDAQ-100 Total Return (Adj Close vs ^NDXT total return benchmark)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='nasdaq_quarterly_history.csv',
            weight_scheme='cap',
            return_type='total',
            benchmark_ticker='^NDXT',
            portfolio_name='nasdaq100_total_return'
        )
    except Exception as e:
        print(f"NASDAQ-100 total return reconstruction failed: {e}")
        
    # 5. NASDAQ-100 NOT in S&P 500 (Price Return vs ^NDX)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='nasdaq_not_sp500_quarterly.csv',
            weight_scheme='equal',
            return_type='price',
            benchmark_ticker='^NDX',
            portfolio_name='nasdaq_not_sp500_price_return'
        )
    except Exception as e:
        print(f"NASDAQ-100 minus S&P 500 portfolio calculation failed: {e}")

    # 6. NASDAQ-100 AND S&P 500 (Intersection) Total Return (Adj Close vs ^NDXT)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='nasdaq_and_sp500_quarterly.csv',
            weight_scheme='cap',
            return_type='total',
            benchmark_ticker='^NDXT',
            portfolio_name='nasdaq_and_sp500_total_return'
        )
    except Exception as e:
        print(f"NASDAQ-100 and S&P 500 intersection portfolio calculation failed: {e}")

    # 7. NASDAQ-100 Candidate Queue Total Return (Adj Close vs ^NDXT)
    try:
        calculate_portfolio_returns(
            constituent_csv_name='nasdaq_candidate_queue.csv',
            weight_scheme='cap',
            return_type='total',
            benchmark_ticker='^NDXT',
            portfolio_name='nasdaq_candidate_queue_total_return'
        )
    except Exception as e:
        print(f"NASDAQ-100 Candidate Queue portfolio calculation failed: {e}")

