# PiTmaster - Raspberry Pi Smoker Controller

A production-ready Raspberry Pi smoker controller with web GUI, featuring dual control modes (thermostat and PID), real-time monitoring, and comprehensive alerting.

## Features

- **Dual Control Modes**: Choose between simple thermostat or advanced time-proportional PID control
- **Temperature Control**: MAX31855 thermocouple sensor with precise temperature monitoring
- **Relay Control**: 12V gas solenoid control with intelligent timing constraints
- **Web Interface**: Modern React-based dashboard with real-time charts
- **Real-time Monitoring**: WebSocket-based live telemetry
- **Alert System**: Configurable alarms with webhook notifications
- **Data Logging**: SQLite database with CSV export
- **Simulation Mode**: Development without hardware
- **Production Ready**: systemd service with auto-restart

## Control Modes

The controller supports two control strategies - see [CONTROL_MODES.md](CONTROL_MODES.md) for detailed information:

### 🌡️ Thermostat Mode (Default)
Simple on/off control with hysteresis - **recommended for most users**:
- Easy to understand and configure
- Proven reliability for smoker applications
- Protects relay lifespan with minimum on/off times
- Works great with slow thermal response systems

### ⚙️ Time-Proportional PID Mode (Advanced)
PID-based duty cycle control for advanced users:
- More precise temperature control
- Adaptive response to temperature changes
- Requires PID tuning for optimal performance
- Best for users comfortable with control theory

You can switch between modes at any time through the Settings page in the web interface.

## Hardware Requirements

### Required Components
- Raspberry Pi 4 (recommended) or Pi 3B+
- MAX31855 thermocouple amplifier board
- Type-K thermocouple probe
- 12V gas solenoid valve
- HiLetgo 12V relay module
- 12V power supply for solenoid
- Jumper wires

### Wiring Diagram

```
Raspberry Pi          MAX31855          Relay Module
┌─────────────┐       ┌─────────────┐   ┌─────────────┐
│ GPIO 11 (SCK)│──────→│ SCK         │   │             │
│ GPIO 9 (MISO)│←──────│ MISO        │   │             │
│ GPIO 8 (CE0) │──────→│ CS          │   │             │
│ 3.3V         │──────→│ VCC         │   │             │
│ GND          │──────→│ GND         │   │             │
│ GPIO 17      │───────────────────────→│ IN          │
│ 5V           │───────────────────────→│ VCC         │
│ GND          │───────────────────────→│ GND         │
└─────────────┘       └─────────────┘   └─────────────┘
                                                      │
                                                      │
                                               ┌─────────────┐
                                               │ 12V Solenoid│
                                               │ Valve       │
                                               └─────────────┘
```

## Software Setup

### Prerequisites

1. **Enable SPI on Raspberry Pi**:
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options → SPI → Enable
   sudo reboot
   ```

2. **Install system dependencies**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-pip python3-venv git
   ```

3. **Install Node.js** (for frontend development):
   ```bash
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

4. **Install Poetry** (Python dependency management):
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   export PATH="$HOME/.local/bin:$PATH"
   ```

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd smoker
   ```

2. **Install dependencies**:
   ```bash
   make install
   ```

3. **Configure environment**:
   ```bash
   cp backend/.env.example /etc/smoker.env
   sudo nano /etc/smoker.env
   ```

4. **Build frontend**:
   ```bash
   make build
   ```

5. **Install systemd service**:
   ```bash
   make service-install
   ```

6. **Deploy to production**:
   ```bash
   make production-deploy
   ```

7. **Start the service**:
   ```bash
   make service-start
   ```

## Configuration

### Environment Variables

Edit `/etc/smoker.env` to configure the controller:

```bash
# API Configuration
SMOKER_API_TOKEN=changeme
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000

# Database
SMOKER_DB_PATH=/var/lib/smoker/smoker.db

# Temperature Units (F or C)
SMOKER_UNITS=F

# Default Setpoint
SMOKER_SETPOINT=225

# Control Mode (thermostat or time_proportional)
SMOKER_CONTROL_MODE=thermostat

# PID Controller Gains (for time_proportional mode)
SMOKER_PID_KP=4.0
SMOKER_PID_KI=0.1
SMOKER_PID_KD=20.0

# Relay Control
SMOKER_MIN_ON_S=5          # Minimum on time (thermostat mode)
SMOKER_MIN_OFF_S=5         # Minimum off time (thermostat mode)
SMOKER_HYST_C=0.6          # Hysteresis (thermostat mode)
SMOKER_TIME_WINDOW_S=10    # Time window (time_proportional mode)
SMOKER_GPIO_PIN=17
SMOKER_RELAY_ACTIVE_HIGH=false

# Simulation Mode (true for development without hardware)
SMOKER_SIM_MODE=false

# Alarm Thresholds (in Celsius)
SMOKER_HI_ALARM_C=135.0
SMOKER_LO_ALARM_C=65.6
SMOKER_STUCK_HIGH_RATE_C_PER_MIN=2.0
SMOKER_STUCK_HIGH_DURATION_S=60

# Boost Mode
SMOKER_BOOST_DURATION_S=60

# Webhook (optional)
SMOKER_WEBHOOK_URL=

