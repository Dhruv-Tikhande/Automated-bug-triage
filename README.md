# Automated Bug Triage & QA Dashboard

A small full-stack prototype for routing bug reports to likely engineering teams using a neural network plus a Bayesian-network feature. The repository combines a React dashboard with a Python inference backend and a separate gRPC prototype.

## What it does

- Accepts a bug description and suspected module in the UI.
- Sends the report to a FastAPI endpoint that predicts:
  - assigned team
  - confidence score
  - flakiness probability
- Uses a trained TensorFlow model together with probabilities derived from the NetBeans-style dataset.

## Tech stack

- Frontend: React, Vite, Tailwind CSS, Recharts
- Backend: FastAPI, Pydantic, TensorFlow/Keras, scikit-learn, pgmpy
- Data: NetBeans-style CSV data in the repo root
- RPC prototype: gRPC + Protocol Buffers

## Local setup

1. Create and activate a Python environment in the backend folder.
2. Install backend dependencies:
   - `pip install -r backend/requirements.txt`
3. Install frontend dependencies:
   - `cd frontend && npm install`
4. Train the model artifacts locally from the repo root:
   - `python train_ai.py`
   - `python train_ann.py`
5. Start the backend:
   - `cd backend && uvicorn main:app --reload`
   - or `python backend/main.py`
6. Start the frontend:
   - `cd frontend && npm run dev`

The default frontend URL is `http://localhost:5173` and the backend API is `http://localhost:8000`.

## Project layout

- [backend/main.py](backend/main.py): FastAPI app, model loading, and prediction endpoint.
- [train_ai.py](train_ai.py): builds the Bayesian-network probability lookup.
- [train_ann.py](train_ann.py): trains the neural network and saves model artifacts.
- [frontend/src/App.jsx](frontend/src/App.jsx): main dashboard UI and API client.
- [proto/triage.proto](proto/triage.proto): gRPC contract for the separate RPC prototype.
- [triage_server.py](triage_server.py) and [triage_client.py](triage_client.py): standalone gRPC example.

## Development notes

- The frontend calls the FastAPI endpoint directly; the gRPC service is not wired into the UI.
- Model files are generated locally and are intentionally ignored by git.
- The current training scripts and backend paths should be normalized before relying on them for repeatable runs.

## Distributed Computing Experiment 11

The final lab experiment is a separate gRPC distributed file store with a metadata coordinator, three storage nodes, two replicas per chunk, Lamport-clock file versions, checksum-verified uploads/downloads, heartbeat-based failure detection, and manual replica repair. It runs independently of the bug-triage web application and the earlier gRPC examples.

Follow the complete Windows PowerShell setup, run, failure, repair, and corruption walkthrough in [EXPERIMENT_11.md](EXPERIMENT_11.md). The service definition is in [proto/dfs.proto](proto/dfs.proto); the generated `dfs_pb2.py` and `dfs_pb2_grpc.py` files are checked in so the lab can start after the documented dependency install.
