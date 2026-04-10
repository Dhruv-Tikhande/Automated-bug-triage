from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pickle
import numpy as np
import re
from tensorflow.keras.models import load_model

app = FastAPI()

# Allow the React frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Load the AI Models when the server starts
print("Loading AI Models...")
model = load_model('models/bug_triage_ann.h5')

with open('models/nlp_vectorizer.pkl', 'rb') as f:
    vectorizer = pickle.load(f)

with open('models/label_encoder.pkl', 'rb') as f:
    encoder = pickle.load(f)

with open('models/bn_model_data.pkl', 'rb') as f:
    bn_data = pickle.load(f)
    bn_lookup = bn_data['lookup']
    bn_teams_count = len(bn_data['teams'])

print("Models Loaded Successfully!")

# 2. Define the input data format expected from the React UI
class BugReport(BaseModel):
    description: str
    module: str

# Helper function to clean text exactly how we trained it
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

# 3. The actual Prediction Endpoint
@app.post("/api/predict_bug")
async def predict_bug(bug: BugReport):
    # A. Clean and Vectorize the Text
    cleaned = clean_text(bug.description)
    X_text = vectorizer.transform([cleaned]).toarray()

    # B. Get the Bayesian Network Probability Array
    prob_array = bn_lookup.get(bug.module, np.zeros(bn_teams_count))
    X_bn = np.array([prob_array])

    # C. Fuse the features together
    X_final = np.hstack((X_text, X_bn))

    # D. Make the Prediction using the ANN
    prediction = model.predict(X_final)
    
    # E. Find the winning team and confidence score
    predicted_index = int(np.argmax(prediction[0]))
    confidence = float(prediction[0][predicted_index]) * 100
    assigned_team = str(encoder.inverse_transform([predicted_index])[0])

    # Calculate "Flakiness" (If confidence is very low, it's highly likely a flaky/confusing bug)
    flakiness = max(0.0, 100.0 - confidence - 10.0) 

    return {
        "assigned_team": assigned_team,
        "confidence": f"{confidence:.1f}%",
        "flakiness_probability": f"{flakiness:.1f}%"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)