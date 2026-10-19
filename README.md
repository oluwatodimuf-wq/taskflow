# Taskflow

A little structure. A lot more focus.

Create, edit, delete, search and filter tasks. Track priorities, due dates and completion progress.

## Stack

- Frontend: responsive HTML, CSS and vanilla JavaScript, DOM rendering and Fetch API.
- Backend: Python standard-library HTTP server, JSON REST API, validation and error responses.
- Database: SQLite, parameterized SQL, automatic schema creation and durable local storage.

## Run

Install Python 3.10 or later. No pip packages or Node build are needed.

```sh
cd taskflow
python server.py
```

On Windows, use `py server.py` if `python` is unavailable.
Open http://127.0.0.1:8001. Stop with Ctrl+C. The app starts empty; add records through its form. Restarting preserves records in `data.sqlite3`.

Optional environment variables: `PORT` changes the port; `DATABASE_PATH` changes the database file. The database parent folder must exist.

## API

| Method | Path | Result |
| --- | --- | --- |
| GET | /api/config | Field metadata |
| GET | /api/records | All records, newest first |
| POST | /api/records | Create a record (201) |
| PUT | /api/records/:id | Replace a record (200) |
| DELETE | /api/records/:id | Delete a record (200) |

POST and PUT require `Content-Type: application/json` and exactly all listed fields:

- `title`: text
- `status`: select
- `priority`: select
- `due_date`: date

Errors return `{"error":"message"}`. Invalid values return 400, missing IDs 404, duplicate SKUs 409, large bodies 413 and unsupported content types 415. Money accepts up to two decimal places. Summary cards reflect all records; filters affect the table only.

## Tests

From the repository root, run `python -m unittest discover -s tests -v`.

## Scope

A single-user local learning/portfolio project with no authentication or user isolation. It binds to loopback and is intended for local use. Public hosting needs authentication, an appropriate production server and database hosting. GitHub Pages cannot run this Python backend.
