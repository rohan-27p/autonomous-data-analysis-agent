# Autonomous Data Analysis Agent Frontend

React + Vite frontend for the FastAPI autonomous data analysis backend.

## Local Development

```powershell
npm install
npm run dev
```

The app reads `VITE_API_BASE_URL`; when unset it defaults to `http://127.0.0.1:8000`.

```powershell
$env:VITE_API_BASE_URL = "https://your-backend.example.com"
npm run dev
```

## Build

```powershell
npm run build
```
