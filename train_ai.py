import pandas as pd
import re

# 1. Load the dataset
df = pd.read_csv('Netbeans.csv', sep=';')

# 2. Keep only the columns we need and rename them to be readable
df = df[['sd', 'pd', 'co']]
df.columns = ['Bug_Description', 'Failing_Module', 'Target_Team']

# Drop any rows with missing data
df = df.dropna()

# 3. Text Cleaning Function for the Neural Network
def clean_text(text):
    text = text.lower() # Convert to lowercase
    text = re.sub(r'[^\w\s]', '', text) # Remove punctuation and symbols
    return text

# Apply the cleaning function to the bug descriptions
df['Cleaned_Text'] = df['Bug_Description'].apply(clean_text)

# Let's see how many teams/components we are predicting
team_counts = df['Target_Team'].value_counts()

print("Dataset ready! Shape:", df.shape)
print("\nTop 5 Teams the AI will learn to assign bugs to:")
print(team_counts.head(5))

# Display the first 3 cleaned records
df.head(3)

import numpy as np
import pickle
import pandas as pd
import re
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.estimators import MaximumLikelihoodEstimator
from pgmpy.inference import VariableElimination

# --- STEP 1 CODE (Included here so the script runs top-to-bottom) ---
print("Loading and cleaning data...")
df = pd.read_csv('Netbeans.csv', sep=';')
df = df[['sd', 'pd', 'co']]
df.columns = ['Bug_Description', 'Failing_Module', 'Target_Team']
df = df.dropna()

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

df['Cleaned_Text'] = df['Bug_Description'].apply(clean_text)

# --- STEP 2 CODE (Updated for latest pgmpy version) ---
print("\n1. Defining Bayesian Network Structure: Failing_Module -> Target_Team")
# Updated to DiscreteBayesianNetwork
bn_model = DiscreteBayesianNetwork([('Failing_Module', 'Target_Team')])

print("2. Training the Bayesian Network...")
bn_model.fit(df[['Failing_Module', 'Target_Team']], estimator=MaximumLikelihoodEstimator)

print("3. Building the Inference Engine...")
inference = VariableElimination(bn_model)

unique_modules = df['Failing_Module'].unique()
unique_teams = sorted(df['Target_Team'].unique())
num_teams = len(unique_teams)

bn_probability_lookup = {}

print("4. Calculating Probability Vectors for Neural Network Fusion...")
for module in unique_modules:
    try:
        q = inference.query(variables=['Target_Team'], evidence={'Failing_Module': module})
        states = q.state_names['Target_Team']
        probs = q.values
        
        prob_vector = np.zeros(num_teams)
        for state, prob in zip(states, probs):
            idx = unique_teams.index(state)
            prob_vector[idx] = prob
            
        bn_probability_lookup[module] = prob_vector
        
    except Exception as e:
        bn_probability_lookup[module] = np.zeros(num_teams)

with open('bn_model_data.pkl', 'wb') as f:
    pickle.dump({'lookup': bn_probability_lookup, 'teams': unique_teams}, f)

print("\n✅ STEP 2 COMPLETED SUCCESSFULLY.")
print(f"Total Unique Teams (Array Size): {num_teams}")
print(f"Example probability vector for 'apisupport' module:\n{bn_probability_lookup['apisupport'][:5]}... (truncated)")