# MetalSense — Recreated Local Project

This project recreates the MetalSense scaffold and the recovered Emergent implementation changes supplied in the conversation.

## Stack

- Frontend: Expo SDK 54, React Native, Expo Router, TypeScript
- Backend: FastAPI, Motor, MongoDB, Pandas
- Authentication: PBKDF2-SHA256 password hashing + bearer sessions
- Data flow: CSV/XLS/XLSX → validation → reverse geocoding → deterministic HPI/HEI/Cd → MongoDB

## Run backend

```bash
cd backend
cp .env.example .env
# Install MongoDB separately, then:
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

## Run frontend

```bash
cd frontend
cp .env.example .env
npm install
npx expo start
```

For Expo web on the same machine, `EXPO_BACKEND_URL=http://localhost:8000` is sufficient. For a physical phone, use the host machine's LAN address instead of `localhost`.

## Important recovered changes

- `EXPO_BACKEND_URL` is now the preferred frontend environment key, with `EXPO_PUBLIC_BACKEND_URL` retained as a compatibility fallback.
- Dataset imports support CSV, XLSX and XLS.
- Authentication, dataset persistence, deletion, validation and deterministic indices are wired to the backend.
- Reverse geocoding is moved off the async event loop with `asyncio.to_thread(...)`.
- Accessibility/automation `testID` values were added to fields, account choices, navigation, upload actions, validation controls, deletion and sign-out.
- `app.json` uses the MetalSense branding and light UI configuration.
