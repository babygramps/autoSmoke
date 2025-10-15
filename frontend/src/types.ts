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
  recipe_id?: number | null;
  recipe_config?: string | null;
  current_phase_id?: number | null;
  meat_target_temp_f?: number | null;
  meat_probe_tc_id?: number | null;
  pending_phase_transition?: boolean;
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
  current_phase: {
    id: number;
    phase_name: string;
    phase_order: number;
    target_temp_f: number;
    started_at: string | null;
    is_active: boolean;
    completion_conditions: PhaseConditions;
  } | null;
  pending_phase_transition: boolean;
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

export interface PhaseTransitionReadyEvent {
  timestamp: string;
  type: 'phase_transition_ready';
  data: {
    smoke_id: number;
    reason: string;
    current_phase: {
      id: number;
      phase_name: string;
      target_temp_f: number;
    } | null;
    next_phase: {
      id: number;
      phase_name: string;
      target_temp_f: number;
    } | null;
  };
}

export interface PhaseStartedEvent {
  timestamp: string;
  type: 'phase_started';
  data: {
    smoke_id: number;
    phase: {
      id: number;
      phase_name: string;
      target_temp_f: number;
      completion_conditions: PhaseConditions;
    };
  };
}

export type WebSocketMessage = TelemetryData | PhaseTransitionReadyEvent | PhaseStartedEvent;

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

// Phase types
export interface PhaseConditions {
  stability_range_f?: number;
  stability_duration_min?: number;
  max_duration_min?: number;
  meat_temp_threshold_f?: number;
}

export interface CookingPhase {
  id: number;
  smoke_id: number;
  phase_name: 'preheat' | 'load_recover' | 'smoke' | 'stall' | 'finish_hold';
  phase_order: number;
  target_temp_f: number;
  started_at: string | null;
  ended_at: string | null;
  is_active: boolean;
  is_paused: boolean;
  completion_conditions: PhaseConditions;
  actual_duration_minutes: number | null;
}

export interface PhaseConfig {
  phase_name: string;
  phase_order: number;
  target_temp_f: number;
  completion_conditions: PhaseConditions;
}

export interface CookingRecipe {
  id: number;
  name: string;
  description: string | null;
  phases: PhaseConfig[];
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface PhaseProgress {
  has_phase: boolean;
  phase_name?: string;
  phase_order?: number;
  target_temp_f?: number;
  duration_minutes?: number;
  overall_progress?: number;
  progress_factors?: Array<{
    type: string;
    progress: number;
    current: number;
    target: number;
    met: boolean;
    in_range?: boolean;
  }>;
  conditions_met?: boolean;
  error?: string;
}

// Smoke/Session types
export interface SmokeCreate {
  name: string;
  description?: string;
  recipe_id: number;
  preheat_temp_f?: number;
  cook_temp_f?: number;
  finish_temp_f?: number;
  meat_target_temp_f?: number;
  meat_probe_tc_id?: number;
  enable_stall_detection?: boolean;
  preheat_duration_min?: number;
  preheat_stability_min?: number;
  cook_duration_min?: number;
  finish_duration_min?: number;
}

export interface SmokeUpdate {
  name?: string;
  description?: string;
  meat_target_temp_f?: number;
  meat_probe_tc_id?: number;
  preheat_temp_f?: number;
  cook_temp_f?: number;
  finish_temp_f?: number;
  enable_stall_detection?: boolean;
  preheat_duration_min?: number;
  preheat_stability_min?: number;
  cook_duration_min?: number;
  finish_duration_min?: number;
}

export interface PhaseUpdate {
  target_temp_f?: number;
  completion_conditions?: PhaseConditions;
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
