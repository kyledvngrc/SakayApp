# SakayApp

A jeepney trip planner for Davao City. Commuters set where they are (GPS, dropped pin or search) and where they want to go. The app tells them which jeepney routes to ride, where to transfer and the approximate fare, with student, senior and PWD discounts.

Built for **UN SDG 11, Target 11.2** (safe, affordable, accessible transport). This is a programming languages capstone that uses four paradigms:

| Paradigm | Where |
|---|---|
| Logic | `prolog/routes.pl`: trip search over `route/3` and `link/5` facts (where routes connect) |
| Functional | `backend/app/geo.py`, `connections.py`, `directions.py`, `fare_calc.py`, `ranking.py`: pure functions (map/filter/reduce, immutable data) |
| Object-Oriented | `backend/app/models.py`, `fares.py`: `Route`, `Network`, `Segment` → `WalkSegment`/`RideSegment`, `Trip`, `TripPlanner`, `FareStrategy` → `RegularFare` → `DiscountedFare` |
| Imperative | `backend/app/main.py`, `services.py`, `db.py`, `prolog_bridge.py`, `routers/`: startup loading, request handling |

## Architecture
```
iOS app (Expo / React Native) ─┐
Admin web page (Leaflet) ──────┴─> FastAPI ──> PostgreSQL 16
                                      └─ pyswip ─> SWI-Prolog
```

## Repository layout
```
database/   schema.sql, seed.sql (empty), migrations/
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
docker compose exec db psql -U sakay -d sakay -c "\dt"
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
uvicorn app.main:app --reload      # API docs at http://localhost:8000/docs
python3 -m pytest                 # uses a separate sakay_test database; your data is never touched
```

### Admin page (route and fare entry)
```bash
cd backend
python3 -m app.create_admin you@example.com   # asks for a password (10+ characters)
uvicorn app.main:app --reload
```
Open http://localhost:8000/admin and sign in. To add a route:
1. **Routes → + New route**: enter a code (letters, digits, `_`, `-`, e.g. the signboard name) and a name written "Start – End" in the direction you will draw.
2. **Draw / edit line**: click along the streets in the order the jeepney drives, from S to E. Click on the line to insert a point; right-click a point to delete it. For a one-way loop, finish back at the start.
3. **Save route**: the planner reloads and finds transfer points (purple dots) where routes cross or pass within 200 m of each other.
4. Optionally add **Landmarks** (malls, schools, terminals) so directions can say "get off near SM Ecoland".
5. Check the result in **Test trip** by clicking a start and a destination on the map.

Enter the official LTFRB fare values with their citation under **Fares**. Until a non-placeholder rule exists, the app shows fares as unavailable.

### Mobile (iPhone with Expo Go)
```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000   # reachable from the phone
cd mobile && npm install && npx expo start                       # scan the QR code with the iPhone
```
See `mobile/README.md`. The phone must be on the same Wi-Fi as the computer.

## How trips are planned
Jeepneys pick up and drop off anywhere, so there are no fixed stops. Each route is the line it drives along.
1. Find where each route passes within 500 m of the origin and of the destination (one point per pass).
2. From the lines, find **transfer points**: where two routes cross, or come within a 200 m walk.
3. Prolog searches route sequences (at most 2 transfers), respecting one-way routes and loops, and keeps the cheapest plan per sequence.
4. Python builds the trips (walk → ride → (walk) → ride → walk), computes fares by distance ridden, and ranks them: fewest transfers, then fare, then walking, then distance.

Directions use distance and landmarks, not times: waiting and travel times vary too much.

### Upgrading an existing database
Databases created before the line-based planner need migration 002 (back up first):
```bash
docker compose exec -T db pg_dump -U sakay -d sakay > backups/before-002.sql
docker compose exec -T db psql -U sakay -d sakay < database/migrations/002_line_routing.sql
```

## Data
The database starts empty (`seed.sql` has no data). Real routes are entered through the admin page, and each record notes its data source and collection date. Fares come from the official LTFRB fare matrix (citation in `docs/tech-justification.md`).

## Contributing
`main` must always work. Make one branch per feature (`feature/<name>`) and merge by pull request with at least one reviewer. Never commit `.env`.
