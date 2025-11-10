# Contributing to Cloud Visualizer Pro

Welcome — thank you for considering contributing to Cloud Visualizer Pro. We appreciate every contribution, big or small.

This document explains the preferred workflow, coding standards, and how to run tests locally so your PRs are easy to review and merge.

Getting started
- Fork the repository and create a feature branch from `main` using a descriptive name, e.g. `feat/diagram-node-labels` or `fix/backend-logging`.
- Keep changes small and focused. One change per PR makes review straightforward.

Development workflow
- Create an issue for larger features or any bug you plan to work on and link your PR to the issue.
- Branch naming: `feat/*`, `fix/*`, `chore/*`, `docs/*`, `test/*`.
- Commit messages: use conventional style, e.g. `feat(iac): add bicep parameter generation`.

Local development
- Frontend (Vite):
  ```powershell
  cd frontend
  pnpm install
  pnpm run dev
  ```

- Backend (FastAPI):
  ```powershell
  cd backend
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
  ```

Testing
- Add unit tests for new backend logic using pytest and for frontend components using your preferred test runner.
- Run backend tests:
  ```powershell
  cd backend
  .\.venv\Scripts\Activate.ps1
  pytest -q
  ```

Code style
- Keep TypeScript/React code consistent with project linters and formatters (Prettier / ESLint if configured).
- Keep Python code formatted with Black / ruff where applicable.

Pull requests
- Open a pull request against `main` and include:
  - A short description of the change
  - Screenshots if the change affects UI
  - Any migration or environment changes required
- Link the PR to an issue when possible and add reviewers.

Security disclosures
- If you discover a security issue, please avoid public disclosure and open a private issue or contact the maintainers directly.

Thanks again for helping improve the project — your contributions make it better!
