# Technologies and Justification

For each technology: what it does in SakayApp, why it was chosen, and alternatives considered.

| Technology | Role | Paradigm shown | Why chosen | Alternatives considered |
|---|---|---|---|---|
| SWI-Prolog | Trip search over `route/3` and `link/5` facts | Logic | _TODO_ | _TODO_ |
| Python 3.12 | Back-end language | Imperative, Functional, OOP | _TODO_ | _TODO_ |
| FastAPI | REST API | Imperative | _TODO_ | Flask, Django, Express |
| pyswip | Python to Prolog bridge | — | _TODO_ | _TODO_ |
| PostgreSQL 16 | Database | — | _TODO_ | SQLite, MySQL |
| Docker Compose | Local database setup | — | _TODO_ | Native install |
| React Native + Expo (TypeScript) | iOS app (Android later) | Functional (React components), OOP | _TODO_ | SwiftUI, Flutter |
| react-native-maps | Map on iOS (Apple Maps) | — | _TODO_ | MapLibre |
| Leaflet + OpenStreetMap | Admin route-entry map | — | _TODO_ | Google Maps |
| GitHub | Version control, PR review | — | _TODO_ | GitLab |

## Data and limitations
- Area covered and data collection dates: _TODO_
- Fare source (LTFRB fare matrix citation): _TODO_
- Limits: the app only knows the routes that have been entered; times are estimates.
