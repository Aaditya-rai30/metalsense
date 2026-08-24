# MetalSense

MetalSense is an Expo/React Native application backed by FastAPI and MongoDB.

## Stack

- Frontend: Expo SDK 54, React Native, Expo Router, TypeScript
- Backend: FastAPI, Motor, MongoDB, Pandas
- Authentication: PBKDF2-SHA256 password hashing + bearer sessions
- Data flow: CSV/XLS/XLSX → validation → reverse geocoding → deterministic HPI/HEI/Cd → MongoDB

## Prerequisites

- Node.js 20 or newer
- Python 3.11 or newer
- A running local MongoDB server or a MongoDB Atlas connection string

## 1. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Before starting the server, set `MONGO_URL` in `backend/.env`. The example
already works with MongoDB running locally on its default port. For Atlas,
replace it with the connection string supplied by Atlas. Keep `DB_NAME` as
`metalsense` unless you intentionally want another database.

The API is ready when <http://localhost:8000/api/> returns a response with
`"status": "running"`.

On Windows PowerShell, activate the virtual environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## 2. Start the Expo frontend

Open a second terminal from the repository root:

```bash
cd frontend
cp .env.example .env
npm install
npm run web
```

The web app opens at <http://localhost:8081> and uses the backend at
<http://localhost:8000> by default.

### Run on Android, iOS, or Expo Go

Start Expo's development server:

```bash
cd frontend
npm start
```

- Press `a` for an Android emulator.
- Press `i` for an iOS simulator (macOS only).
- To use Expo Go on a physical phone, scan the QR code and make sure the phone
  and development computer are on the same network.

A physical phone cannot reach the computer through `localhost`. Set the
frontend URL in `frontend/.env` using the computer's LAN address:

```dotenv
EXPO_PUBLIC_BACKEND_URL=http://192.168.1.10:8000
```

Replace `192.168.1.10` with the computer's address. Also append that address to
`ALLOWED_HOSTS` in `backend/.env` so FastAPI accepts phone requests:

```dotenv
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.10
```

Restart Expo after changing an environment file. If its cached configuration
is stale, use `npx expo start --clear`.

## Useful commands

From `frontend/`:

```bash
npm run web      # Expo web
npm run android  # Android emulator/device
npm run ios      # iOS simulator (macOS only)
npm run lint     # Frontend lint checks
```

## Important recovered changes

- `EXPO_PUBLIC_BACKEND_URL` configures the API URL for Expo clients;
  `EXPO_BACKEND_URL` remains supported as a compatibility fallback.
- Dataset imports support CSV, XLSX and XLS.
- Authentication, dataset persistence, deletion, validation and deterministic indices are wired to the backend.
- Reverse geocoding is moved off the async event loop with `asyncio.to_thread(...)`.
- Accessibility/automation `testID` values were added to fields, account choices, navigation, upload actions, validation controls, deletion and sign-out.
- `app.json` uses the MetalSense branding and light UI configuration.
