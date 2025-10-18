"""Database models for the smoker controller."""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship


# Control mode options
CONTROL_MODE_THERMOSTAT = "thermostat"
CONTROL_MODE_TIME_PROPORTIONAL = "time_proportional"


class CookingRecipe(SQLModel, table=True):
    """Preset cooking recipes/templates."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(description="Recipe name (e.g., Brisket, Ribs)", index=True)
    description: Optional[str] = Field(default=None, description="Recipe description")
    phases: str = Field(description="JSON array of phase configurations")
    is_system: bool = Field(default=False, description="System preset vs user-created")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Smoke(SQLModel, table=True):
    """A smoking session - groups readings together."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(description="Name of the smoking session", index=True)
    description: Optional[str] = Field(default=None, description="Optional description")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="When session started")
    ended_at: Optional[datetime] = Field(default=None, description="When session ended")
    is_active: bool = Field(default=True, description="Whether this is the currently active session")
    
    # Recipe/phase tracking
    recipe_id: Optional[int] = Field(default=None, foreign_key="cookingrecipe.id", description="Link to recipe")
    recipe_config: Optional[str] = Field(default=None, description="JSON snapshot of recipe at session start")
    current_phase_id: Optional[int] = Field(default=None, description="Current active phase ID")
    meat_target_temp_f: Optional[float] = Field(default=None, description="Target meat temperature")
    meat_probe_tc_id: Optional[int] = Field(default=None, foreign_key="thermocouple.id", description="Meat probe thermocouple")
    pending_phase_transition: bool = Field(default=False, description="Flag for awaiting user approval")
    
    # Summary stats (computed when session ends)
    total_duration_minutes: Optional[int] = Field(default=None, description="Total session duration")
    avg_temp_f: Optional[float] = Field(default=None, description="Average temperature")
    min_temp_f: Optional[float] = Field(default=None, description="Minimum temperature")
    max_temp_f: Optional[float] = Field(default=None, description="Maximum temperature")


class SmokePhase(SQLModel, table=True):
    """Phase tracking for active smoke session."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    smoke_id: int = Field(foreign_key="smoke.id", index=True, description="Parent smoke session")
    phase_name: str = Field(description="Phase name: preheat, load_recover, smoke, stall, finish_hold")
    phase_order: int = Field(description="Order in sequence (0-indexed)")
    target_temp_f: float = Field(description="Target temperature for this phase")
    started_at: datetime = Field(default_factory=datetime.utcnow, description="When phase started")
    ended_at: Optional[datetime] = Field(default=None, description="When phase ended")
    is_active: bool = Field(default=False, description="Whether this is the currently active phase")
    is_paused: bool = Field(default=False, description="Whether this phase is currently paused")
    completion_conditions: str = Field(description="JSON with stability/time/temp conditions")
    actual_duration_minutes: Optional[int] = Field(default=None, description="Actual phase duration")


class Thermocouple(SQLModel, table=True):
    """Thermocouple configuration."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(description="User-friendly name for the thermocouple", index=True)
    cs_pin: int = Field(description="GPIO pin for SPI CS (chip select)")
    enabled: bool = Field(default=True, description="Whether this thermocouple is enabled")
    is_control: bool = Field(default=False, description="Whether this is the control thermocouple for PID")
    order: int = Field(default=0, description="Display order")
    color: str = Field(default="#3b82f6", description="Display color (hex)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Reading(SQLModel, table=True):
    """Temperature reading and control state at a point in time."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    smoke_id: Optional[int] = Field(default=None, foreign_key="smoke.id", index=True, description="Session this reading belongs to")
    temp_c: float = Field(description="Control temperature in Celsius")
    temp_f: float = Field(description="Control temperature in Fahrenheit")
    setpoint_c: float = Field(description="Setpoint in Celsius")
    setpoint_f: float = Field(description="Setpoint in Fahrenheit")
    output_bool: bool = Field(description="PID output as boolean (relay should be on)")
    relay_state: bool = Field(description="Actual relay state")
    loop_ms: int = Field(description="Control loop execution time in milliseconds")
    pid_output: float = Field(description="Raw PID output (0-100%)")
    boost_active: bool = Field(default=False, description="Boost mode was active")


class ThermocoupleReading(SQLModel, table=True):
    """Individual thermocouple reading."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    reading_id: int = Field(foreign_key="reading.id", index=True, description="Parent reading")
    thermocouple_id: int = Field(foreign_key="thermocouple.id", index=True, description="Which thermocouple")
    temp_c: float = Field(description="Temperature in Celsius")
    temp_f: float = Field(description="Temperature in Fahrenheit")
    fault: bool = Field(default=False, description="Whether sensor reported a fault")


class Alert(SQLModel, table=True):
    """System alerts and alarms."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    alert_type: str = Field(description="Type of alert: high_temp, low_temp, stuck_high, sensor_fault")
    severity: str = Field(description="Severity: info, warning, error, critical")
    message: str = Field(description="Human-readable alert message")
    active: bool = Field(default=True, description="Whether alert is currently active")
    acknowledged: bool = Field(default=False, description="Whether alert has been acknowledged")
    cleared_ts: Optional[datetime] = Field(default=None, description="When alert was cleared")
    meta_data: Optional[str] = Field(default=None, description="JSON metadata about the alert")


class Event(SQLModel, table=True):
    """System events and state changes."""
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    kind: str = Field(description="Event type: controller_start, controller_stop, setpoint_change, etc.")
    message: str = Field(description="Event description")
    meta_json: Optional[str] = Field(default=None, description="JSON metadata")


class Settings(SQLModel, table=True):
    """System settings (singleton table)."""
    
    singleton_id: int = Field(default=1, primary_key=True)
    
    # Temperature units
    units: str = Field(default="F", description="Temperature units: F or C")
    
    # Setpoint
    setpoint_c: float = Field(default=107.2, description="Setpoint in Celsius (225F default)")
    setpoint_f: float = Field(default=225.0, description="Setpoint in Fahrenheit")
    
    # Control mode
    control_mode: str = Field(default=CONTROL_MODE_THERMOSTAT, description="Control mode: thermostat or time_proportional")
    
    # PID gains (for time-proportional mode)
    kp: float = Field(default=4.0, description="Proportional gain")
    ki: float = Field(default=0.1, description="Integral gain")
    kd: float = Field(default=20.0, description="Derivative gain")
    
    # Relay control
    min_on_s: int = Field(default=5, description="Minimum relay on time in seconds")
    min_off_s: int = Field(default=5, description="Minimum relay off time in seconds")
    hyst_c: float = Field(default=0.6, description="Hysteresis in Celsius (for thermostat mode)")
    time_window_s: int = Field(default=10, description="Time window for time-proportional control in seconds")
    
    # Alarm thresholds (Celsius)
    hi_alarm_c: float = Field(default=135.0, description="High temperature alarm threshold")
    lo_alarm_c: float = Field(default=65.6, description="Low temperature alarm threshold")
    stuck_high_c: float = Field(default=2.0, description="Stuck high rate threshold (C/min)")
    stuck_high_duration_s: int = Field(default=60, description="Stuck high duration threshold")
    
    # Hardware
    sim_mode: bool = Field(default=False, description="Simulation mode enabled")
    gpio_pin: int = Field(default=17, description="GPIO pin for relay control")
    relay_active_high: bool = Field(default=False, description="Relay active high or low")
    
    # Boost mode
    boost_duration_s: int = Field(default=60, description="Boost mode duration in seconds")
    
    # Adaptive PID
    adaptive_pid_enabled: bool = Field(default=True, description="Adaptive PID tuning enabled")
    
    # Webhook
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL for alerts")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
