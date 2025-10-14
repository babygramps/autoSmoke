# Quick Start Guide

This guide will help you get the smoker controller running quickly in development mode.

## Prerequisites

Before starting, make sure you have:
- Python 3.11 or higher
- Node.js 18 or higher
- npm or pnpm

## Quick Setup

### 1. Install Poetry (Python dependency manager)

```bash
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"
```

Verify installation:
```bash
poetry --version
```

### 2. Install Backend Dependencies

```bash
cd backend
poetry install
cd ..
```

### 3. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 4. Start Development Servers

Open two terminal windows:

**Terminal 1 - Backend:**
```bash
cd backend
poetry run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### 5. Access the Application

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Default Configuration

The application starts in **SIMULATION MODE** by default, so you don't need any hardware to test it.

- Simulation mode enabled (no hardware required)
- Default setpoint: 225°F
- PID gains: Kp=4.0, Ki=0.1, Kd=20.0
- Database stored locally: `backend/smoker.db`

## Testing the Controller

1. Open http://localhost:5173 in your browser
2. Click "Start" to begin the controller
3. Watch the temperature chart update in real-time
4. Try adjusting the setpoint using the presets (180°F, 225°F, etc.)
5. Test boost mode to see the relay forced ON
6. Check the Settings page to modify PID parameters
7. View historical data in the History page

## Troubleshooting

### Poetry not found
```bash
# Add Poetry to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### npm not found
```bash
# Install Node.js and npm
# Ubuntu/Debian:
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# macOS:
brew install node
```

### Port already in use
```bash
# Backend (port 8000)
lsof -ti:8000 | xargs kill -9

# Frontend (port 5173)
lsof -ti:5173 | xargs kill -9
```

### Module not found errors
```bash
# Reinstall backend dependencies
cd backend
poetry install --no-cache

# Reinstall frontend dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check out the API documentation at http://localhost:8000/docs
- Learn about hardware setup for Raspberry Pi deployment
- Customize PID parameters for your smoker

## Development Tips

- Backend auto-reloads on code changes
- Frontend hot-reloads automatically
- All data is stored in `backend/smoker.db` (SQLite)
- Logs are written to `backend/smoker.log`
- WebSocket connects automatically for real-time updates

## Production Deployment

When ready to deploy to a Raspberry Pi:

1. Set `SMOKER_SIM_MODE=false` in `/etc/smoker.env`
2. Follow the hardware wiring diagram in README.md
3. Run `make build` to build the frontend
4. Run `make production-deploy` to deploy
5. Run `make service-start` to start as a service

Enjoy your automated smoker controller! 🔥🍖
