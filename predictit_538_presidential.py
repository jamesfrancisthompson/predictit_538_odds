# TO DO
# 1. Fix poll numbers from same survey but different question, ie Delaware
# 2. Clean up workarounds
# 3. Fair probability

# Import modules
import json
import requests
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
pd.set_option('display.max_rows', None) #print all rows without truncating
import numpy as np
import datetime
import os

# Pull in market data from PredictIt's API
Predictit_URL = "https://www.predictit.org/api/marketdata/all/"
Predictit_response = requests.get(Predictit_URL)
jsondata = Predictit_response.json()

# Replace null values with zero
def dict_clean(items):
    result = {}
    for key, value in items:
        if value is None:
            value = 0
        result[key] = value
    return result
dict_str = json.dumps(jsondata)
jsondata = json.loads(dict_str, object_pairs_hook=dict_clean)

# Market data by contract/price in dataframe
data = []
for p in jsondata['markets']:
    for k in p['contracts']:
        data.append([p['id'],p['name'],k['id'],k['name'],k['bestBuyYesCost'],k['bestBuyNoCost'],k['bestSellYesCost'],k['bestSellNoCost']])

# Pandas dataframe named 'predictit_df'
predictit_df = pd.DataFrame(data)

# Update dataframe column names
predictit_df.columns=['Market_ID','Market_Name','Contract_ID','Contract_Name','PredictIt_Yes','bestBuyNoCost','BestSellYesCost','BestSellNoCost']

# Filter PredicitIt dataframe to presidential state markets/contracts
predictit_df = predictit_df[predictit_df['Market_Name'].str.contains("Which party will win") & predictit_df['Market_Name'].str.contains("2020 presidential election?")]

# Fix annoying typo (double space) in congressional district market names
predictit_df['Market_Name'] = predictit_df['Market_Name'].str.replace('in the  2020','in the 2020')

# Split Market_Name column into state name column
start_string = "Which party will win"
end_string = "in the 2020 presidential election?"
predictit_df['a'], predictit_df['state'] = predictit_df['Market_Name'].str.split(start_string, 1).str
predictit_df['state'], predictit_df['b'] = predictit_df['state'].str.split(end_string, 1).str
del predictit_df['a']
del predictit_df['b']

# Create answer column from contract names
predictit_df['answer'] = predictit_df['Contract_Name'].str.replace('Republican','Trump').str.replace('Democratic','Biden')

# Strip trailing/leading whitespaces in answer and state columns
predictit_df['state'] = predictit_df['state'].str.strip()
predictit_df['answer'] = predictit_df['answer'].str.strip()

# Pull in polling data from 538
pres_polling = pd.read_csv('https://projects.fivethirtyeight.com/polls-page/president_polls.csv')
pres_polling = pres_polling.dropna(subset=['state'])

# Drop extraneous columns
pres_polling = pres_polling.drop(['pollster_id', 'pollster','sponsor_ids','sponsors','display_name', 'pollster_rating_id', 'pollster_rating_name', 'fte_grade', 'sample_size', 'population', 'population_full', 'methodology', 'seat_number', 'seat_name', 'start_date', 'end_date', 'sponsor_candidate', 'internal', 'partisan', 'tracking', 'nationwide_batch', 'ranked_choice_reallocated', 'notes', 'url'], axis=1)

# Standardize congressional district names in 538 with PredictIt
pres_polling['state'] = pres_polling['state'].str.replace('Maine CD-1','ME-01')
pres_polling['state'] = pres_polling['state'].str.replace('Maine CD-2','ME-02')
pres_polling['state'] = pres_polling['state'].str.replace('Nebraska CD-2','NE-02')

# Filter to most recent poll for Biden & Trump
pres_polling['created_at'] = pd.to_datetime(pres_polling['created_at']) #convert 'created_at' to datetime
recent_pres_polling = pres_polling.sort_values(by=['created_at']).drop_duplicates(['state', 'candidate_name'], keep='last')
recent_pres_polling = recent_pres_polling[recent_pres_polling['answer'].isin(['Biden', 'Trump'])]

