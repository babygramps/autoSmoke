# Cooking Phase System Implementation

This document describes the multi-phase cooking state machine implementation for the smoker controller.

## Overview

The system now supports automated cooking phases with semi-automatic transitions requiring user approval. Users can create sessions with preset recipes (Brisket, Ribs, Pork Shoulder, Chicken) and customize parameters.

## Features Implemented

### 1. Database Schema
- **CookingRecipe** table: Stores system and custom cooking recipes
- **SmokePhase** table: Tracks phase progress for active sessions
- **Smoke model updates**: Added recipe_id, current_phase_id, meat_target_temp_f, meat_probe_tc_id, pending_phase_transition

### 2. Backend API

#### New Endpoints

**Recipes:**
- `GET /api/recipes` - List all recipes
- `GET /api/recipes/{id}` - Get specific recipe
- `POST /api/recipes` - Create custom recipe
- `PUT /api/recipes/{id}` - Update recipe
- `DELETE /api/recipes/{id}` - Delete recipe
- `POST /api/recipes/{id}/clone` - Clone recipe

**Phase Management:**
- `GET /api/smokes/{id}/phases` - Get all phases for session
- `POST /api/smokes/{id}/approve-phase-transition` - Approve moving to next phase
- `PUT /api/smokes/{id}/phases/{phase_id}` - Edit phase parameters
- `POST /api/smokes/{id}/skip-phase` - Skip current phase
- `GET /api/smokes/{id}/phase-progress` - Get phase progress information

#### Updated Endpoints
- `POST /api/smokes` - Now accepts recipe_id and cooking parameters

### 3. Phase State Machine

**Phase Manager** (`core/phase_manager.py`):
- Checks phase completion conditions each control loop
- Detects temperature stability, duration limits, meat temp thresholds
- Optional stall detection (meat temp < 2°F rise in 30-45 min)
- Requests phase transitions via websocket events

**Cooking Phases:**
1. **Preheat & Clean-burn**: 260-275°F, stable ±5°F for 5-10min
2. **Load & Recover**: Drop to cook temp (225-245°F)
3. **Smoke Phase**: Hold at cook temp for bark/smoke absorption
4. **Stall Management**: Adaptive +10-15°F when stall detected
5. **Finish & Hold**: Reduce to 150-165°F for resting

### 4. Controller Integration

- Automatic phase condition checking in control loop
- WebSocket events for phase_transition_ready, phase_started
- Phase-aware setpoint management
- Supports both with and without meat probes

### 5. Frontend Components

**New Components:**
- **Session Creation Wizard**: Multi-step recipe selection and parameter customization
- **PhaseProgress**: Visual phase timeline with progress indicators
- **PhaseTransitionModal**: User approval dialog for phase transitions
- **EditPhaseDialog**: Edit phase parameters during active session

**Dashboard Integration:**
- New "Cooking Phases" tile shows current phase progress
- Real-time websocket updates trigger phase transition modals
- Edit phase parameters on-the-fly

## Default Recipes

### Brisket
- Preheat: 270°F (10min stability)
- Load & Recover: 225°F
- Smoke: 225°F until meat hits 165°F
- Stall: 240°F until meat hits 180°F
- Finish: 160°F until meat hits 203°F

### Ribs
- Preheat: 265°F (5min stability)
- Load & Recover: 225°F
- Smoke: 225°F for 3 hours
- Finish: 250°F for 2 hours

### Pork Shoulder
- Preheat: 270°F (10min stability)
- Load & Recover: 225°F
- Smoke: 225°F until meat hits 160°F
- Stall: 240°F until meat hits 180°F
- Finish: 160°F until meat hits 195°F

### Chicken
- Preheat: 265°F (5min stability)
- Load & Recover: 250°F
- Smoke: 250°F until meat hits 165°F

## Usage

### Creating a New Session

1. Click "+ New Smoking Session" on Dashboard
2. **Step 1**: Select a recipe preset (Brisket, Ribs, etc.)
3. **Step 2**: Customize parameters:
   - Session name and description
   - Preheat, cook, and finish temperatures
   - Optional: Meat target temp and probe selection
   - Enable/disable stall detection
4. Click "Create Session" - system starts with first phase automatically

### During a Session

**Automatic Phase Transitions:**
- System monitors phase completion conditions continuously
- When conditions are met, a modal appears asking for approval
- Options: "Approve & Continue" or "Stay in Current Phase"
- Temperature setpoint updates automatically upon approval

**Manual Control:**
- Edit phase parameters anytime via "Edit Phase" button
- Skip phase if needed via API
- End session early if desired

**Phase Progress Display:**
- Current phase with icon and target temperature
- Progress bar based on completion conditions
- Timeline showing completed, current, and upcoming phases
- Real-time duration tracking

### Phase Completion Conditions

Phases can complete based on:
- **Temperature Stability**: Temp within ±X°F for Y minutes
- **Meat Temperature**: Meat probe reaches target temp
- **Maximum Duration**: Time limit reached
- Multiple conditions can apply; any met condition triggers transition request

## Migration

To apply database changes:

```bash
cd autoSmoke/autoSmoke/backend
python migrate_phases.py
```

This will:
1. Create new CookingRecipe and SmokePhase tables
2. Add new columns to Smoke table
3. Seed default recipes (Brisket, Ribs, Pork Shoulder, Chicken)

## Architecture Notes

### Semi-Automatic Transitions
- System detects when phase conditions are met
- Websocket event sent to frontend
- User must approve before transition occurs
- Prevents unexpected temperature changes during critical moments

### Meat Probe Support
- Optional: Works with or without meat probes
- If meat probe configured: Uses actual temp for stall detection and thresholds
- If no meat probe: Uses time-based estimates or manual management

### Customization
- All phase parameters editable during session
- Changes take effect immediately
- Useful for adapting to unexpected conditions

### Logging
- Phase transitions logged as events
- Phase durations recorded in database
- Full audit trail for post-mortem analysis

## Future Enhancements

Potential improvements:
- Recipe management UI page
- Custom recipe builder
- Phase templates/library
- Advanced stall detection algorithms
- Mobile notifications for phase transitions
- Historical phase performance analytics

