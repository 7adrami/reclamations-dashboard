# Reclamations Dashboard

Streamlit dashboard for submitting reclamations to a Google Sheet, plus a local
bridge (`sync.py`) that auto-fills each row's transaction details from a local
Postgres database.

## Local (with DB auto-fill)
- Install deps: `pip install -r requirements.txt`
- Run: `streamlit run streamlit_app.py`
- The app auto-starts `sync.py` (windowless, via `pythonw`) whenever the database
  is reachable on this machine (localhost). It polls the sheet and fills the
  transaction details from the DB based on `switch_ref` (or phone / montant /
  date). The bridge never runs on machines that can't reach the DB.
- For always-on, set up a Scheduled Task (on logon) that runs `pythonw sync.py`
  (see `run_sync.bat`).

## Streamlit Community Cloud
- The cloud app only writes to the shared Google Sheet. It cannot reach the local
  DB, so `sync.py` is never started there — **no console windows appear**.
- Set the `[gcp_service_account]` Streamlit secret with your service-account JSON.
- Keep your local `sync.py` running so that reclamations inserted from the cloud
  still get their DB-backed details filled into the shared sheet.

## Moving to another computer / the company database
`sync.py` is the only piece that needs to reach the database, so it must run on
the machine that can reach Postgres (e.g. the company DB server). The dashboard
itself (local or on Streamlit Cloud) is database-agnostic — it only talks to the
shared Google Sheet.

On the new machine:
1. Clone the repo (or copy the folder) and create the venv:
   `python -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
2. Copy `credentials.json` (the Google service-account key) into the folder — it is
   gitignored, so transfer it separately (it's the same key that accesses the sheet).
3. Point at the company DB **without editing committed code**:
   - set environment variables `RECLAMATIONS_DB_HOST`, `RECLAMATIONS_DB_PORT`,
     `RECLAMATIONS_DB_NAME`, `RECLAMATIONS_DB_USER`, `RECLAMATIONS_DB_PASSWORD`, or
   - create a gitignored `local_config.py` with those variables (see `config.py`).
   Never put the DB password in `config.py` (it is committed to git).
4. Make sure the company DB has the expected table/columns
   (`public.RECLAMATIONS` with the columns listed in `config.DB_COLUMNS`); adjust
   `DB_COLUMNS` / `SEARCH_COLUMNS` in `config.py` if the schema differs.
5. Run `streamlit run streamlit_app.py` (auto-starts `sync.py`) or launch
   `sync.py` directly / via the Scheduled Task.

Reuse the same Streamlit Cloud app (it's already linked to this repo and only
needs the `[gcp_service_account]` secret) or create a new app pointing at the same
repo — no DB settings are required in the cloud.