# Pull in polling data from 538 polling averages
pres_poll_avg = pd.read_csv('https://projects.fivethirtyeight.com/2020-general-data/presidential_poll_averages_2020.csv')

# Drop extraneous columns
pres_poll_avg = pres_poll_avg.drop(['cycle'], axis=1)

# Standardize congressional district names in 538 polling averages with PredictIt
pres_poll_avg['state'] = pres_poll_avg['state'].str.replace('Maine CD-1','ME-01')
pres_poll_avg['state'] = pres_poll_avg['state'].str.replace('Maine CD-2','ME-02')
pres_poll_avg['state'] = pres_poll_avg['state'].str.replace('Nebraska CD-2','NE-02')

# Split candidate_name column into 'answer' column
pres_poll_avg['candidate_name'] = pres_poll_avg['candidate_name'].str.replace('Donald', 'Joseph R.') #ugly workaround
start_string = "Joseph R. "
end_string = " Jr."
pres_poll_avg['a'], pres_poll_avg['answer'] = pres_poll_avg['candidate_name'].str.split("Joseph R. ", 1).str
pres_poll_avg['answer'], pres_poll_avg['b'] = pres_poll_avg['answer'].str.split(end_string, 1).str
del pres_poll_avg['a']
del pres_poll_avg['b']

# Strip trailing/leading whitespaces in answer column
pres_poll_avg['answer'] = pres_poll_avg['answer'].str.strip()

# Filter to most recent poll for Biden & Trump
pres_poll_avg['modeldate'] = pd.to_datetime(pres_poll_avg['modeldate']) #convert 'modeldate' to datetime
pres_poll_avg = pres_poll_avg.sort_values(by=['modeldate']).drop_duplicates(['state', 'candidate_name'], keep='last')
pres_poll_avg = pres_poll_avg[pres_poll_avg['answer'].isin(['Biden', 'Trump'])]

# Rename 538 'pct' column to '538_latest_poll'
recent_pres_polling = recent_pres_polling.rename({'pct': '538_latest_poll'}, axis=1)

# Round pct_estimate and pct_trend_adjusted to 2 decimal places
pres_poll_avg['pct_estimate'] = pres_poll_avg['pct_estimate'].round(2)
pres_poll_avg['pct_trend_adjusted'] = pres_poll_avg['pct_trend_adjusted'].round(2)

# Merge 538 poll and 538 poll averages dataframes together
recent_pres_polling = pd.merge(recent_pres_polling, pres_poll_avg, on=['state', 'answer'], how='left')

# Pull in odds
odds_df = pd.read_csv('https://raw.githubusercontent.com/mauricebransfield/predictit_538_odds/master/odds_state_presidential.csv', index_col=[0]) # error_bad_lines=False,

# Replace hyphen in state names with space
odds_df['state'] = odds_df['state'].str.replace('-',' ') 

# Standardize Washington DC & Washington State
odds_df['state'] = odds_df['state'].str.replace('Washington Dc','DC')
odds_df['state'] = odds_df['state'].str.replace('Washington State','Washington')

# Replace party with candidate names
odds_df['answer'] = odds_df['answer'].str.replace('Republicans','Trump')
odds_df['answer'] = odds_df['answer'].str.replace('Democratic','Biden')
odds_df['answer'] = odds_df['answer'].str.replace('Democrats','Biden')
odds_df['answer'] = odds_df['answer'].str.replace('Democrat','Biden')

# Drop columns with all nan values
odds_df = odds_df.dropna(axis=1, how='all')

# Convert odds_df column headers to list
odds_df_columns = list(odds_df.columns.values)
odds_df_columns.remove('answer')
odds_df_columns.remove('state')
odds_df_loop = odds_df.copy()
del odds_df_loop['answer']
del odds_df_loop['state']

