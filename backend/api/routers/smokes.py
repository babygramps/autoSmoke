"""Smoke session management API endpoints."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Annotated, Optional, List, Dict, Any
from datetime import datetime

from db.models import Smoke, SmokePhase, CookingRecipe
from db.session import get_session_sync
from core.app_state import get_service_container
from core.container import get_controller
from core.controller import SmokerController
from core.phase_manager import phase_manager
from sqlmodel import select

logger = logging.getLogger(__name__)

ControllerDep = Annotated[SmokerController, Depends(get_controller)]

router = APIRouter()


class SmokeCreate(BaseModel):
    """Schema for creating a new smoke session with recipe."""
    name: str
    description: Optional[str] = None
    recipe_id: int
    # Customizable parameters
    preheat_temp_f: float = 270.0
    cook_temp_f: float = 225.0
    finish_temp_f: float = 160.0
    meat_target_temp_f: Optional[float] = None
    meat_probe_tc_id: Optional[int] = None
    enable_stall_detection: bool = True
    # Phase timing controls
    preheat_duration_min: int = 60  # Maximum preheat time
    preheat_stability_min: int = 10  # How long to hold stable before advancing
    stability_range_f: float = 5.0  # Temperature stability range (±°F) for preheat
    cook_duration_min: int = 360  # Maximum cook phase time (6 hours default)
    cook_stability_min: int = 10  # Cook phase stability hold time
    cook_stability_range_f: float = 10.0  # Cook phase temperature stability range (±°F)
    finish_duration_min: int = 120  # Maximum finish phase time (2 hours default)
    finish_stability_min: int = 10  # Finish phase stability hold time
    finish_stability_range_f: float = 10.0  # Finish phase temperature stability range (±°F)


class SmokeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    meat_target_temp_f: Optional[float] = None
    meat_probe_tc_id: Optional[int] = None
    preheat_temp_f: Optional[float] = None
    cook_temp_f: Optional[float] = None
    finish_temp_f: Optional[float] = None
    enable_stall_detection: Optional[bool] = None
    # Phase timing controls
    preheat_duration_min: Optional[int] = None
    preheat_stability_min: Optional[int] = None
    stability_range_f: Optional[float] = None
    cook_duration_min: Optional[int] = None
    cook_stability_min: Optional[int] = None
    cook_stability_range_f: Optional[float] = None
    finish_duration_min: Optional[int] = None
    finish_stability_min: Optional[int] = None
    finish_stability_range_f: Optional[float] = None


class PhaseUpdate(BaseModel):
    """Schema for updating phase parameters."""
    target_temp_f: Optional[float] = None
    completion_conditions: Optional[Dict[str, Any]] = None


@router.get("")
async def list_smokes(active_only: bool = False, limit: int = 50):
    """Get list of smoke sessions."""
    try:
        with get_session_sync() as session:
            if active_only:
                statement = select(Smoke).where(Smoke.is_active == True).limit(limit)
            else:
                statement = select(Smoke).order_by(Smoke.started_at.desc()).limit(limit)
            
            smokes = session.exec(statement).all()
            
            return {
                "smokes": [
                    {
                        "id": smoke.id,
                        "name": smoke.name,
                        "description": smoke.description,
                        "started_at": smoke.started_at.isoformat() + 'Z' if not smoke.started_at.isoformat().endswith('Z') else smoke.started_at.isoformat(),
                        "ended_at": (smoke.ended_at.isoformat() + 'Z' if not smoke.ended_at.isoformat().endswith('Z') else smoke.ended_at.isoformat()) if smoke.ended_at else None,
                        "is_active": smoke.is_active,
                        "total_duration_minutes": smoke.total_duration_minutes,
                        "avg_temp_f": smoke.avg_temp_f,
                        "min_temp_f": smoke.min_temp_f,
                        "max_temp_f": smoke.max_temp_f,
                    }
                    for smoke in smokes
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list smoke sessions: {str(e)}")


@router.get("/{smoke_id}")
async def get_smoke(smoke_id: int):
    """Get a specific smoke session."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            return {
                "id": smoke.id,
                "name": smoke.name,
                "description": smoke.description,
                "started_at": smoke.started_at.isoformat() + 'Z' if not smoke.started_at.isoformat().endswith('Z') else smoke.started_at.isoformat(),
                "ended_at": (smoke.ended_at.isoformat() + 'Z' if not smoke.ended_at.isoformat().endswith('Z') else smoke.ended_at.isoformat()) if smoke.ended_at else None,
                "is_active": smoke.is_active,
                "total_duration_minutes": smoke.total_duration_minutes,
                "avg_temp_f": smoke.avg_temp_f,
                "min_temp_f": smoke.min_temp_f,
                "max_temp_f": smoke.max_temp_f,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get smoke session: {str(e)}")


