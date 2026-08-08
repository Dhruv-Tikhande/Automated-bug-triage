# Current Work and Next Tasks

## Immediate priorities

- Keep the project documented from the perspective of a new developer or AI agent.
- Ensure the documented startup path matches the current repository structure.
- Clarify the relationship between the FastAPI workflow and the separate gRPC prototype.

## Recommended next implementation tasks

1. Standardize model artifact paths so training and inference both use the same location.
2. Add a lightweight startup validation step in the backend when model files are missing.
3. Optionally remove or integrate the gRPC prototype to reduce confusion.
4. Replace static UI demo data with real persisted history if the project evolves.

## Known blockers

- Trained model files are not committed to the repository and must be generated locally.
- The repo currently mixes two different service styles (FastAPI and gRPC), which can confuse contributors.
