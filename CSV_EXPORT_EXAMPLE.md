# CSV Export with Multiple Thermocouples

## Updated Export Format

The CSV export has been updated to include **all thermocouple data** in addition to the control data.

### Example CSV Structure

If you have 3 thermocouples configured (Grate, Meat Probe 1, Meat Probe 2), your CSV will look like:

```csv
timestamp,smoke_id,control_temp_c,control_temp_f,setpoint_c,setpoint_f,output_bool,relay_state,loop_ms,pid_output,boost_active,tc_1_Grate_temp_c,tc_1_Grate_temp_f,tc_1_Grate_fault,tc_2_Meat_Probe_1_temp_c,tc_2_Meat_Probe_1_temp_f,tc_2_Meat_Probe_1_fault,tc_3_Meat_Probe_2_temp_c,tc_3_Meat_Probe_2_temp_f,tc_3_Meat_Probe_2_fault
2025-10-19T10:00:00,1,107.2,225.0,107.2,225.0,true,true,45,75.5,false,107.2,225.0,false,65.5,150.0,false,68.3,155.0,false
2025-10-19T10:00:05,1,107.5,225.5,107.2,225.0,false,false,43,45.2,false,107.5,225.5,false,65.8,150.5,false,68.5,155.3,false
```

### Column Structure

#### Control/System Columns (always present):
- `timestamp` - ISO 8601 timestamp
- `smoke_id` - Current smoke session ID (if any)
- `control_temp_c` - Control thermocouple temperature in Celsius
- `control_temp_f` - Control thermocouple temperature in Fahrenheit
- `setpoint_c` - Target temperature in Celsius
- `setpoint_f` - Target temperature in Fahrenheit
- `output_bool` - PID output as boolean (should relay be on?)
- `relay_state` - Actual relay state
- `loop_ms` - Control loop execution time in milliseconds
- `pid_output` - Raw PID output (0-100%)
- `boost_active` - Whether boost mode was active

#### Thermocouple Columns (dynamic based on configured thermocouples):
For each thermocouple, three columns are added:
- `tc_{id}_{name}_temp_c` - Temperature in Celsius
- `tc_{id}_{name}_temp_f` - Temperature in Fahrenheit
- `tc_{id}_{name}_fault` - Whether sensor had a fault (true/false)

The columns are ordered by the thermocouple's `order` field in the database.

### API Endpoint

```
GET /api/export/readings.csv?from_time=2025-10-19T00:00:00Z&to_time=2025-10-19T23:59:59Z
```

### Key Features

1. **Dynamic Columns**: The CSV automatically adjusts to include all configured thermocouples
2. **Ordered Output**: Thermocouples appear in the order specified in their configuration
3. **Fault Tracking**: Each thermocouple has a fault column to track sensor errors
4. **Backward Compatible**: Empty strings are used if a thermocouple reading is missing
5. **Robust Logging**: Detailed logging shows what data is being exported

### Implementation Details

The export function:
1. Queries all readings in the time range
2. Gets all configured thermocouples
3. For each reading, fetches associated thermocouple readings
4. Builds a row with both control data and all thermocouple data
5. Missing thermocouple data is represented with empty strings

### Logging Output

When exporting, you'll see logs like:
```
📥 Exporting readings from 2025-10-19 00:00:00 to 2025-10-19 23:59:59
📊 Found 1440 readings to export
🌡️ Found 3 configured thermocouples
✅ CSV export complete: 1440 readings exported
```

This helps debug any issues with the export process.

