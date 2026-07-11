import os
import json
import pandas as pd
from datetime import datetime

def reconstruct_nasdaq_history(start_year=1997, end_year=2006):
    """
    Reconstructs NASDAQ-100 constituents quarterly from start_yearQ1 to end_yearQ4.
    Returns a dict mapping quarter (e.g. '1997Q1') to:
    {
        'Start_Date': str,
        'End_Date': str,
        'Constituents': list of str,
        'Additions': list of str,
        'Removals': list of str
    }
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    changes_path = os.path.join(script_dir, 'unique_historical_changes.json')
    wiki_path = os.path.join(script_dir, 'wiki_quarterly_constituents.json')
    
    with open(changes_path, 'r') as f:
        changes = json.load(f)
        
    with open(wiki_path, 'r') as f:
        wiki_quarters = json.load(f)
        
    # Sort changes descending by Date
    changes_desc = sorted(changes, key=lambda x: x['Date'], reverse=True)
    
    alias_map = {
        'EXDS': 'EXDSQ',
        'IDPH': 'BIIB',
        'TMPW': 'MNST',
        'GMST': 'GMSTE',
        'ADLAC': 'ADLAE',
        'NXLK': 'XOXO',
        'UNPH': 'JDSU',
        'ATHM': 'ATHMQ',
        'USAI': 'IACI',
        'JJSC': 'SSCC',
        'SPOT': 'SPOTE'
    }
    
    # We will build the timeline from 1997Q1 to 2006Q4
    quarter_data = {}
    
    # 1. Quarters 2004Q1 to 2006Q4 are loaded directly from Wikipedia snapshots
    for y in range(2004, 2007):
        for q in [1, 2, 3, 4]:
            q_name = f"{y}Q{q}"
            if q_name in wiki_quarters:
                consts = set(wiki_quarters[q_name])
                # Quarter dates
                if q == 1:
                    q_start, q_end = f"{y}-01-01", f"{y}-03-31"
                elif q == 2:
                    q_start, q_end = f"{y}-04-01", f"{y}-06-30"
                elif q == 3:
                    q_start, q_end = f"{y}-07-01", f"{y}-09-30"
                else:
                    q_start, q_end = f"{y}-10-01", f"{y}-12-31"
                
                quarter_data[q_name] = {
                    'Start_Date': q_start,
                    'End_Date': q_end,
                    'Constituents': sorted(list(consts)),
                    'Additions': [],
                    'Removals': []
                }
                
    # Fill in additions and removals for 2004Q1 to 2006Q4 by comparing adjacent quarters
    # We need 2003Q4 first, which we will compute below, so we'll do additions/removals diffs later.
    
    # 2. Roll backward from 2004Q1 to 1997Q1
    # We start with 2004Q1 constituents
    current_consts = set(quarter_data['2004Q1']['Constituents'])
    
    # Generate list of quarters to roll backward
    roll_quarters = []
    for y in range(2003, start_year - 1, -1):
        for q in [4, 3, 2, 1]:
            roll_quarters.append((y, q))
            
    # We trace from 2004-03-31 backwards
    last_end_date = "2004-03-31"
    
    for y, q in roll_quarters:
        q_name = f"{y}Q{q}"
        if q == 1:
            q_start, q_end = f"{y}-01-01", f"{y}-03-31"
        elif q == 2:
            q_start, q_end = f"{y}-04-01", f"{y}-06-30"
        elif q == 3:
            q_start, q_end = f"{y}-07-01", f"{y}-09-30"
        else:
            q_start, q_end = f"{y}-10-01", f"{y}-12-31"
            
        # Find all changes that occurred AFTER q_end and BEFORE OR ON last_end_date
        # (Rolling backward from last_end_date to q_end)
        chgs_in_between = [c for c in changes_desc if q_end < c['Date'] <= last_end_date]
        
        # Apply backward: remove added ticker, add removed ticker
        for chg in chgs_in_between:
            add = chg['Added_Ticker']
            rem = chg['Removed_Ticker']
            
            if add in current_consts:
                current_consts.remove(add)
            else:
                alias = alias_map.get(add)
                if alias and alias in current_consts:
                    current_consts.remove(alias)
                else:
                    # check suffixes
                    found_suff = False
                    for suff in ['Q', 'E', 'A', 'B', 'C']:
                        if (add + suff) in current_consts:
                            current_consts.remove(add + suff)
                            found_suff = True
                            break
            current_consts.add(rem)
            
        quarter_data[q_name] = {
            'Start_Date': q_start,
            'End_Date': q_end,
            'Constituents': sorted(list(current_consts)),
            'Additions': [],
            'Removals': []
        }
        
        last_end_date = q_end
        
    # 3. Compute Additions and Removals for all quarters from 1997Q2 to 2006Q4
    # For a quarter Q_t, additions = Q_t - Q_{t-1}, removals = Q_{t-1} - Q_t
    sorted_q_names = []
    for y in range(start_year, 2007):
        for q in [1, 2, 3, 4]:
            sorted_q_names.append(f"{y}Q{q}")
            
    for idx in range(1, len(sorted_q_names)):
        prev_q = sorted_q_names[idx-1]
        curr_q = sorted_q_names[idx]
        
        prev_consts = set(quarter_data[prev_q]['Constituents'])
        curr_consts = set(quarter_data[curr_q]['Constituents'])
        
        adds = curr_consts - prev_consts
        rems = prev_consts - curr_consts
        
        quarter_data[curr_q]['Additions'] = sorted(list(adds))
        quarter_data[curr_q]['Removals'] = sorted(list(rems))
        
    # For 1997Q1 (first quarter), we don't have a previous quarter, so additions and removals are empty
    quarter_data[f"{start_year}Q1"]['Additions'] = []
    quarter_data[f"{start_year}Q1"]['Removals'] = []
    
    return quarter_data

if __name__ == '__main__':
    # Test execution
    data = reconstruct_nasdaq_history()
    print("Reconstructed quarters count:", len(data))
    print("Sample 1997Q1 count:", len(data['1997Q1']['Constituents']))
    print("Sample 2000Q1 count:", len(data['2000Q1']['Constituents']))
    print("Sample 2006Q4 count:", len(data['2006Q4']['Constituents']))
