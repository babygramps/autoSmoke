// Type definitions for the smoker controller

export type ControlMode = 'thermostat' | 'time_proportional';

export interface Smoke {
  id: number;
  name: string;
  description: string | null;
  started_at: string;
  ended_at: string | null;
  is_active: boolean;
  total_duration_minutes: number | null;
  avg_temp_f: number | null;
  min_temp_f: number | null;
  max_temp_f: number | null;
}

export interface Reading {
  id: number;
  ts: string;
  smoke_id: number | null;
  temp_c: number;
  temp_f: number;
  setpoint_c: number;
  setpoint_f: number;
  output_bool: boolean;
  relay_state: boolean;
  loop_ms: number;
  pid_output: number;
  boost_active: boolean;
  thermocouple_readings?: Record<number, ThermocoupleReading>;
}

export interface Alert {
  id: number;
  ts: string;
  alert_type: 'high_temp' | 'low_temp' | 'stuck_high' | 'sensor_fault';
  severity: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  active: boolean;
  acknowledged: boolean;
  cleared_ts: string | null;
  metadata: string | null;
}

export interface AlertSummary {
  count: number;
  critical: number;
  error: number;
  warning: number;
  info: number;
  unacknowledged: number;
}

export interface ControllerStatus {
  running: boolean;
  boost_active: boolean;
  boost_until: string | null;
  control_mode: ControlMode;
  active_smoke_id: number | null;
  control_tc_id: number | null;
  thermocouple_readings: Record<number, ThermocoupleReading>;
  current_temp_c: number | null;
  current_temp_f: number | null;
  setpoint_c: number;
  setpoint_f: number;
  pid_output: number;
  output_bool: boolean;
  relay_state: boolean;
  loop_count: number;
  last_loop_time: number | null;
  alert_summary: AlertSummary;
  alerts: Alert[];
}

export interface Settings {
  units: 'F' | 'C';
  setpoint_c: number;
  setpoint_f: number;
  control_mode: ControlMode;
  kp: number;
  ki: number;
  kd: number;
  min_on_s: number;
  min_off_s: number;
  hyst_c: number;
  time_window_s: number;
  hi_alarm_c: number;
  lo_alarm_c: number;
  stuck_high_c: number;
  stuck_high_duration_s: number;
  sim_mode: boolean;
  gpio_pin: number;
  relay_active_high: boolean;
  boost_duration_s: number;
  webhook_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface TelemetryData {
  timestamp: string;
  type: 'telemetry';
  data: ControllerStatus;
}

export interface ChartDataPoint {
  timestamp: string;
  temp_c: number;
  temp_f: number;
  setpoint_c: number;
  setpoint_f: number;
  relay_state: boolean;
  pid_output: number;
  thermocouple_readings?: Record<number, ThermocoupleReading>;
}

export interface ReadingStats {
  period_hours: number;
  reading_count: number;
  stats: {
    temperature_c: {
      min: number;
      max: number;
      avg: number;
    };
    temperature_f: {
      min: number;
      max: number;
      avg: number;
    };
    relay_on_percentage: number;
  } | null;
}

// API Request/Response types
export interface SetpointRequest {
  value: number;
  units: 'F' | 'C';
}

export interface PIDGainsRequest {
  kp: number;
  ki: number;
  kd: number;
  min_on_s: number;
  min_off_s: number;
  hyst_c: number;
}

export interface BoostRequest {
  duration_s?: number;
}

export interface SettingsUpdate {
  units?: 'F' | 'C';
  setpoint_f?: number;
  control_mode?: ControlMode;
  kp?: number;
  ki?: number;
  kd?: number;
  min_on_s?: number;
  min_off_s?: number;
  hyst_c?: number;
  time_window_s?: number;
  hi_alarm_c?: number;
  lo_alarm_c?: number;
  stuck_high_c?: number;
  stuck_high_duration_s?: number;
  sim_mode?: boolean;
  gpio_pin?: number;
  relay_active_high?: boolean;
  boost_duration_s?: number;
  webhook_url?: string | null;
}

// Smoke/Session types
export interface SmokeCreate {
  name: string;
  description?: string;
}

export interface SmokeUpdate {
  name?: string;
  description?: string;
}

// Thermocouple types
export interface Thermocouple {
  id: number;
  name: string;
  cs_pin: number;
  enabled: boolean;
  is_control: boolean;
  order: number;
  color: string;
  created_at: string;
  updated_at: string;
}

export interface ThermocoupleCreate {
  name: string;
  cs_pin: number;
  enabled?: boolean;
  color?: string;
}

export interface ThermocoupleUpdate {
  name?: string;
  cs_pin?: number;
  enabled?: boolean;
  order?: number;
  color?: string;
}

export interface ThermocoupleReading {
  temp_c: number;
  temp_f: number;
  fault: boolean;
}
