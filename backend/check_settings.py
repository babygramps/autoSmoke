#!/usr/bin/env python3
"""Check current controller settings for debugging oscillation issues."""

import sqlite3
from pathlib import Path

def check_settings(db_path: str = "./smoker.db"):
    """Display current controller settings."""
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM settings WHERE singleton_id = 1")
        row = cursor.fetchone()
        
        if not row:
            print("No settings found in database")
            return
        
        # Get column names
        cursor.execute("PRAGMA table_info(settings)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Create dict
        settings = dict(zip(columns, row))
        
        print("=" * 60)
        print("CURRENT CONTROLLER SETTINGS")
        print("=" * 60)
        print(f"\n🎯 SETPOINT:")
        print(f"  Setpoint: {settings['setpoint_f']:.1f}°F ({settings['setpoint_c']:.1f}°C)")
        
        print(f"\n🔄 CONTROL MODE:")
        print(f"  Mode: {settings['control_mode']}")
        
        print(f"\n⏱️  TIMING PARAMETERS:")
        print(f"  Min ON time:  {settings['min_on_s']}s")
        print(f"  Min OFF time: {settings['min_off_s']}s")
        print(f"  Hysteresis:   {settings['hyst_c']:.1f}°C ({settings['hyst_c'] * 1.8:.1f}°F)")
        print(f"  Time window:  {settings['time_window_s']}s (for PID mode)")
        
        print(f"\n🎛️  PID GAINS:")
        print(f"  Kp: {settings['kp']:.1f}")
        print(f"  Ki: {settings['ki']:.2f}")
        print(f"  Kd: {settings['kd']:.1f}")
        
        # Calculate thresholds for thermostat mode
        if settings['control_mode'] == 'thermostat':
            upper_threshold_c = settings['setpoint_c'] + settings['hyst_c']
            lower_threshold_c = settings['setpoint_c'] - settings['hyst_c']
            upper_threshold_f = upper_threshold_c * 1.8 + 32
            lower_threshold_f = lower_threshold_c * 1.8 + 32
            
            print(f"\n📊 THERMOSTAT THRESHOLDS:")
            print(f"  Turn OFF at: {upper_threshold_f:.1f}°F ({upper_threshold_c:.1f}°C)")
            print(f"  Turn ON at:  {lower_threshold_f:.1f}°F ({lower_threshold_c:.1f}°C)")
            print(f"  Dead band:   {(upper_threshold_f - lower_threshold_f):.1f}°F")
        
        print(f"\n🚨 ALARM THRESHOLDS:")
        hi_alarm_f = settings['hi_alarm_c'] * 1.8 + 32
        lo_alarm_f = settings['lo_alarm_c'] * 1.8 + 32
        print(f"  High alarm:  {hi_alarm_f:.1f}°F ({settings['hi_alarm_c']:.1f}°C)")
        print(f"  Low alarm:   {lo_alarm_f:.1f}°F ({settings['lo_alarm_c']:.1f}°C)")
        
        print(f"\n💡 RECOMMENDATIONS:")
        
        # Check if hysteresis is too small
        if settings['control_mode'] == 'thermostat' and settings['hyst_c'] < 1.5:
            hyst_f = settings['hyst_c'] * 1.8
            print(f"  ⚠️  Hysteresis is very tight ({hyst_f:.1f}°F)")
            print(f"     This can cause rapid cycling!")
            print(f"     Recommended: 2-3°C (3.6-5.4°F) for smokers")
        
        # Check min on/off times
        if settings['min_on_s'] < 10 or settings['min_off_s'] < 10:
            print(f"  ⚠️  Min ON/OFF times are short ({settings['min_on_s']}s/{settings['min_off_s']}s)")
            print(f"     This allows frequent relay cycling")
            print(f"     Recommended: 15-30s for relay longevity")
        
        print("=" * 60)
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_settings()

