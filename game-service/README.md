# Immortal MMO Game Service

FastAPI backend service for the Immortal Minecraft MMORPG.

## Local Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Run Tests

```bash
.venv/bin/python -m pytest
```

## Lint

```bash
.venv/bin/python -m ruff check .
```

## Run Service

```bash
.venv/bin/python -m uvicorn immortal_mmo.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

