// API client for the smoker controller

import { 
  Reading, 
  Alert, 
  AlertSummary, 
  ControllerStatus, 
  Settings, 
  ReadingStats,
  SetpointRequest,
  PIDGainsRequest,
  BoostRequest,
  SettingsUpdate,
  Smoke,
  SmokeCreate,
  SmokeUpdate
} from '../types';

const API_BASE = '/api';

class ApiClient {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`API Error: ${response.status} ${error}`);
    }

    return response.json();
  }

  // Control endpoints
  async startController(): Promise<{ status: string; message: string }> {
    return this.request('/control/start', { method: 'POST' });
  }

  async stopController(): Promise<{ status: string; message: string }> {
    return this.request('/control/stop', { method: 'POST' });
  }

  async getStatus(): Promise<ControllerStatus> {
    return this.request('/control/status');
  }

  async setSetpoint(request: SetpointRequest): Promise<{ status: string; message: string; setpoint_f: number; setpoint_c: number }> {
    return this.request('/control/setpoint', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async setPIDGains(request: PIDGainsRequest): Promise<{ status: string; message: string; kp: number; ki: number; kd: number; min_on_s: number; min_off_s: number; hyst_c: number }> {
    return this.request('/control/pid', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async enableBoost(request: BoostRequest = {}): Promise<{ status: string; message: string; duration_s: number }> {
    return this.request('/control/boost', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async disableBoost(): Promise<{ status: string; message: string }> {
    return this.request('/control/boost', { method: 'DELETE' });
  }

  // Readings endpoints
  async getReadings(params: {
    smoke_id?: number;
    from_time?: string;
    to_time?: string;
    limit?: number;
  } = {}): Promise<{ readings: Reading[]; count: number; limit: number }> {
    const searchParams = new URLSearchParams();
    if (params.smoke_id !== undefined) searchParams.set('smoke_id', params.smoke_id.toString());
    if (params.from_time) searchParams.set('from_time', params.from_time);
    if (params.to_time) searchParams.set('to_time', params.to_time);
    if (params.limit) searchParams.set('limit', params.limit.toString());
    
    const query = searchParams.toString();
    return this.request(`/readings?${query}`);
  }

  async getLatestReading(smoke_id?: number): Promise<{ reading: Reading | null }> {
    const params = smoke_id !== undefined ? `?smoke_id=${smoke_id}` : '';
    return this.request(`/readings/latest${params}`);
  }

  async getReadingStats(params: { smoke_id?: number; hours?: number } = {}): Promise<ReadingStats> {
    const searchParams = new URLSearchParams();
    if (params.smoke_id !== undefined) searchParams.set('smoke_id', params.smoke_id.toString());
    if (params.hours) searchParams.set('hours', params.hours.toString());
    const query = searchParams.toString();
    return this.request(`/readings/stats?${query || 'hours=24'}`);
  }

  // Settings endpoints
  async getSettings(): Promise<Settings> {
    return this.request('/settings');
  }

  async updateSettings(settings: SettingsUpdate): Promise<{ status: string; message: string; settings: Settings }> {
    return this.request('/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  async resetSettings(): Promise<{ status: string; message: string; settings: Settings }> {
    return this.request('/settings/reset', { method: 'POST' });
  }

  // Alerts endpoints
  async getAlerts(params: {
    active_only?: boolean;
    limit?: number;
  } = {}): Promise<{ alerts: Alert[]; count: number; active_only: boolean }> {
    const searchParams = new URLSearchParams();
    if (params.active_only !== undefined) searchParams.set('active_only', params.active_only.toString());
    if (params.limit) searchParams.set('limit', params.limit.toString());
    
    const query = searchParams.toString();
    return this.request(`/alerts?${query}`);
  }

  async getAlertSummary(): Promise<AlertSummary> {
    return this.request('/alerts/summary');
  }

  async acknowledgeAlert(alertId: number): Promise<{ status: string; message: string }> {
    return this.request(`/alerts/${alertId}/ack`, { method: 'POST' });
  }

  async clearAlert(alertId: number): Promise<{ status: string; message: string }> {
    return this.request(`/alerts/${alertId}/clear`, { method: 'POST' });
  }

  async clearAllAlerts(): Promise<{ status: string; message: string; cleared_count: number }> {
    return this.request('/alerts/clear-all', { method: 'POST' });
  }

  // Smoke/Session endpoints
  async getSmokes(params: { active_only?: boolean; limit?: number } = {}): Promise<{ smokes: Smoke[] }> {
    const searchParams = new URLSearchParams();
    if (params.active_only !== undefined) searchParams.set('active_only', params.active_only.toString());
    if (params.limit) searchParams.set('limit', params.limit.toString());
    const query = searchParams.toString();
    return this.request(`/smokes?${query}`);
  }

  async getSmoke(smokeId: number): Promise<Smoke> {
    return this.request(`/smokes/${smokeId}`);
  }

  async createSmoke(smoke: SmokeCreate): Promise<{ status: string; message: string; smoke: Smoke }> {
    return this.request('/smokes', {
      method: 'POST',
      body: JSON.stringify(smoke),
    });
  }

  async updateSmoke(smokeId: number, smoke: SmokeUpdate): Promise<{ status: string; message: string; smoke: Smoke }> {
    return this.request(`/smokes/${smokeId}`, {
      method: 'PUT',
      body: JSON.stringify(smoke),
    });
  }

  async activateSmoke(smokeId: number): Promise<{ status: string; message: string }> {
    return this.request(`/smokes/${smokeId}/activate`, { method: 'POST' });
  }

  async endSmoke(smokeId: number): Promise<{ status: string; message: string; smoke: Partial<Smoke> }> {
    return this.request(`/smokes/${smokeId}/end`, { method: 'POST' });
  }

  async deleteSmoke(smokeId: number): Promise<{ status: string; message: string }> {
    return this.request(`/smokes/${smokeId}`, { method: 'DELETE' });
  }

  // Export endpoints
  async exportReadingsCSV(fromTime: string, toTime: string): Promise<Blob> {
    const response = await fetch(`${API_BASE}/export/readings.csv?from_time=${fromTime}&to_time=${toTime}`);
    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`);
    }
    return response.blob();
  }

  async exportAlertsCSV(fromTime: string, toTime: string): Promise<Blob> {
    const response = await fetch(`${API_BASE}/export/alerts.csv?from_time=${fromTime}&to_time=${toTime}`);
    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`);
    }
    return response.blob();
  }

  async exportEventsCSV(fromTime: string, toTime: string): Promise<Blob> {
    const response = await fetch(`${API_BASE}/export/events.csv?from_time=${fromTime}&to_time=${toTime}`);
    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`);
    }
    return response.blob();
  }
}

export const apiClient = new ApiClient();

// WebSocket hook
export function useWebSocket(onMessage: (data: any) => void) {
  const connect = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };
    
    ws.onclose = () => {
      console.log('WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(connect, 5000);
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
    
    return ws;
  };
  
  return { connect };
}
