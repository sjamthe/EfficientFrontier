#!/usr/bin/env python3
import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Paths
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'SP500')
trades_csv = os.path.join(data_dir, 'nasdaq_20_total_return_trades.csv')
output_static_png = os.path.join(data_dir, 'nasdaq20_top_weights_over_time.png')
output_interactive_html = os.path.join(data_dir, 'nasdaq20_weights_interactive.html')

def main():
    if not os.path.exists(trades_csv):
        print(f"Error: Trades CSV not found at {trades_csv}")
        return

    # 1. Load and process trades data
    df = pd.read_csv(trades_csv)
    
    # We only care about the target weights set at rebalancing
    df_weights = df[['Quarter', 'Ticker', 'New_Weight_Pct']].drop_duplicates()
    
    # Pivot the data: Quarters as rows, Tickers as columns, New_Weight_Pct as values
    df_pivot = df_weights.pivot(index='Quarter', columns='Ticker', values='New_Weight_Pct').fillna(0.0)
    
    # Sort index chronologically
    df_pivot['Year'] = df_pivot.index.str[:4].astype(int)
    df_pivot['Q'] = df_pivot.index.str[5].astype(int)
    df_pivot = df_pivot.sort_values(['Year', 'Q']).drop(columns=['Year', 'Q'])
    
    quarters = df_pivot.index.tolist()
    tickers = df_pivot.columns.tolist()
    
    # Calculate dominance metrics for each ticker
    ticker_stats = []
    for ticker in tickers:
        series = df_pivot[ticker]
        avg_weight = series.mean()
        max_weight = series.max()
        quarters_active = int((series > 0.0).sum())
        ticker_stats.append({
            'Ticker': ticker,
            'Avg_Weight': avg_weight,
            'Max_Weight': max_weight,
            'Quarters_Active': quarters_active
        })
        
    df_stats = pd.DataFrame(ticker_stats).sort_values(by='Avg_Weight', ascending=False)
    
    # Get top 10 tickers by average weight
    top10_tickers = df_stats['Ticker'].head(10).tolist()
    print(f"Top 10 dominant tickers in NASDAQ-20 history by average weight:")
    for idx, row in df_stats.head(10).iterrows():
        print(f"  - {row['Ticker']}: Avg {row['Avg_Weight']:.2f}%, Max {row['Max_Weight']:.2f}%, Active in {row['Quarters_Active']}/78 quarters")

    # 2. Generate Static Matplotlib Plot (Top 10 Tickers)
    print(f"\nGenerating static plot for top 10 tickers: {output_static_png}")
    try:
        plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
        fig, ax = plt.subplots(figsize=(15, 8), dpi=300)
        
        # Color palette
        colors = plt.cm.tab10(np.linspace(0, 1, 10))
        
        # Sort top 10 tickers by their weight in the latest quarter (New %) descending
        latest_quarter = quarters[-1]
        top10_tickers_sorted = sorted(top10_tickers, key=lambda t: df_pivot.loc[latest_quarter, t], reverse=True)
        
        for idx, ticker in enumerate(top10_tickers_sorted):
            latest_weight = df_pivot.loc[latest_quarter, ticker]
            ax.plot(quarters, df_pivot[ticker], label=f"{ticker} (New: {latest_weight:.1f}%, Avg: {df_stats.loc[df_stats['Ticker'] == ticker, 'Avg_Weight'].values[0]:.1f}%)", 
                    linewidth=2.0, color=colors[idx])
            
        ax.set_title('Weight History of Top 10 Dominant Tickers in NASDAQ-20 (2007 - 2026)', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Quarter', fontsize=11, fontweight='semibold', labelpad=10)
        ax.set_ylabel('Allocation Weight (%)', fontsize=11, fontweight='semibold', labelpad=10)
        
        # Adjust x-axis ticks to show once a year
        ax.xaxis.set_major_locator(plt.MultipleLocator(4))
        plt.xticks(rotation=90, fontsize=8)
        
        max_val_top10 = df_pivot[top10_tickers].values.max()
        ax.set_ylim(0, max_val_top10 + 1.0)
        ax.yaxis.set_major_locator(plt.MultipleLocator(1))
        
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), frameon=True, facecolor='white', edgecolor='none')
        
        plt.tight_layout()
        plt.savefig(output_static_png, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"Static plot saved.")
        
        # Copy static plot to artifact folder if it exists
        artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
        if os.path.exists(artifact_dir):
            import shutil
            shutil.copy(output_static_png, os.path.join(artifact_dir, 'nasdaq20_top_weights_over_time.png'))
    except Exception as e:
        print(f"Error generating static plot: {e}")

    # 3. Generate Interactive HTML File (Chart.js + CDN)
    print(f"Generating interactive dashboard at: {output_interactive_html}")
    
    quarters_json = json.dumps(quarters)
    
    datasets = []
    # Sort datasets so that the top 10 appear first in the legend
    sorted_tickers_for_js = df_stats['Ticker'].tolist()
    
    for ticker in sorted_tickers_for_js:
        weights_list = df_pivot[ticker].tolist()
        is_default_visible = ticker in top10_tickers
        
        # Simple stats for JavaScript table
        stat_row = df_stats[df_stats['Ticker'] == ticker].iloc[0]
        
        datasets.append({
            'label': ticker,
            'data': weights_list,
            'hidden': not is_default_visible, # hidden by default if not top 10
            'borderWidth': 2,
            'pointRadius': 2,
            'pointHoverRadius': 5,
            'fill': False,
            'avgWeight': round(float(stat_row['Avg_Weight']), 2),
            'maxWeight': round(float(stat_row['Max_Weight']), 2),
            'quartersActive': int(stat_row['Quarters_Active'])
        })
        
    datasets_json = json.dumps(datasets)
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NASDAQ-20 Weight History Dashboard</title>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #334155;
            --accent-color: #38bdf8;
            --accent-hover: #0ea5e9;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        header {
            margin-bottom: 25px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
        }
        
        h1 {
            margin: 0 0 5px 0;
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        p.subtitle {
            margin: 0;
            color: var(--text-muted);
            font-size: 14px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 3fr 1fr;
            gap: 20px;
        }
        
        @media (max-width: 1024px) {
            .grid {
                grid-template-columns: 1fr;
            }
        }
        
        .card {
            background-color: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            padding: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        
        .nav-bar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            background-color: var(--bg-color);
            padding: 10px 15px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }
        
        .nav-bar select {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            padding: 8px 12px;
            font-size: 13px;
            cursor: pointer;
        }
        
        .nav-bar select:focus {
            outline: none;
            border-color: var(--accent-color);
        }
        
        .nav-btn-group {
            display: flex;
            gap: 6px;
        }
        
        .nav-bar button {
            padding: 8px 14px;
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            cursor: pointer;
            font-weight: 600;
            font-size: 13px;
            transition: all 0.2s;
        }
        
        .nav-bar button:hover:not(:disabled) {
            background-color: #334155;
            border-color: var(--accent-color);
        }
        
        .nav-bar button:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }
        
        .chart-container {
            position: relative;
            height: 480px;
            width: 100%;
        }
        
        .controls {
            display: flex;
            flex-direction: column;
            gap: 15px;
            max-height: 590px;
        }
        
        .search-box {
            width: 100%;
            padding: 10px;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            box-sizing: border-box;
        }
        
        .search-box:focus {
            outline: none;
            border-color: var(--accent-color);
        }
        
        .btn-group {
            display: flex;
            gap: 8px;
        }
        
        button {
            padding: 8px 12px;
            background-color: var(--border-color);
            border: none;
            border-radius: 6px;
            color: var(--text-color);
            cursor: pointer;
            font-weight: 500;
            font-size: 12px;
            transition: background-color 0.2s;
        }
        
        button:hover {
            background-color: #475569;
        }
        
        button.btn-accent {
            background-color: var(--accent-color);
            color: #0f172a;
        }
        
        button.btn-accent:hover {
            background-color: var(--accent-hover);
        }
        
        .ticker-list-container {
            overflow-y: auto;
            flex-grow: 1;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: var(--bg-color);
        }
        
        .ticker-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        
        .ticker-table th {
            position: sticky;
            top: 0;
            background-color: #1e293b;
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-muted);
            font-weight: 600;
        }
        
        .ticker-table td {
            padding: 8px;
            border-bottom: 1px dotted var(--border-color);
        }
        
        .ticker-table tr:hover {
            background-color: rgba(56, 189, 248, 0.05);
        }
        
        .checkbox-cell {
            width: 30px;
            text-align: center;
        }
        
        .ticker-label {
            font-weight: 600;
            cursor: pointer;
            display: block;
            width: 100%;
        }
        
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            background-color: var(--border-color);
            color: var(--text-muted);
        }
        
        .badge.active {
            background-color: rgba(16, 185, 129, 0.2);
            color: #10b981;
        }
        
        .tip-banner {
            background-color: rgba(56, 189, 248, 0.05);
            border: 1px solid rgba(56, 189, 248, 0.2);
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 12px;
            color: var(--accent-color);
            display: flex;
            align-items: center;
            gap: 8px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>NASDAQ-20 Weight History Dashboard</h1>
            <p class="subtitle">Interactive tracking and comparison of historical rebalancing weights (2007 - 2026)</p>
        </header>
        
        <div class="grid">
            <!-- Chart Card -->
            <div class="card">
                <!-- Sliding Window Navigation Bar -->
                <div class="nav-bar">
                    <div class="nav-btn-group">
                        <button onclick="slideFirst()" id="btnFirst">« First</button>
                        <button onclick="slideLeft()" id="btnPrev">‹ Previous</button>
                    </div>
                    
                    <select id="quarterSelector" onchange="jumpToQuarter(this.value)">
                        <!-- Populated by JS -->
                    </select>
                    
                    <div class="nav-btn-group">
                        <button onclick="slideRight()" id="btnNext">Next ›</button>
                        <button onclick="slideLast()" id="btnLast">Last »</button>
                    </div>
                    
                    <select id="windowSizeSelector" onchange="changeWindowSize(this.value)">
                        <option value="2" selected>View: 2 Quarters</option>
                        <option value="4">View: 1 Year (4 Qtrs)</option>
                        <option value="8">View: 2 Years (8 Qtrs)</option>
                        <option value="999">View: Show All Time</option>
                    </select>
                </div>
                
                <div class="chart-container">
                    <canvas id="weightChart"></canvas>
                </div>
                
                <div class="tip-banner">
                    <strong>💡 Navigation Tip:</strong> Use the <b>Left Arrow (←)</b> and <b>Right Arrow (→)</b> keys on your keyboard to quickly scroll through quarters.
                </div>
            </div>
            
            <!-- Controls Card -->
            <div class="card controls">
                <input type="text" id="tickerSearch" class="search-box" placeholder="Search Ticker...">
                
                <div class="btn-group">
                    <button onclick="resetToTop10()" class="btn-accent">Reset (Top 10)</button>
                    <button onclick="clearAll()">Clear All</button>
                    <button onclick="selectAllVisible()">Select Visible</button>
                </div>
                
                <div class="ticker-list-container">
                    <table class="ticker-table" id="tickerTable">
                        <thead>
                            <tr>
                                <th class="checkbox-cell"><input type="checkbox" id="masterCheckbox" onclick="toggleAllVisible(this)"></th>
                                <th>Ticker</th>
                                <th>New %</th>
                                <th>Change %</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody id="tickerTableBody">
                            <!-- Populated by JavaScript -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        const quarters = __QUARTERS_JSON__;
        const datasets = __DATASETS_JSON__;
        
        let currentStartIndex = quarters.length - 2; // Default to the last 2 quarters
        let windowSize = 2;
        
        // Setup distinct colors using an HSL cycle
        datasets.forEach((ds, i) => {
            const hue = (i * 137.5) % 360;
            ds.borderColor = `hsl(${hue}, 70%, 55%)`;
            ds.backgroundColor = `hsl(${hue}, 70%, 55%)`;
        });
        
        // Initialize Chart.js
        const ctx = document.getElementById('weightChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: quarters,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#1e293b',
                        titleColor: '#38bdf8',
                        borderColor: '#334155',
                        borderWidth: 1,
                        padding: 10,
                        itemSort: function(a, b) {
                            return b.raw - a.raw;
                        },
                        filter: function(item) {
                            return item.parsed.y > 0.001;
                        },
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== null) {
                                    label += context.parsed.y.toFixed(2) + '%';
                                }
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: '#334155',
                            alpha: 0.1
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: {
                                size: 11,
                                weight: 'bold'
                            },
                            maxRotation: 0,
                            minRotation: 0,
                            autoSkip: false,
                            callback: function(val, index) {
                                const label = quarters[val];
                                // Show all labels if window is small, otherwise show once a year
                                if (windowSize <= 8) {
                                    return label;
                                }
                                return label.endsWith('Q1') ? label : '';
                            }
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Rebalancing Weight (%)',
                            color: '#94a3b8',
                            font: {
                                weight: 'bold'
                            }
                        },
                        grid: {
                            color: '#334155'
                        },
                        ticks: {
                            color: '#94a3b8'
                        },
                        min: 0
                    }
                }
            }
        });
        
        // Populate Table
        const tableBody = document.getElementById('tickerTableBody');
        
        function renderTable(filterText = '') {
            tableBody.innerHTML = '';
            const search = filterText.toUpperCase();
            
            const latestIdx = currentStartIndex + windowSize - 1;
            
            // Create a list of datasets with their original indices
            const sortedList = datasets.map((ds, index) => ({ ds, index }))
                .filter(item => {
                    if (search && !item.ds.label.includes(search)) return false;
                    return true;
                });
                
            // Sort by current weight (New %) descending
            sortedList.sort((a, b) => {
                const weightA = a.ds.data[latestIdx];
                const weightB = b.ds.data[latestIdx];
                return weightB - weightA;
            });
            
            sortedList.forEach(item => {
                const ds = item.ds;
                const index = item.index;
                
                const currentWeight = ds.data[latestIdx];
                const prevWeight = ds.data[currentStartIndex];
                const weightChange = currentWeight - prevWeight;
                
                const tr = document.createElement('tr');
                tr.setAttribute('data-ticker', ds.label);
                
                const dotHtml = `<span style="display:inline-block; width:8px; height:8px; border-radius:50%; background-color:${ds.borderColor}; margin-right:6px;"></span>`;
                
                // Format change indicator
                let changeBadge = '';
                if (weightChange > 0.001) {
                    changeBadge = `<span style="color:#10b981; font-weight:bold;">+${weightChange.toFixed(2)}%</span>`;
                } else if (weightChange < -0.001) {
                    changeBadge = `<span style="color:#ef4444; font-weight:bold;">${weightChange.toFixed(2)}%</span>`;
                } else {
                    changeBadge = `<span style="color:var(--text-muted);">0.00%</span>`;
                }
                
                tr.innerHTML = `
                    <td class="checkbox-cell">
                        <input type="checkbox" id="chk_${ds.label}" data-index="${index}" ${!ds.hidden ? 'checked' : ''} onchange="toggleTicker(this)">
                    </td>
                    <td>
                        <label for="chk_${ds.label}" class="ticker-label">${dotHtml}${ds.label}</label>
                    </td>
                    <td>${currentWeight.toFixed(2)}%</td>
                    <td>${changeBadge}</td>
                    <td><span class="badge ${currentWeight > 0.001 ? 'active' : ''}">${currentWeight > 0.001 ? 'Active' : 'Out'}</span></td>
                `;
                tableBody.appendChild(tr);
            });
        }
        
        // Toggle single ticker checkbox
        function toggleTicker(checkbox) {
            const index = checkbox.getAttribute('data-index');
            const isChecked = checkbox.checked;
            
            datasets[index].hidden = !isChecked;
            chart.update();
        }
        
        // Populate dropdown selectors for navigation
        const quarterSelector = document.getElementById('quarterSelector');
        function populateQuarterSelector() {
            quarterSelector.innerHTML = '';
            const maxStart = quarters.length - windowSize;
            
            for (let i = 0; i <= maxStart; i++) {
                const opt = document.createElement('option');
                opt.value = i;
                if (windowSize === 1) {
                    opt.textContent = quarters[i];
                } else {
                    opt.textContent = `${quarters[i]} - ${quarters[i + windowSize - 1]}`;
                }
                opt.selected = (i === currentStartIndex);
                quarterSelector.appendChild(opt);
            }
        }
        
        // Update Chart Visible Range
        function updateChartWindow() {
            chart.options.scales.x.min = currentStartIndex;
            chart.options.scales.x.max = currentStartIndex + windowSize - 1;
            chart.update();
            
            // Sync controls
            document.getElementById('btnFirst').disabled = (currentStartIndex === 0);
            document.getElementById('btnPrev').disabled = (currentStartIndex === 0);
            
            const isAtEnd = (currentStartIndex + windowSize >= quarters.length);
            document.getElementById('btnNext').disabled = isAtEnd;
            document.getElementById('btnLast').disabled = isAtEnd;
            
            quarterSelector.value = currentStartIndex;
            
            // Re-render table to sort dynamically by new visible weights!
            renderTable(document.getElementById('tickerSearch').value);
        }
        
        function slideLeft() {
            if (currentStartIndex > 0) {
                currentStartIndex--;
                updateChartWindow();
            }
        }
        
        function slideRight() {
            if (currentStartIndex + windowSize < quarters.length) {
                currentStartIndex++;
                updateChartWindow();
            }
        }
        
        function slideFirst() {
            currentStartIndex = 0;
            updateChartWindow();
        }
        
        function slideLast() {
            currentStartIndex = quarters.length - windowSize;
            updateChartWindow();
        }
        
        function jumpToQuarter(indexVal) {
            currentStartIndex = parseInt(indexVal);
            updateChartWindow();
        }
        
        function changeWindowSize(sizeVal) {
            let selectedSize = parseInt(sizeVal);
            if (selectedSize > quarters.length) {
                selectedSize = quarters.length;
            }
            windowSize = selectedSize;
            
            if (currentStartIndex + windowSize > quarters.length) {
                currentStartIndex = quarters.length - windowSize;
            }
            
            populateQuarterSelector();
            updateChartWindow();
        }
        
        // Reset to default top 10 tickers
        function resetToTop10() {
            const top10 = __TOP10_TICKERS_JSON__;
            datasets.forEach((ds) => {
                ds.hidden = !top10.includes(ds.label);
            });
            chart.update();
            renderTable(document.getElementById('tickerSearch').value);
        }
        
        // Clear all selected tickers
        function clearAll() {
            datasets.forEach((ds) => {
                ds.hidden = true;
            });
            chart.update();
            renderTable(document.getElementById('tickerSearch').value);
        }
        
        // Select all visible tickers based on search filter
        function selectAllVisible() {
            const search = document.getElementById('tickerSearch').value.toUpperCase();
            datasets.forEach((ds) => {
                if (!search || ds.label.includes(search)) {
                    ds.hidden = false;
                }
            });
            chart.update();
            renderTable(search);
        }
        
        // Toggle checkbox master
        function toggleAllVisible(master) {
            const search = document.getElementById('tickerSearch').value.toUpperCase();
            datasets.forEach((ds) => {
                if (!search || ds.label.includes(search)) {
                    ds.hidden = !master.checked;
                }
            });
            chart.update();
            renderTable(search);
        }
        
        // Search Filter Event
        document.getElementById('tickerSearch').addEventListener('input', function(e) {
            renderTable(e.target.value);
            document.getElementById('masterCheckbox').checked = false;
        });
        
        // Setup Keyboard Navigation
        document.addEventListener('keydown', function(event) {
            // Ignore keypresses inside search input
            if (document.activeElement === document.getElementById('tickerSearch')) {
                return;
            }
            if (event.key === 'ArrowLeft') {
                slideLeft();
            } else if (event.key === 'ArrowRight') {
                slideRight();
            }
        });
        
        // Initial dashboard setup
        populateQuarterSelector();
        updateChartWindow();
        renderTable();
    </script>
</body>
</html>
"""

    # Inject variables without python f-string curly brace errors
    html_content = html_content.replace('__QUARTERS_JSON__', quarters_json)
    html_content = html_content.replace('__DATASETS_JSON__', datasets_json)
    html_content = html_content.replace('__TOP10_TICKERS_JSON__', json.dumps(top10_tickers))

    with open(output_interactive_html, 'w') as f:
        f.write(html_content)
    print("Interactive HTML dashboard written successfully.")
    
    # Copy HTML to artifact folder if it exists
    artifact_dir = '/Users/sjamthe/.gemini/antigravity-ide/brain/c97a0c5d-2fd6-4ac1-ab91-853c8103ac79'
    if os.path.exists(artifact_dir):
        import shutil
        shutil.copy(output_interactive_html, os.path.join(artifact_dir, 'nasdaq20_weights_interactive.html'))
        print(f"Copied to artifact directory: {os.path.join(artifact_dir, 'nasdaq20_weights_interactive.html')}")

if __name__ == "__main__":
    main()
