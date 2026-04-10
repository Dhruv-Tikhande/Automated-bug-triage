# Automated Bug Triage & QA Dashboard

Monorepo with:

- `frontend/`: React + Vite + Tailwind + Recharts dashboard UI
- `backend/`: FastAPI mock service for triage predictions

## 🚀 How to Run Locally

### 1. Clone the Repository
`git clone https://github.com/Dhruv-Tikhande/automated-bug-triage.git`
`cd automated-bug-triage`

### 2. Setup the Machine Learning Backend
Open a terminal and navigate to the `backend` folder:
`cd backend`
`pip install -r requirements.txt`

**Train the AI Models (Crucial Step):**
Because model files are large, they are not stored in this repository. You must generate them locally using the provided dataset.
`python train_model.py`
*(This will read `data/netbeans_bugs.csv` and generate the `.h5` and `.pkl` files needed for the API).*

**Start the FastAPI Server:**
`uvicorn main:app --reload`

### 3. Setup the React Frontend
Open a *new* terminal and navigate to the `frontend` folder:
`cd frontend`
`npm install`
`npm start`

The UI will now be running on `localhost:3000` and connected to the AI backend!
