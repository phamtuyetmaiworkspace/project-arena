# Project Arena

A futuristic Streamlit app for project pitching and simulated investment across 3 classes/servers.

## Core rules in this MVP
- 3 independent servers/classes (A, B, C).
- Each student starts with VND 100,000,000.
- Four categories: Communication, Business, Public, Social.
- Pitching is category-by-category.
- Teacher opens investment only after all projects in the current category finish pitching.
- Students cannot invest in projects from their own category, including their own project.
- Maximum VND 25,000,000 per project.
- Results: most-funded project in each category + Top 5 Investors by Investment Quality.
- Student investment identities are never shown to project teams.

## Persistent storage
Uses Supabase/Postgres. Data persists across app restarts and across the 2-day pitching period.

## Setup
1. Create a Supabase project.
2. Run `supabase_schema.sql` in the Supabase SQL editor.
3. Create `.streamlit/secrets.toml` locally or Streamlit Cloud secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_KEY"
TEACHER_PASSWORD = "change-me"
```

4. Install and run:

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Student import
CSV columns:
- server_id
- student_id
- student_name
- login_code (optional for initial setup)

`sample_students.csv` is included.

## Recommended next hardening step
Before real classroom use, enable RLS and separate public/student access from teacher/admin operations.


## Production classes
This build uses class IDs directly instead of A/B/C:
- E.032.03_1 — 51 students
- E.032.03_2 — 53 students
- E.032.03_3 — 49 students

Run `supabase_schema.sql`, then `seed_students_3_classes.sql`. Student username = student ID; login code = DOB in DDMMYYYY.
