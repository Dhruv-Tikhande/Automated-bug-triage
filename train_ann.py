import pandas as pd
import numpy as np
import re
import pickle
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout

print("1. Loading Data & Grouping Small Teams (Strategy 1)...")
df = pd.read_csv('Netbeans.csv', sep=';')
df = df[['sd', 'pd', 'co']].dropna()
df.columns = ['Bug_Description', 'Failing_Module', 'Target_Team']

# STRATEGY 1: Reduce Classes. Find teams with fewer than 30 bugs and group them.
team_counts = df['Target_Team'].value_counts()
teams_to_keep = team_counts[team_counts >= 30].index.tolist()

df['Target_Team'] = df['Target_Team'].apply(lambda x: x if x in teams_to_keep else 'Other')
print(f"Reduced from 232 teams down to {len(teams_to_keep) + 1} core teams.")

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text
df['Cleaned_Text'] = df['Bug_Description'].apply(clean_text)

print("Reading Bayesian Network from backend/models/ folder...")
# CHANGED: Read from the backend folder
with open('backend/models/bn_model_data.pkl', 'rb') as f:
    bn_data = pickle.load(f)
bn_lookup = bn_data['lookup']
df['BN_Probabilities'] = df['Failing_Module'].map(lambda x: bn_lookup.get(x, np.zeros(len(bn_data['teams']))))

print("2. Converting Text to Bigrams (Strategy 3)...")
vectorizer = TfidfVectorizer(max_features=2500, ngram_range=(1, 2))
X_text = vectorizer.fit_transform(df['Cleaned_Text']).toarray()

print("3. Fusing Features...")
X_bn = np.stack(df['BN_Probabilities'].values)
X_final = np.hstack((X_text, X_bn))

encoder = LabelEncoder()
y_encoded = encoder.fit_transform(df['Target_Team'])

X_train, X_test, y_train, y_test = train_test_split(X_final, y_encoded, test_size=0.2, random_state=42)

print("4. Building the Upgraded Neural Network...")
model = Sequential([
    Dense(512, activation='relu', input_shape=(X_train.shape[1],)),
    Dropout(0.4), 
    Dense(256, activation='relu'),
    Dropout(0.4),
    Dense(len(encoder.classes_), activation='softmax')
])

model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

print("5. Training the Model...")
history = model.fit(X_train, y_train, epochs=12, batch_size=32, validation_split=0.1)

print("\n6. Evaluating Model on Unseen Data...")
loss, accuracy = model.evaluate(X_test, y_test)
print(f"\n=> NEW FINAL TEST ACCURACY: {accuracy*100:.2f}%")

print("7. Saving Upgraded Models directly to backend/models/...")
# CHANGED: Save directly to the backend folder so the UI gets automatically updated
model.save('backend/models/bug_triage_ann.h5')
with open('backend/models/nlp_vectorizer.pkl', 'wb') as f:
    pickle.dump(vectorizer, f)
with open('backend/models/label_encoder.pkl', 'wb') as f:
    pickle.dump(encoder, f)

print("\n✅ UPGRADE COMPLETED SUCCESSFULLY.")