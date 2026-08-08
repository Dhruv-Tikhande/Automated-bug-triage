# AI Context

## Project goal

This repository is a lightweight bug-triage prototype that predicts a likely engineering team for a reported bug using a combination of text features and module-based priors.

## Current state

The app is functional as a local prototype:

- The React frontend collects a bug description and module.
- The FastAPI backend loads trained model artifacts and returns a prediction.
- A separate gRPC service exists as an alternative prototype but is not connected to the UI.

## Architecture summary

The system has three main layers:

1. Frontend dashboard: React + Vite UI for entering bug reports and viewing triage results.
2. Inference backend: FastAPI service that loads model artifacts and exposes `/api/predict_bug`.
3. Training pipeline: Python scripts that prepare the dataset, build Bayesian-network probability vectors, and train the neural network.

## Critical files

- [backend/main.py](backend/main.py): API entry point and model loading.
- [train_ann.py](train_ann.py): training pipeline for the neural network.
- [train_ai.py](train_ai.py): training pipeline for the Bayesian network.
- [frontend/src/App.jsx](frontend/src/App.jsx): UI and prediction request logic.
- [proto/triage.proto](proto/triage.proto): gRPC contract definition.

## Business logic

The backend performs the following flow for each prediction:

1. Clean the bug description text.
2. Vectorize the cleaned text using a fitted TF-IDF vectorizer.
3. Retrieve a module-to-team probability vector from the Bayesian-network lookup.
4. Concatenate the text features with the Bayesian-network feature vector.
5. Pass the fused input to the trained TensorFlow model.
6. Return the top predicted team, confidence, and flakiness estimate.

## Module relationships

- The frontend depends on the backend API URL configured by `VITE_API_BASE_URL` or the default localhost address.
- The backend expects model files in [backend/models](backend/models).
- The training scripts read [Netbeans.csv](Netbeans.csv) and save model artifacts into the backend models directory.
- The gRPC server and client are independent from the FastAPI workflow.

## Coding conventions

- Python scripts are straightforward and procedural rather than package-oriented.
- The code favors explicit variables and inline comments over abstraction.
- Frontend code is component-based but currently keeps most logic in the main app file.

## Safe extension points

- Add more prediction fields to the FastAPI response without changing the frontend contract drastically.
- Extend the UI with additional triage metrics or history widgets.
- Add new training features by updating the preprocessing and fusion steps in the training scripts and backend inference logic together.

## Risk areas

- Model artifacts are generated locally and are not part of the repo by default.
- The backend assumes the model files exist in specific paths and will fail if they are missing.
- The training scripts and backend paths are slightly inconsistent and may break when run from different directories.
- The gRPC prototype is not integrated with the main application path.

## Known issues

- The current README contains outdated instructions that refer to a different training command pattern.
- The backend uses a permissive CORS policy, which is acceptable for local development but should be tightened for production.
- The UI currently shows static historical data rather than real backend history.

## Recommended next tasks

1. Normalize the training and runtime paths so the project can be run consistently from any working directory.
2. Add a simple startup check that fails clearly when required model files are missing.
3. Decide whether the gRPC prototype should remain separate or be folded into the main architecture.
4. Replace the static history cards with real data if the project is expanded beyond the demo stage.
