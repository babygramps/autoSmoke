"""Configuration management for the smoker controller."""

from enum import Enum
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlMode(str, Enum):
    """Control mode for heater control."""
    THERMOSTAT = "thermostat"  # Simple on/off with hysteresis
    TIME_PROPORTIONAL = "time_proportional"  # PID with time-proportional relay control


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # API Configuration
    smoker_api_token: str = Field(default="changeme", alias="SMOKER_API_TOKEN")
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        alias="ALLOWED_ORIGINS"
    )
    
    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v):
        """Parse comma-separated origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # Database
    smoker_db_path: str = Field(default="./smoker.db", alias="SMOKER_DB_PATH")
    
    # Temperature Units
    smoker_units: str = Field(default="F", alias="SMOKER_UNITS")
    
    # Default Setpoint
    smoker_setpoint: float = Field(default=225.0, alias="SMOKER_SETPOINT")
    
    # PID Controller
    smoker_pid_kp: float = Field(default=4.0, alias="SMOKER_PID_KP")
    smoker_pid_ki: float = Field(default=0.1, alias="SMOKER_PID_KI")
    smoker_pid_kd: float = Field(default=20.0, alias="SMOKER_PID_KD")
    
    # Control Mode
    smoker_control_mode: str = Field(default="thermostat", alias="SMOKER_CONTROL_MODE")
    
    # Relay Control
    smoker_min_on_s: int = Field(default=5, alias="SMOKER_MIN_ON_S")
    smoker_min_off_s: int = Field(default=5, alias="SMOKER_MIN_OFF_S")
    smoker_hyst_c: float = Field(default=0.6, alias="SMOKER_HYST_C")
    smoker_time_window_s: int = Field(default=10, alias="SMOKER_TIME_WINDOW_S")  # Time window for time-proportional control
    smoker_gpio_pin: int = Field(default=17, alias="SMOKER_GPIO_PIN")
    smoker_relay_active_high: bool = Field(default=False, alias="SMOKER_RELAY_ACTIVE_HIGH")
    
    # Simulation Mode
    smoker_sim_mode: bool = Field(default=True, alias="SMOKER_SIM_MODE")
    
    # Alarm Thresholds (in Celsius)
    smoker_hi_alarm_c: float = Field(default=135.0, alias="SMOKER_HI_ALARM_C")
    smoker_lo_alarm_c: float = Field(default=65.6, alias="SMOKER_LO_ALARM_C")
    smoker_stuck_high_rate_c_per_min: float = Field(default=2.0, alias="SMOKER_STUCK_HIGH_RATE_C_PER_MIN")
    smoker_stuck_high_duration_s: int = Field(default=60, alias="SMOKER_STUCK_HIGH_DURATION_S")
    
    # Boost Mode
    smoker_boost_duration_s: int = Field(default=60, alias="SMOKER_BOOST_DURATION_S")
    
    # Webhook
    smoker_webhook_url: Optional[str] = Field(default=None, alias="SMOKER_WEBHOOK_URL")
    
    # Logging
    smoker_log_level: str = Field(default="INFO", alias="SMOKER_LOG_LEVEL")
    smoker_log_file: str = Field(default="./smoker.log", alias="SMOKER_LOG_FILE")
        
    def celsius_to_fahrenheit(self, temp_c: float) -> float:
        """Convert Celsius to Fahrenheit."""
        return (temp_c * 9.0 / 5.0) + 32.0
    
    def fahrenheit_to_celsius(self, temp_f: float) -> float:
        """Convert Fahrenheit to Celsius."""
        return (temp_f - 32.0) * 5.0 / 9.0
    
    def get_setpoint_celsius(self) -> float:
        """Get setpoint in Celsius."""
        if self.smoker_units.upper() == "F":
            return self.fahrenheit_to_celsius(self.smoker_setpoint)
        return self.smoker_setpoint
    
    def get_setpoint_fahrenheit(self) -> float:
        """Get setpoint in Fahrenheit."""
        if self.smoker_units.upper() == "C":
            return self.celsius_to_fahrenheit(self.smoker_setpoint)
        return self.smoker_setpoint


# Global settings instance
settings = Settings()
