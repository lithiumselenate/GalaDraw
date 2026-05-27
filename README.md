# GalaDraw

A small monolithic gala lottery app.

It includes:

- Employee management
- CSV employee import
- Prize level configuration
- Server-side winner drawing
- Winner result export
- SQLite by default
- Docker-friendly deployment

## Local Development

Prerequisites:

- Python 3.10+
- pip

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
python app.py
```

Open:

```text
http://localhost:8000
```

## CSV Import Format

Use UTF-8 CSV with these headers:

```csv
employee_no,name,department
001,Alice,Engineering
002,Bob,Sales
```

## Docker

Build and run:

```powershell
docker compose up --build
```

Then open:

```text
http://localhost:8000
```

## Notes

The first version uses a simple event rule: one employee can win at most once across the whole event.

For production, set a strong `SECRET_KEY` and back up `instance/gala_draw.db`.