@router.post("")
async def create_smoke(
    smoke_create: SmokeCreate,
    controller: ControllerDep,
):
    """Create a new smoke session with recipe and phases."""
    try:
        with get_session_sync() as session:
            # Get the recipe
            recipe = session.get(CookingRecipe, smoke_create.recipe_id)
            if not recipe:
                raise HTTPException(status_code=404, detail=f"Recipe {smoke_create.recipe_id} not found")
            
            # Deactivate all other smoke sessions
            statement = select(Smoke).where(Smoke.is_active == True)
            active_smokes = session.exec(statement).all()
            for active_smoke in active_smokes:
                active_smoke.is_active = False
                # Compute stats if ending a session
                if not active_smoke.ended_at:
                    active_smoke.ended_at = datetime.utcnow()
                    await _compute_smoke_stats(session, active_smoke)
            
            # Create session configuration with user customizations
            session_config = {
                "recipe_phases": recipe.phases,
                "preheat_temp_f": smoke_create.preheat_temp_f,
                "cook_temp_f": smoke_create.cook_temp_f,
                "finish_temp_f": smoke_create.finish_temp_f,
                "enable_stall_detection": smoke_create.enable_stall_detection,
                "preheat_duration_min": smoke_create.preheat_duration_min,
                "preheat_stability_min": smoke_create.preheat_stability_min,
                "stability_range_f": smoke_create.stability_range_f,
                "cook_duration_min": smoke_create.cook_duration_min,
                "cook_stability_min": smoke_create.cook_stability_min,
                "cook_stability_range_f": smoke_create.cook_stability_range_f,
                "finish_duration_min": smoke_create.finish_duration_min,
                "finish_stability_min": smoke_create.finish_stability_min,
                "finish_stability_range_f": smoke_create.finish_stability_range_f
            }
            
            # Create new smoke session
            smoke = Smoke(
                name=smoke_create.name,
                description=smoke_create.description,
                is_active=True,
                recipe_id=recipe.id,
                recipe_config=json.dumps(session_config),  # Store snapshot with customizations
                meat_target_temp_f=smoke_create.meat_target_temp_f,
                meat_probe_tc_id=smoke_create.meat_probe_tc_id,
                pending_phase_transition=False
            )
            session.add(smoke)
            session.commit()
            session.refresh(smoke)
            
            # Create phases from recipe with user customizations
            recipe_phases = json.loads(recipe.phases)
            created_phases = []
            
            for phase_config in recipe_phases:
                # Apply user temperature customizations
                target_temp_f = phase_config["target_temp_f"]
                if phase_config["phase_name"] == "preheat":
                    target_temp_f = smoke_create.preheat_temp_f
                elif phase_config["phase_name"] in ["load_recover", "smoke"]:
                    target_temp_f = smoke_create.cook_temp_f
                elif phase_config["phase_name"] == "finish_hold":
                    target_temp_f = smoke_create.finish_temp_f
                
                # Adjust completion conditions
                conditions = phase_config["completion_conditions"].copy()
                
                # Apply phase timing customizations
                if phase_config["phase_name"] == "preheat":
                    conditions["max_duration_min"] = smoke_create.preheat_duration_min
                    conditions["stability_duration_min"] = smoke_create.preheat_stability_min
                    conditions["stability_range_f"] = smoke_create.stability_range_f
                elif phase_config["phase_name"] in ["load_recover", "smoke"]:
                    # Cook phases use cook_duration_min
                    conditions["max_duration_min"] = smoke_create.cook_duration_min
                    # Apply cook phase stability settings
                    if "stability_duration_min" in conditions:
                        conditions["stability_duration_min"] = smoke_create.cook_stability_min
                    if "stability_range_f" in conditions:
                        conditions["stability_range_f"] = smoke_create.cook_stability_range_f
                elif phase_config["phase_name"] == "finish_hold":
                    conditions["max_duration_min"] = smoke_create.finish_duration_min
                    # Apply finish phase stability settings
                    if "stability_duration_min" in conditions:
                        conditions["stability_duration_min"] = smoke_create.finish_stability_min
                    if "stability_range_f" in conditions:
                        conditions["stability_range_f"] = smoke_create.finish_stability_range_f
                
                # Disable stall phase if stall detection is off
                if not smoke_create.enable_stall_detection and phase_config["phase_name"] == "stall":
                    # Skip stall phase by setting very short duration
                    conditions["max_duration_min"] = 1
                
                phase = SmokePhase(
                    smoke_id=smoke.id,
                    phase_name=phase_config["phase_name"],
                    phase_order=phase_config["phase_order"],
                    target_temp_f=target_temp_f,
                    completion_conditions=json.dumps(conditions),
                    is_active=False  # Will activate first phase manually
                )
                session.add(phase)
                created_phases.append(phase)
            
            session.commit()
            
            # Refresh all phases to get IDs
            for phase in created_phases:
                session.refresh(phase)
            
            # Activate first phase and set as current
            if created_phases:
                first_phase = created_phases[0]
                first_phase.is_active = True
                first_phase.started_at = datetime.utcnow()
                smoke.current_phase_id = first_phase.id
                
                # Set controller setpoint to first phase target
                await controller.set_setpoint(first_phase.target_temp_f)
                
                session.commit()
                logger.info(f"Started smoke session '{smoke.name}' with phase: {first_phase.phase_name}")
            
            # Set as active in controller
            controller.set_active_smoke(smoke.id)
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' created with {len(created_phases)} phases",
                "smoke": {
                    "id": smoke.id,
                    "name": smoke.name,
                    "description": smoke.description,
                    "started_at": smoke.started_at.isoformat() + 'Z' if not smoke.started_at.isoformat().endswith('Z') else smoke.started_at.isoformat(),
                    "is_active": smoke.is_active,
                    "recipe_id": smoke.recipe_id,
                    "current_phase_id": smoke.current_phase_id,
                    "meat_target_temp_f": smoke.meat_target_temp_f,
                    "meat_probe_tc_id": smoke.meat_probe_tc_id
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create smoke session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create smoke session: {str(e)}")


@router.put("/{smoke_id}")
async def update_smoke(
    smoke_id: int,
    smoke_update: SmokeUpdate,
    controller: ControllerDep,
):
    """Update a smoke session and its phase configurations."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            # Track what's being updated for logging
            updates = []
            
            # Update basic fields
            if smoke_update.name is not None:
                smoke.name = smoke_update.name
                updates.append(f"name='{smoke_update.name}'")
            if smoke_update.description is not None:
                smoke.description = smoke_update.description
                updates.append("description")
            if smoke_update.meat_target_temp_f is not None:
                smoke.meat_target_temp_f = smoke_update.meat_target_temp_f
                updates.append(f"meat_target={smoke_update.meat_target_temp_f}°F")
            if smoke_update.meat_probe_tc_id is not None:
                smoke.meat_probe_tc_id = smoke_update.meat_probe_tc_id
                updates.append(f"meat_probe_tc={smoke_update.meat_probe_tc_id}")
            
            # Update temperature presets and stall detection in recipe_config
            config_updated = False
            if smoke.recipe_config:
                try:
                    config = json.loads(smoke.recipe_config)
                except json.JSONDecodeError:
                    # Old format: just recipe phases string, create new config
                    config = {
                        "recipe_phases": smoke.recipe_config,
                        "preheat_temp_f": 270.0,
                        "cook_temp_f": 225.0,
                        "finish_temp_f": 160.0,
                        "enable_stall_detection": True
                    }
                
                # Update temperature settings in config
                if smoke_update.preheat_temp_f is not None:
                    config["preheat_temp_f"] = smoke_update.preheat_temp_f
                    config_updated = True
                    updates.append(f"preheat={smoke_update.preheat_temp_f}°F")
                if smoke_update.cook_temp_f is not None:
                    config["cook_temp_f"] = smoke_update.cook_temp_f
                    config_updated = True
                    updates.append(f"cook={smoke_update.cook_temp_f}°F")
                if smoke_update.finish_temp_f is not None:
                    config["finish_temp_f"] = smoke_update.finish_temp_f
                    config_updated = True
                    updates.append(f"finish={smoke_update.finish_temp_f}°F")
                if smoke_update.enable_stall_detection is not None:
                    config["enable_stall_detection"] = smoke_update.enable_stall_detection
                    config_updated = True
                    updates.append(f"stall_detection={smoke_update.enable_stall_detection}")
                if smoke_update.preheat_duration_min is not None:
                    config["preheat_duration_min"] = smoke_update.preheat_duration_min
                    config_updated = True
                    updates.append(f"preheat_duration={smoke_update.preheat_duration_min}min")
                if smoke_update.preheat_stability_min is not None:
                    config["preheat_stability_min"] = smoke_update.preheat_stability_min
                    config_updated = True
                    updates.append(f"preheat_stability={smoke_update.preheat_stability_min}min")
                if smoke_update.stability_range_f is not None:
                    config["stability_range_f"] = smoke_update.stability_range_f
                    config_updated = True
                    updates.append(f"stability_range=±{smoke_update.stability_range_f}°F")
                if smoke_update.cook_duration_min is not None:
                    config["cook_duration_min"] = smoke_update.cook_duration_min
                    config_updated = True
                    updates.append(f"cook_duration={smoke_update.cook_duration_min}min")
                if smoke_update.cook_stability_min is not None:
                    config["cook_stability_min"] = smoke_update.cook_stability_min
                    config_updated = True
                    updates.append(f"cook_stability={smoke_update.cook_stability_min}min")
                if smoke_update.cook_stability_range_f is not None:
                    config["cook_stability_range_f"] = smoke_update.cook_stability_range_f
                    config_updated = True
                    updates.append(f"cook_stability_range=±{smoke_update.cook_stability_range_f}°F")
                if smoke_update.finish_duration_min is not None:
                    config["finish_duration_min"] = smoke_update.finish_duration_min
                    config_updated = True
                    updates.append(f"finish_duration={smoke_update.finish_duration_min}min")
                if smoke_update.finish_stability_min is not None:
                    config["finish_stability_min"] = smoke_update.finish_stability_min
                    config_updated = True
                    updates.append(f"finish_stability={smoke_update.finish_stability_min}min")
                if smoke_update.finish_stability_range_f is not None:
                    config["finish_stability_range_f"] = smoke_update.finish_stability_range_f
                    config_updated = True
                    updates.append(f"finish_stability_range=±{smoke_update.finish_stability_range_f}°F")
                
                if config_updated:
                    smoke.recipe_config = json.dumps(config)
                    
                    # Update corresponding phase temperatures and timing
                    statement = select(SmokePhase).where(SmokePhase.smoke_id == smoke_id)
                    phases = session.exec(statement).all()
                    
                    for phase in phases:
                        if smoke_update.preheat_temp_f is not None and phase.phase_name == "preheat":
                            phase.target_temp_f = smoke_update.preheat_temp_f
                            logger.info(f"Updated preheat phase target to {smoke_update.preheat_temp_f}°F")
                        
                        # Update phase timing
                        conditions = json.loads(phase.completion_conditions)
                        timing_updated = False
                        
                        if phase.phase_name == "preheat":
                            if smoke_update.preheat_duration_min is not None:
                                conditions["max_duration_min"] = smoke_update.preheat_duration_min
                                timing_updated = True
                            if smoke_update.preheat_stability_min is not None:
                                conditions["stability_duration_min"] = smoke_update.preheat_stability_min
                                timing_updated = True
                            if smoke_update.stability_range_f is not None:
                                conditions["stability_range_f"] = smoke_update.stability_range_f
                                timing_updated = True
                            if timing_updated:
                                phase.completion_conditions = json.dumps(conditions)
                                logger.info(f"Updated preheat phase timing: max={conditions.get('max_duration_min')}min, stability={conditions.get('stability_duration_min')}min, range=±{conditions.get('stability_range_f')}°F")
                        
                        elif phase.phase_name in ["load_recover", "smoke"]:
                            if smoke_update.cook_duration_min is not None:
                                conditions["max_duration_min"] = smoke_update.cook_duration_min
                                timing_updated = True
                            if smoke_update.cook_stability_min is not None and "stability_duration_min" in conditions:
                                conditions["stability_duration_min"] = smoke_update.cook_stability_min
                                timing_updated = True
                            if smoke_update.cook_stability_range_f is not None and "stability_range_f" in conditions:
                                conditions["stability_range_f"] = smoke_update.cook_stability_range_f
                                timing_updated = True
                            if timing_updated:
                                phase.completion_conditions = json.dumps(conditions)
                                logger.info(f"Updated {phase.phase_name} phase timing: max={conditions.get('max_duration_min')}min, stability={conditions.get('stability_duration_min')}min, range=±{conditions.get('stability_range_f')}°F")
                        
                        elif phase.phase_name == "finish_hold":
                            if smoke_update.finish_duration_min is not None:
                                conditions["max_duration_min"] = smoke_update.finish_duration_min
                                timing_updated = True
                            if smoke_update.finish_stability_min is not None and "stability_duration_min" in conditions:
                                conditions["stability_duration_min"] = smoke_update.finish_stability_min
                                timing_updated = True
                            if smoke_update.finish_stability_range_f is not None and "stability_range_f" in conditions:
                                conditions["stability_range_f"] = smoke_update.finish_stability_range_f
                                timing_updated = True
                            if timing_updated:
                                phase.completion_conditions = json.dumps(conditions)
                                logger.info(f"Updated finish phase timing: max={conditions.get('max_duration_min')}min, stability={conditions.get('stability_duration_min')}min, range=±{conditions.get('stability_range_f')}°F")
                        elif smoke_update.cook_temp_f is not None and phase.phase_name in ["load_recover", "smoke"]:
                            phase.target_temp_f = smoke_update.cook_temp_f
                            logger.info(f"Updated {phase.phase_name} phase target to {smoke_update.cook_temp_f}°F")
                        elif smoke_update.finish_temp_f is not None and phase.phase_name == "finish_hold":
                            phase.target_temp_f = smoke_update.finish_temp_f
                            logger.info(f"Updated finish phase target to {smoke_update.finish_temp_f}°F")
                        
                        # Update stall phase if stall detection changed
                        if smoke_update.enable_stall_detection is not None and phase.phase_name == "stall":
                            conditions = json.loads(phase.completion_conditions)
                            if not smoke_update.enable_stall_detection:
                                # Disable stall phase by setting very short duration
                                conditions["max_duration_min"] = 1
                            else:
                                # Re-enable with normal duration (45-120 min typical)
                                conditions["max_duration_min"] = 120
                            phase.completion_conditions = json.dumps(conditions)
                            logger.info(f"Updated stall phase: enabled={smoke_update.enable_stall_detection}")
                    
                    # If current phase was updated, update controller setpoint
                    if smoke.current_phase_id:
                        current_phase = session.get(SmokePhase, smoke.current_phase_id)
                        if current_phase and current_phase.is_active:
                            await controller.set_setpoint(current_phase.target_temp_f)
                            logger.info(f"Updated controller setpoint to {current_phase.target_temp_f}°F for active phase")
            
            session.commit()
            session.refresh(smoke)
            
            # Log all updates
            if updates:
                logger.info(f"Updated smoke session {smoke_id}: {', '.join(updates)}")
            
            # Parse config for response
            config_data = {}
            if smoke.recipe_config:
                try:
                    config = json.loads(smoke.recipe_config)
                    config_data = {
                        "preheat_temp_f": config.get("preheat_temp_f"),
                        "cook_temp_f": config.get("cook_temp_f"),
                        "finish_temp_f": config.get("finish_temp_f"),
                        "enable_stall_detection": config.get("enable_stall_detection"),
                        "preheat_duration_min": config.get("preheat_duration_min"),
                        "preheat_stability_min": config.get("preheat_stability_min"),
                        "stability_range_f": config.get("stability_range_f"),
                        "cook_duration_min": config.get("cook_duration_min"),
                        "cook_stability_min": config.get("cook_stability_min"),
                        "cook_stability_range_f": config.get("cook_stability_range_f"),
                        "finish_duration_min": config.get("finish_duration_min"),
                        "finish_stability_min": config.get("finish_stability_min"),
                        "finish_stability_range_f": config.get("finish_stability_range_f")
                    }
                except:
                    pass
            
            return {
                "status": "success",
                "message": "Smoke session updated",
                "smoke": {
                    "id": smoke.id,
                    "name": smoke.name,
                    "description": smoke.description,
                    "started_at": smoke.started_at.isoformat(),
                    "ended_at": smoke.ended_at.isoformat() if smoke.ended_at else None,
                    "is_active": smoke.is_active,
                    "meat_target_temp_f": smoke.meat_target_temp_f,
                    "meat_probe_tc_id": smoke.meat_probe_tc_id,
                    **config_data
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update smoke session: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update smoke session: {str(e)}")


@router.post("/{smoke_id}/activate")
async def activate_smoke(smoke_id: int, controller: ControllerDep):
    """Set a smoke session as active."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            # Deactivate all other smokes
            statement = select(Smoke).where(Smoke.is_active == True)
            active_smokes = session.exec(statement).all()
            for active_smoke in active_smokes:
                if active_smoke.id != smoke_id:
                    active_smoke.is_active = False
                    if not active_smoke.ended_at:
                        active_smoke.ended_at = datetime.utcnow()
                        await _compute_smoke_stats(session, active_smoke)
            
            # Activate this smoke
            smoke.is_active = True
            session.commit()
            
            # Set as active in controller
            controller.set_active_smoke(smoke.id)
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' activated"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate smoke session: {str(e)}")


@router.post("/{smoke_id}/end")
async def end_smoke(smoke_id: int, controller: ControllerDep):
    """End a smoke session."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            if smoke.ended_at:
                raise HTTPException(status_code=400, detail="Smoke session already ended")
            
            smoke.ended_at = datetime.utcnow()
            smoke.is_active = False
            
            # Compute statistics
            await _compute_smoke_stats(session, smoke)
            
            session.commit()
            
            # Clear active smoke in controller
            if controller.active_smoke_id == smoke_id:
                controller.active_smoke_id = None
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' ended",
                "smoke": {
                    "id": smoke.id,
                    "name": smoke.name,
                    "ended_at": smoke.ended_at.isoformat() + 'Z' if not smoke.ended_at.isoformat().endswith('Z') else smoke.ended_at.isoformat(),
                    "total_duration_minutes": smoke.total_duration_minutes,
                    "avg_temp_f": smoke.avg_temp_f,
                    "min_temp_f": smoke.min_temp_f,
                    "max_temp_f": smoke.max_temp_f,
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end smoke session: {str(e)}")


@router.delete("/{smoke_id}")
async def delete_smoke(smoke_id: int):
    """Delete a smoke session and all its readings."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            if smoke.is_active:
                raise HTTPException(status_code=400, detail="Cannot delete active smoke session. End it first.")
            
            # Delete associated readings
            from db.models import Reading
            statement = select(Reading).where(Reading.smoke_id == smoke_id)
            readings = session.exec(statement).all()
            for reading in readings:
                session.delete(reading)
            
            # Delete the smoke session
            session.delete(smoke)
            session.commit()
            
            return {
                "status": "success",
                "message": f"Smoke session '{smoke.name}' deleted"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete smoke session: {str(e)}")


async def _compute_smoke_stats(session, smoke: Smoke):
    """Compute statistics for a smoke session."""
    from db.models import Reading
    from sqlmodel import func, select
    
    # Duration
    if smoke.ended_at and smoke.started_at:
        duration = smoke.ended_at - smoke.started_at
        smoke.total_duration_minutes = int(duration.total_seconds() / 60)
    
    # Temperature stats
    statement = select(
        func.avg(Reading.temp_f),
        func.min(Reading.temp_f),
        func.max(Reading.temp_f)
    ).where(Reading.smoke_id == smoke.id)
    
    result = session.exec(statement).first()
    if result and result[0] is not None:
        smoke.avg_temp_f = round(result[0], 1)
        smoke.min_temp_f = round(result[1], 1)
        smoke.max_temp_f = round(result[2], 1)


# ========== Phase Management Endpoints ==========

@router.get("/{smoke_id}/phases")
async def get_smoke_phases(smoke_id: int):
    """Get all phases for a smoke session."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            statement = select(SmokePhase).where(SmokePhase.smoke_id == smoke_id).order_by(SmokePhase.phase_order)
            phases = session.exec(statement).all()
            
            return {
                "phases": [
                    {
                        "id": phase.id,
                        "phase_name": phase.phase_name,
                        "phase_order": phase.phase_order,
                        "target_temp_f": phase.target_temp_f,
                        "started_at": phase.started_at.isoformat() if phase.started_at else None,
                        "ended_at": phase.ended_at.isoformat() if phase.ended_at else None,
                        "is_active": phase.is_active,
                        "completion_conditions": json.loads(phase.completion_conditions),
                        "actual_duration_minutes": phase.actual_duration_minutes
                    }
                    for phase in phases
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get phases: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get phases: {str(e)}")


@router.post("/{smoke_id}/approve-phase-transition")
async def approve_phase_transition(
    smoke_id: int,
    controller: ControllerDep,
    request: Request,
):
    """User approves moving to next phase."""
    try:
        success, error_msg = phase_manager.approve_phase_transition(smoke_id)
        
        if not success:
            raise HTTPException(status_code=400, detail=error_msg or "Failed to approve phase transition")
        
        # Update controller setpoint to new phase target
        current_phase = phase_manager.get_current_phase(smoke_id)
        if current_phase:
            await controller.set_setpoint(current_phase.target_temp_f)
            logger.info(f"Controller setpoint updated to {current_phase.target_temp_f}°F for phase {current_phase.phase_name}")
            
            # Broadcast phase started event
            try:
                ws_manager = get_service_container(request.app).connection_manager
                await ws_manager.broadcast_phase_event("phase_started", {
                    "smoke_id": smoke_id,
                    "phase": {
                        "id": current_phase.id,
                        "phase_name": current_phase.phase_name,
                        "target_temp_f": current_phase.target_temp_f,
                        "completion_conditions": json.loads(current_phase.completion_conditions)
                    }
                })
            except Exception as e:
                logger.error(f"Failed to broadcast phase started event: {e}")
        
        return {
            "status": "success",
            "message": "Phase transition approved",
            "current_phase": {
                "id": current_phase.id,
                "phase_name": current_phase.phase_name,
                "target_temp_f": current_phase.target_temp_f
            } if current_phase else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to approve phase transition: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to approve phase transition: {str(e)}")


@router.put("/{smoke_id}/phases/{phase_id}")
async def update_phase(
    smoke_id: int,
    phase_id: int,
    phase_update: PhaseUpdate,
    controller: ControllerDep,
):
    """Edit phase parameters during session."""
    try:
        with get_session_sync() as session:
            # Verify smoke exists
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
            
            # Verify phase belongs to this smoke
            phase = session.get(SmokePhase, phase_id)
            if not phase or phase.smoke_id != smoke_id:
                raise HTTPException(status_code=404, detail="Phase not found")
        
        # Update phase using phase manager
        success, error_msg = phase_manager.update_phase(
            phase_id,
            target_temp_f=phase_update.target_temp_f,
            completion_conditions=phase_update.completion_conditions
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=error_msg or "Failed to update phase")
        
        # If this is the active phase and temp changed, update controller
        with get_session_sync() as session:
            phase = session.get(SmokePhase, phase_id)
            if phase and phase.is_active and phase_update.target_temp_f is not None:
                await controller.set_setpoint(phase_update.target_temp_f)
                logger.info(f"Updated active phase setpoint to {phase_update.target_temp_f}°F")
        
        return {
            "status": "success",
            "message": "Phase updated"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update phase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update phase: {str(e)}")


@router.post("/{smoke_id}/skip-phase")
async def skip_phase(smoke_id: int, controller: ControllerDep):
    """Skip current phase and move to next."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
        
        success, error_msg = phase_manager.skip_phase(smoke_id)
        
        if not success:
            raise HTTPException(status_code=400, detail=error_msg or "Failed to skip phase")
        
        # Update controller setpoint to new phase target
        current_phase = phase_manager.get_current_phase(smoke_id)
        if current_phase:
            await controller.set_setpoint(current_phase.target_temp_f)
            logger.info(f"Skipped to phase {current_phase.phase_name}, setpoint: {current_phase.target_temp_f}°F")
        
        return {
            "status": "success",
            "message": "Phase skipped",
            "current_phase": {
                "id": current_phase.id,
                "phase_name": current_phase.phase_name,
                "target_temp_f": current_phase.target_temp_f
            } if current_phase else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to skip phase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to skip phase: {str(e)}")


@router.post("/{smoke_id}/pause-phase")
async def pause_phase(smoke_id: int):
    """Pause the current phase. Temperature control continues but phase condition checking stops."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
        
        success, error_msg = phase_manager.pause_phase(smoke_id)
        
        if not success:
            raise HTTPException(status_code=400, detail=error_msg or "Failed to pause phase")
        
        current_phase = phase_manager.get_current_phase(smoke_id)
        
        return {
            "status": "success",
            "message": "Phase paused",
            "current_phase": {
                "id": current_phase.id,
                "phase_name": current_phase.phase_name,
                "target_temp_f": current_phase.target_temp_f,
                "is_paused": current_phase.is_paused
            } if current_phase else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause phase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to pause phase: {str(e)}")


@router.post("/{smoke_id}/resume-phase")
async def resume_phase(smoke_id: int):
    """Resume the current paused phase."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
        
        success, error_msg = phase_manager.resume_phase(smoke_id)
        
        if not success:
            raise HTTPException(status_code=400, detail=error_msg or "Failed to resume phase")
        
        current_phase = phase_manager.get_current_phase(smoke_id)
        
        return {
            "status": "success",
            "message": "Phase resumed",
            "current_phase": {
                "id": current_phase.id,
                "phase_name": current_phase.phase_name,
                "target_temp_f": current_phase.target_temp_f,
                "is_paused": current_phase.is_paused
            } if current_phase else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume phase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume phase: {str(e)}")


@router.get("/{smoke_id}/phase-progress")
async def get_phase_progress(smoke_id: int, controller: ControllerDep):
    """Get progress information for current phase."""
    try:
        with get_session_sync() as session:
            smoke = session.get(Smoke, smoke_id)
            if not smoke:
                raise HTTPException(status_code=404, detail="Smoke session not found")
        
        # Get current temperature
        current_temp_f = controller.current_temp_f if controller.current_temp_f else 0.0
        
        # Get meat temp if probe is configured
        meat_temp_f = None
        if smoke.meat_probe_tc_id and smoke.meat_probe_tc_id in controller.tc_readings:
            meat_temp_c, fault = controller.tc_readings[smoke.meat_probe_tc_id]
            if not fault and meat_temp_c is not None:
                from core.config import settings
                meat_temp_f = settings.celsius_to_fahrenheit(meat_temp_c)
        
        progress = phase_manager.get_phase_progress(smoke_id, current_temp_f, meat_temp_f)
        
        return progress
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get phase progress: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get phase progress: {str(e)}")