# denominator / (denominator + numerator) = implied probability
# Loop through odds columns to convert fractional odds to new column of implied probability
for i in odds_df_columns:
	odds_df_loop['numerator'], odds_df_loop['denominator'] = odds_df_loop[i].str.split('/', 1).str
	odds_df_loop['denominator'] = pd.to_numeric(odds_df_loop['denominator'], errors='coerce').fillna(0).astype(np.int64)
	odds_df_loop['denominator'] = odds_df_loop['denominator'].mask(odds_df_loop['denominator']==0).fillna(1) # workaround
	odds_df_loop['numerator'] = pd.to_numeric(odds_df_loop['numerator'], errors='coerce').fillna(0).astype(np.int64)
	odds_df_loop[str(i) + '_imp_prob'] = (odds_df_loop['denominator'] / (odds_df_loop['denominator'] + odds_df_loop['numerator'])).round(2)

# Concatenate imp_prob columns with 'answer' and 'state' columns
asdf = [odds_df['answer'], odds_df['state']]
headers = ["answer", "state"]
as_df = pd.concat(asdf, axis=1, keys=headers)
odds_imp_prob_df = pd.concat([odds_df_loop, as_df], axis=1)

# Merge PredictIt and odds dataframes together
df = pd.merge(predictit_df, odds_imp_prob_df, on=['state', 'answer'], how='left')

# Merge 538 polls into new dataframe
df = pd.merge(df, recent_pres_polling, on=['state', 'answer'], how='left')

# workaround to fix previous workaround
for i in odds_df_columns:
	mask = df[i].isnull()
	column_name = str(i) + '_imp_prob'
	df.loc[mask, column_name] = np.nan

# Find average of all implied probabilities
m = df.loc[:, df.columns.str.contains('_imp_prob')]
odds_df_columns2 = list(m.columns.values)
df['ari_mean_imp_prob'] = df[odds_df_columns2].mean(1).round(2)

# Sort alphabetically by state and answer
df = df.sort_values(["state", "answer"])

# Create column matching Trump Yes cost with Biden No cost, and vice versa
trump = (df['answer']=='Trump')
df.loc[trump,'PredictIt_Oppo_No'] = df.loc[df['answer'] == 'Biden','bestBuyNoCost'].values
biden = (df['answer']=='Biden')
df.loc[biden,'PredictIt_Oppo_No'] = df.loc[df['answer'] == 'Trump','bestBuyNoCost'].values

# Create column of difference in betfair & PredictIt
df['ari_mean_imp_prob-PredicitIt_Yes'] = (df['ari_mean_imp_prob']-df['PredictIt_Yes']).round(2)

# Print out select columns
print(df[['state', 
			'answer', 
			'538_latest_poll', 
			'pct_estimate',
			'pct_trend_adjusted',
			'PredictIt_Yes',
			'PredictIt_Oppo_No',
			'betfair',
			'betfair_imp_prob',
			'WilliamHill',
			'WilliamHill_imp_prob',
			#'skybet_imp_prob',
			#'ladbrokes_imp_prob',
			#'888sport_imp_prob',
			#'paddypower_imp_prob',
			#'unibet_imp_prob',
			#'coral_imp_prob',
			#'betfred_imp_prob',
			#'betway_imp_prob',
			#'sportingbet_imp_prob',
			#'betfairexchange_imp_prob',
			#'smarkets_imp_prob',
			'ari_mean_imp_prob',
			'ari_mean_imp_prob-PredicitIt_Yes']])

# Write dataframe to CSV file in working directory
df.to_csv(r'C:/Users/Mick/Documents/Python/Python/predictit_538_odds/predictit_538_odds.csv', sep=',', encoding='utf-8', header='true')

# Write dataframe with timestamp to archive folder
snapshotdate = datetime.datetime.today().strftime('%Y-%m-%d')
os.chdir('C:/Users/Mick/Documents/Python/Python/predictit_538_odds/Archive')
df.to_csv(open(snapshotdate+'.csv','w'))
