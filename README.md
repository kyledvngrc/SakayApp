# SakayApp

A jeepney trip planner for Davao City. Commuters set where they are (GPS, dropped pin or search) and where they want to go. The app tells them which jeepney routes to ride, where to transfer and the approximate fare, with student, senior and PWD discounts.

Built for **UN SDG 11, Target 11.2** (safe, affordable, accessible transport). This is a programming languages capstone that uses four paradigms:

| Paradigm | Where |
|---|---|
| Logic | `prolog/routes.pl`: route search over `leg/3` facts |
| Functional | `backend/app/geo.py`, `fare_calc.py`, `ranking.py`: pure functions |
| Object-Oriented | `backend/app/models.py`, `fares.py`: `Trip`, `TripPlanner`, `FareStrategy` subclasses |
| Imperative | `backend/app/main.py`, `db.py`, `prolog_bridge.py`: startup loading, request handling |

## Architecture
```
iOS app (Expo / React Native) ─┐
Admin web page (Leaflet) ──────┴─> FastAPI ──> PostgreSQL 16
                                      └─ pyswip ─> SWI-Prolog
```

## Repository layout
```
database/   schema.sql, seed.sql (SAMPLE DATA ONLY)
prolog/     routes.pl
backend/    FastAPI app and tests
mobile/     Expo iOS app
docs/       tech justification, paradigms, data sources
```

## Getting started

### Prerequisites
- Docker Desktop (for PostgreSQL)
- SWI-Prolog: `brew install swi-prolog` (macOS)
- Python 3.12, Node 22
- Expo Go on an iPhone, or Xcode for the iOS Simulator

### Database
```bash
cp .env.example .env        # then edit passwords
docker compose up -d
docker compose exec db psql -U sakay -d sakay -c "SELECT * FROM v_legs;"
```

### Prolog route finder (standalone tests)
```bash
swipl -g run_tests -t halt prolog/tests/test_routes.pl
```

### Back-end
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Mobile
```bash
cd mobile
npm install
npx expo start
```

## Data
All seed data is **placeholder only**. Real routes are entered through the admin page, and each record notes its data source and collection date. Fares come from the official LTFRB fare matrix (citation in `docs/tech-justification.md`).

## Contributing
`main` must always work. Make one branch per feature (`feature/<name>`) and merge by pull request with at least one reviewer. Never commit `.env`.