# Logging
SMOKER_LOG_LEVEL=INFO
SMOKER_LOG_FILE=/var/log/smoker/smoker.log
```

### Control Mode Configuration

**Thermostat Mode** (default):
- **Hysteresis**: Temperature deadband (default: 0.6°C / ~1°F)
- **Min On Time**: Minimum relay on duration (default: 5s)
- **Min Off Time**: Minimum relay off duration (default: 5s)

**Time-Proportional PID Mode** (advanced):
- **Kp (Proportional)**: 4.0 - Controls response to current error
- **Ki (Integral)**: 0.1 - Eliminates steady-state error
- **Kd (Derivative)**: 20.0 - Reduces overshoot and oscillation
- **Time Window**: Duty cycle window length (default: 10s)

See [CONTROL_MODES.md](CONTROL_MODES.md) for detailed tuning guidelines.

## Usage

### Web Interface

Access the web interface at `http://<pi-ip>:8000`

**Dashboard**:
- Real-time temperature display
- Live temperature chart (last 2 hours)
- Controller start/stop controls
- Setpoint adjustment with presets
- Boost mode control
- Alert notifications

**Settings**:
- Control mode selection (Thermostat vs Time-Proportional PID)
- Mode-specific parameter adjustment
- Alarm threshold configuration
- Hardware settings
- Simulation mode toggle

**History**:
- Historical data viewing
- Data export to CSV
- Statistical analysis

### API Endpoints

**Control**:
- `POST /api/control/start` - Start controller
- `POST /api/control/stop` - Stop controller
- `POST /api/control/setpoint` - Set temperature target
- `POST /api/control/pid` - Update PID gains
- `POST /api/control/boost` - Enable boost mode

**Readings**:
- `GET /api/readings` - Get temperature readings
- `GET /api/readings/stats` - Get reading statistics

**Settings**:
- `GET /api/settings` - Get current settings
- `PUT /api/settings` - Update settings

**Alerts**:
- `GET /api/alerts` - Get active alerts
- `POST /api/alerts/{id}/ack` - Acknowledge alert
- `POST /api/alerts/{id}/clear` - Clear alert

**Export**:
- `GET /api/export/readings.csv` - Export readings as CSV
- `GET /api/export/alerts.csv` - Export alerts as CSV

### WebSocket

Real-time telemetry available at `ws://<pi-ip>:8000/ws`

Message format:
```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "type": "telemetry",
  "data": {
    "running": true,
    "current_temp_f": 225.5,
    "setpoint_f": 225.0,
    "relay_state": true,
    "pid_output": 45.2,
    "alert_summary": {
      "count": 0,
      "critical": 0,
      "error": 0,
      "warning": 0
    }
  }
}
```

## Development

### Running in Development Mode

1. **Start backend**:
   ```bash
   cd backend
   poetry run uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Start frontend** (in another terminal):
   ```bash
   cd frontend
   npm run dev
   ```

3. **Or use the Makefile**:
   ```bash
   make dev
   ```

### Simulation Mode

Set `SMOKER_SIM_MODE=true` in your environment to run without hardware:
- Simulates temperature readings with random walk
- Logs relay state changes instead of controlling GPIO
- Perfect for development and testing

### Backend service container

The FastAPI application now bootstraps all long-lived backend services through
`backend/core/container.py`. The `ServiceContainer` class wires together the
database repositories, `SmokerController`, alert manager, and WebSocket
`ConnectionManager` during the application's `lifespan` event. Each router
requests these collaborators via FastAPI dependencies such as
`Depends(get_controller)` or `Depends(get_settings_repository)` instead of
importing module-level singletons.

When adding new endpoints you should rely on the dependency helpers from
`core.container` rather than instantiating services directly. Tests can build an
isolated container with `ServiceContainer.build()` (see
`backend/tests/conftest.py`) to override components or use simulated hardware
without touching production wiring.

### Testing

Run the test suite:
```bash
make test
```

## Troubleshooting

### Common Issues

**1. SPI Permission Denied**:
```bash
sudo usermod -a -G spi,gpio pi
sudo reboot
```

**2. GPIO Permission Denied**:
```bash
sudo usermod -a -G gpio pi
sudo reboot
```

**3. Service Won't Start**:
```bash
# Check logs
make service-logs

# Check service status
make service-status

# Restart service
make service-stop
make service-start
```

**4. Frontend Not Loading**:
- Ensure frontend is built: `make build`
- Check that `frontend/dist` directory exists
- Verify CORS settings in backend configuration

**5. Temperature Reading Issues**:
- Check thermocouple connections
- Verify SPI is enabled
- Test with simulation mode first

### Logs

**Service logs**:
```bash
make service-logs
```

**Application logs**:
```bash
tail -f /var/log/smoker/smoker.log
```

**Database location**:
```bash
ls -la /var/lib/smoker/
```

## Safety Considerations

⚠️ **Important Safety Notes**:

1. **Gas Safety**: This controller manages gas flow. Ensure proper ventilation and gas leak detection.

2. **Temperature Monitoring**: Always monitor temperatures manually as a backup.

3. **Fire Safety**: Keep fire extinguisher nearby and ensure proper clearance.

4. **Electrical Safety**: Use proper grounding and electrical safety practices.

5. **Testing**: Test all safety systems before leaving unattended.

6. **Backup Controls**: Maintain manual override capability for emergency shutdown.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs
3. Create an issue on GitHub
4. Include relevant log output and configuration details
