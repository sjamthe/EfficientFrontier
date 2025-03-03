#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 11 20:50:39 2023

@author: sjamthe
"""

import pandas as pd
from itertools import combinations, permutations, product
import pickle
from datetime import datetime
import numpy as np
import math

# possible_weights replaced port_weights
possible_weights = [.05,.10,.15,.20]
portfolio_size = 10

# Selected as +-25% of market risk in 10 bands of 1% each
riskbands = [0.10,0.11,0.12,0.13,0.14,0.15,0.16,0.17,0.18,0.19,0.20]
#Count of portfolios foundCounter in each chunk
foundCounter = 0
oldFoundCounter = 0


# On 5-11-2023 obtained data using
#from get_yahoo_monthly_returns import get_monthly_returns_for_n_years 
#df = get_monthly_returns_for_n_years("VTI", 10)
# market_return = df.mean()
# marker_risk = df.std()

# On 2-25-2025 obtained data from ycharts manually as yahoo is now a paid site.
# The data is monthly (not annualized)


#get all permutations of only highest return weights 
def get_highest_ret_weights():
    all_weights = [[0.2 , 0.2 , 0.2 , 0.1 , 0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
                    [0.2 , 0.2 , 0.15, 0.15, 0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
                    [0.2 , 0.2 , 0.15, 0.1 , 0.1 , 0.05, 0.05, 0.05, 0.05, 0.05],
                    [0.2 , 0.2 , 0.1 , 0.1 , 0.1 , 0.1 , 0.05, 0.05, 0.05, 0.05],
                    [0.2 , 0.15, 0.15, 0.15, 0.1 , 0.05, 0.05, 0.05, 0.05, 0.05],
                    [0.2 , 0.15, 0.15, 0.1 , 0.1 , 0.1 , 0.05, 0.05, 0.05, 0.05],
                    [0.2 , 0.15, 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.05, 0.05, 0.05],
                    [0.2 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.05, 0.05],
                    [0.15, 0.15, 0.15, 0.15, 0.15, 0.05, 0.05, 0.05, 0.05, 0.05],
                    [0.15, 0.15, 0.15, 0.15, 0.1 , 0.1 , 0.05, 0.05, 0.05, 0.05],
                    [0.15, 0.15, 0.15, 0.1 , 0.1 , 0.1 , 0.1 , 0.05, 0.05, 0.05],
                    [0.15, 0.15, 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.05, 0.05],
                    [0.15, 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.05],
                    [0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 , 0.1 ]]
    return all_weights

# go through all all_weights for a given portfolio
# if the returns are better for any risk band in high_returns then store it
# in high_returns for that risk band
def selectBestPortfolios(all_weights, high_returns, portfolio, returns):
    global foundCounter
    
    sortedreturns = returns.mean().sort_values()
    cov_matrix = returns.cov()
    
    for w in all_weights:
        w = np.array(w)
        portfolio_return = w.T.dot(sortedreturns)*12 # Annualize from monthly data
        portfolio_risk = np.sqrt(w.T.dot(cov_matrix).dot(w))*12**0.5 # Annualize 
        
        if(portfolio_risk > riskbands[-1] or portfolio_risk < riskbands[0]):
            continue #skip portfolios is the risk is our of band.
        
        #find out the riskband we fit in
        for i in range(len(riskbands)-1):
            if (portfolio_risk >= riskbands[i] and portfolio_risk < riskbands[i+1]): 
                if len(high_returns[i][1]) > 0:
                    if portfolio_return < high_returns[i][1][-1][0]:
                       continue # bail out if portfolio_return is below lowest return we have
                    
                high_returns[i][1].append([portfolio_return, portfolio_risk, portfolio, w])
                high_returns[i][1].sort(reverse=True)
                foundCounter = foundCounter + 1
                if(len(high_returns[i][1]) > 10):
                    high_returns[i][1].pop() #don't let returns go above 10
                break

"""
This method uses matrix multiplation is a 8x or more faster than above.
"""    
def selectBestPortfolios2(all_weights, high_returns, portfolio, returns, market_return):
    global foundCounter
    # Get the mean returns and sort them
    mean_returns = returns.mean()
    sortedreturns = mean_returns.sort_values()
    
    # Get the sorted indices to reorder the covariance matrix
    sorted_indices = sortedreturns.index
    
    # Reorder the covariance matrix according to the sorted returns
    cov_matrix = returns.cov()
    cov_matrix_sorted = cov_matrix.loc[sorted_indices, sorted_indices]
    
    # Convert to numpy arrays for efficient computation
    sortedreturns_np = sortedreturns.values
    cov_matrix_np = cov_matrix_sorted.values
    
    # Make sure all_weights is a proper 2D numpy array
    all_weights_np = np.array(all_weights)
    
    # Calculate returns for all portfolios
    portfolio_returns = all_weights_np @ sortedreturns_np*12 # Annualize
    
    # Calculate risks for all portfolios
    temp = all_weights_np @ cov_matrix_np
    portfolio_risks = np.sqrt(np.sum(temp * all_weights_np, axis=1))*12**0.5 # Annualize 
    
    # Sort everything by returns in descending order
    sort_indices = np.argsort(-portfolio_returns)  # Negative for descending order
    portfolio_returns = portfolio_returns[sort_indices]
    portfolio_risks = portfolio_risks[sort_indices]
    all_weights_np = all_weights_np[sort_indices]
    
    for i, (w, portfolio_return, portfolio_risk) in enumerate(zip(all_weights_np, portfolio_returns, portfolio_risks)):
        # Early termination if return falls below market return
        if portfolio_return < market_return:
            break

        if(portfolio_risk > riskbands[-1] or portfolio_risk < riskbands[0]):
            continue
        
        for j in range(len(riskbands)-1):
            if (portfolio_risk >= riskbands[j] and portfolio_risk < riskbands[j+1]): 
                if len(high_returns[j][1]) > 0:
                    if portfolio_return < high_returns[j][1][-1][0]:
                       continue # bail out if portfolio_return is below lowest return we have
                    
                high_returns[j][1].append([portfolio_return, portfolio_risk, portfolio, w])
                high_returns[j][1].sort(reverse=True)
                foundCounter = foundCounter + 1
                if(len(high_returns[j][1]) > 10):
                    high_returns[j][1].pop() #don't let returns go above 10
                break

def selectPortfolio(all_weights, high_returns, low_risks, portfolio, returns):
    market_return = 0.010835074626865672 #VTI mean
    market_risk = 0.043753288611030186 #VTI SD
    lowest_return = market_return
    highest_risk = market_risk*1.25

    sortedreturns = returns.mean().sort_values()
    cov_matrix = returns.cov()
    
    for w in all_weights:
        w = np.array(w)
        portfolio_return = w.T.dot(sortedreturns)*12 # Annualize from monthly data
        portfolio_risk = np.sqrt(w.T.dot(cov_matrix).dot(w))*12**0.5 # Annualize 
        
        if(portfolio_return > lowest_return and portfolio_risk < market_risk):
            #Add to high_returns
            high_returns.append([portfolio_return, portfolio])
            high_returns.sort(reverse=True)
            if(len(high_returns) > 10):
                high_returns.pop()
            #break #as highest return for a portfolio is the first one.
            
        if(portfolio_risk < highest_risk and portfolio_return > market_return):
            #Add to low_risks
            low_risks.append([portfolio_risk, portfolio])
            low_risks.sort()
            if(len(low_risks) > 10):
                low_risks.pop()
 
def get_size(iterator):
  """Returns the size of the iterator.

  Args:
    iterator: An iterator.

  Returns:
    The size of the iterator.
  """
  try:
    return sum(1 for _ in iterator)
  except StopIteration:
    return 0

#for selected ETFs find top 100 market return portfolios with risks between
# 25%+- or market risk (VTI)
def top100(dfret, selected, results_file, skip=0):
    global foundCounter, oldFoundCounter
    
    all_weights = get_highest_ret_weights()

    if skip > 0:
        high_returns = readtop100()
    else:
        high_returns = []
        #initailize the final resultset to capture returns
        for risk in riskbands:
            high_returns.append([risk,[]])
        
    #Make all combinations of portfolios 
    total_comb = (math.factorial(selected.size) /
    (math.factorial(selected.size - portfolio_size) *
     math.factorial(portfolio_size)))
    
    print ("Total portfolio combinations: ", "{:,}".format(total_comb))
    comb = combinations(selected, portfolio_size)

    market_return = dfret.VTI.mean()*12
    
    cnt = 0
    for portfolio in comb:   
        if cnt < skip:
            cnt+=1
            continue
        
        returns=dfret[np.array(portfolio)]           
        selectBestPortfolios2(all_weights, high_returns, portfolio, returns, market_return)      
        cnt+=1  
        
        if(cnt%1000 == 0): 
            print(datetime.now(), cnt, portfolio, "found=",foundCounter, foundCounter-oldFoundCounter)
            oldFoundCounter = foundCounter
            with open(results_file,'wb') as fileObject:
                pickle.dump(high_returns,fileObject)
    # capture the last recs.
    with open(results_file,'wb') as fileObject:
        pickle.dump(high_returns,fileObject) 

def readtop100(results_file):
    with open(results_file, 'rb') as fileObject:
        high_returns = pickle.load(fileObject)
        
        for rows in high_returns:
            if(len(rows[1]) > 0):
                for row in rows[1]:
                    print(row[0], row[1], row[2])
                
    return high_returns  

def create_top100DB():
    results_file = 'top100-2025-02-25.pkl'
    df = pd.read_csv('monthly/data-2025.csv')
    skip = 0

    sortedreturns = df.mean(numeric_only=True).sort_values(ascending=False)
    selected = sortedreturns.index
    top100(df, selected, results_file, skip)

# readtop100(results_file)

create_top100DB()