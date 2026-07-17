# curricula.live API

Minimal FastAPI starter for the curricula.live API.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run locally

```bash
uvicorn app.main:app --reload
```

## Test

```bash
pytest
```

## Pull request previews

The FastAPI entry point is configured for Vercel in `pyproject.toml`.

After importing the `curricula-live/api` GitHub repository into Vercel, every pull request and non-production branch receives its own Preview Deployment URL. The `main` branch remains the production branch.

GitHub Actions also runs the Python test suite for every pull request and every push to `main`.
