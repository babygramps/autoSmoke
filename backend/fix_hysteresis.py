#!/usr/bin/env python3
"""Fix negative hysteresis value in settings."""

import sqlite3
from pathlib import Path

def fix_hysteresis(db_path: str = "./smoker.db"):
    """Fix the hysteresis setting."""
    
    if not Path(db_path).exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get current hysteresis
        cursor.execute("SELECT hyst_c FROM settings WHERE singleton_id = 1")
        row = cursor.fetchone()
        
        if not row:
            print("No settings found")
            return
        
        current_hyst = row[0]
        print(f"Current hysteresis: {current_hyst:.1f}°C ({current_hyst * 1.8:.1f}°F)")
        
        # Set recommended hysteresis for smokers: 2.0°C (3.6°F)
        # This provides good temperature control without excessive cycling
        new_hyst = 2.0
        
        cursor.execute("UPDATE settings SET hyst_c = ? WHERE singleton_id = 1", (new_hyst,))
        conn.commit()
        
        print(f"\n✅ Fixed hysteresis to: {new_hyst:.1f}°C ({new_hyst * 1.8:.1f}°F)")
        print(f"\nThis will create proper thresholds:")
        print(f"  - More stable temperature control")
        print(f"  - Less frequent relay cycling")
        print(f"  - Better for relay longevity")
        
        print(f"\n📝 You should also consider increasing min_on_s and min_off_s")
        print(f"   from 5s to 15-30s for even better relay protection.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    fix_hysteresis()

