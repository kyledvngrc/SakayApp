# SakayApp mobile (Expo, iOS first)

The commuter app: a full-screen map with a bottom sheet. Set where you are
(GPS, a pin, or a saved place) and where you're going, and see which jeepneys
to ride, where to transfer, and the fare.

## Run it on your iPhone
1. Start the back-end so the phone can reach it (from `backend/`):
   `uvicorn app.main:app --host 0.0.0.0 --port 8000`
2. Start the app (from `mobile/`): `npm install` (first time), then `npx expo start`
3. Scan the QR code with the iPhone camera; it opens in **Expo Go**
   (install it from the App Store). The phone and computer must be on the same Wi-Fi.

The app talks to `http://<the computer running Expo>:8000`. To use another
server, set `EXPO_PUBLIC_API_URL`, e.g. `EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 npx expo start`.

## Layout
- `src/app/` screens (Expo Router): `index.tsx` is the map and sheet
- `src/components/` sheet, map, trip card, directions, badges
- `src/lib/` API client, types, formatting and geometry helpers
- `src/hooks/` GPS location, remembered rider type

## Live trip
Plan → Start (directions) → **Go** follows you with GPS: "Get off in 400 m",
then "Get off soon, say para" (vibrates, and speaks if sound is on) and
"Get off here". Keep the app open: Expo Go has no background location, so the
screen stays on during a live trip. Alerts with the screen locked need a
development build (`eas build --profile development`).

Checks: `npx tsc --noEmit`, `npx expo lint`, and `npm test` (live tracking logic).
