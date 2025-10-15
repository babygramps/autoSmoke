"""Cooking recipe management API endpoints."""

import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from db.models import CookingRecipe
from db.session import get_session_sync
from sqlmodel import select

logger = logging.getLogger(__name__)

router = APIRouter()


class PhaseConfig(BaseModel):
    """Configuration for a single cooking phase."""
    phase_name: str  # preheat, load_recover, smoke, stall, finish_hold
    phase_order: int
    target_temp_f: float
    completion_conditions: Dict[str, Any]  # stability_range_f, stability_duration_min, max_duration_min, etc.


class RecipeCreate(BaseModel):
    """Schema for creating a new recipe."""
    name: str
    description: Optional[str] = None
    phases: List[PhaseConfig]


class RecipeUpdate(BaseModel):
    """Schema for updating a recipe."""
    name: Optional[str] = None
    description: Optional[str] = None
    phases: Optional[List[PhaseConfig]] = None


@router.get("")
async def list_recipes(include_user: bool = True):
    """Get list of cooking recipes."""
    try:
        with get_session_sync() as session:
            # Get system recipes
            statement = select(CookingRecipe).where(CookingRecipe.is_system == True).order_by(CookingRecipe.name)
            system_recipes = session.exec(statement).all()
            
            user_recipes = []
            if include_user:
                # Get user recipes
                statement = select(CookingRecipe).where(CookingRecipe.is_system == False).order_by(CookingRecipe.name)
                user_recipes = session.exec(statement).all()
            
            all_recipes = list(system_recipes) + list(user_recipes)
            
            return {
                "recipes": [
                    {
                        "id": recipe.id,
                        "name": recipe.name,
                        "description": recipe.description,
                        "phases": json.loads(recipe.phases),
                        "is_system": recipe.is_system,
                        "created_at": recipe.created_at.isoformat(),
                        "updated_at": recipe.updated_at.isoformat(),
                    }
                    for recipe in all_recipes
                ]
            }
    except Exception as e:
        logger.error(f"Failed to list recipes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list recipes: {str(e)}")


@router.get("/{recipe_id}")
async def get_recipe(recipe_id: int):
    """Get a specific recipe."""
    try:
        with get_session_sync() as session:
            recipe = session.get(CookingRecipe, recipe_id)
            if not recipe:
                raise HTTPException(status_code=404, detail="Recipe not found")
            
            return {
                "id": recipe.id,
                "name": recipe.name,
                "description": recipe.description,
                "phases": json.loads(recipe.phases),
                "is_system": recipe.is_system,
                "created_at": recipe.created_at.isoformat(),
                "updated_at": recipe.updated_at.isoformat(),
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get recipe: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recipe: {str(e)}")


@router.post("")
async def create_recipe(recipe_create: RecipeCreate):
    """Create a new custom recipe."""
    try:
        with get_session_sync() as session:
            # Validate phases
            phases_data = [phase.dict() for phase in recipe_create.phases]
            
            recipe = CookingRecipe(
                name=recipe_create.name,
                description=recipe_create.description,
                phases=json.dumps(phases_data),
                is_system=False
            )
            session.add(recipe)
            session.commit()
            session.refresh(recipe)
            
            logger.info(f"Created custom recipe: {recipe.name} (ID={recipe.id})")
            
            return {
                "status": "success",
                "message": f"Recipe '{recipe.name}' created",
                "recipe": {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "phases": json.loads(recipe.phases),
                    "is_system": recipe.is_system
                }
            }
    except Exception as e:
        logger.error(f"Failed to create recipe: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create recipe: {str(e)}")


@router.put("/{recipe_id}")
async def update_recipe(recipe_id: int, recipe_update: RecipeUpdate):
    """Update a custom recipe (system recipes cannot be modified)."""
    try:
        with get_session_sync() as session:
            recipe = session.get(CookingRecipe, recipe_id)
            if not recipe:
                raise HTTPException(status_code=404, detail="Recipe not found")
            
            if recipe.is_system:
                raise HTTPException(status_code=400, detail="Cannot modify system recipes. Clone it to create a custom version.")
            
            if recipe_update.name is not None:
                recipe.name = recipe_update.name
            if recipe_update.description is not None:
                recipe.description = recipe_update.description
            if recipe_update.phases is not None:
                phases_data = [phase.dict() for phase in recipe_update.phases]
                recipe.phases = json.dumps(phases_data)
            
            recipe.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(recipe)
            
            logger.info(f"Updated recipe: {recipe.name} (ID={recipe.id})")
            
            return {
                "status": "success",
                "message": "Recipe updated",
                "recipe": {
                    "id": recipe.id,
                    "name": recipe.name,
                    "description": recipe.description,
                    "phases": json.loads(recipe.phases),
                    "is_system": recipe.is_system
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update recipe: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update recipe: {str(e)}")


@router.delete("/{recipe_id}")
async def delete_recipe(recipe_id: int):
    """Delete a custom recipe (system recipes cannot be deleted)."""
    try:
        with get_session_sync() as session:
            recipe = session.get(CookingRecipe, recipe_id)
            if not recipe:
                raise HTTPException(status_code=404, detail="Recipe not found")
            
            if recipe.is_system:
                raise HTTPException(status_code=400, detail="Cannot delete system recipes")
            
            recipe_name = recipe.name
            session.delete(recipe)
            session.commit()
            
            logger.info(f"Deleted recipe: {recipe_name} (ID={recipe_id})")
            
            return {
                "status": "success",
                "message": f"Recipe '{recipe_name}' deleted"
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete recipe: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete recipe: {str(e)}")


@router.post("/{recipe_id}/clone")
async def clone_recipe(recipe_id: int, name: Optional[str] = None):
    """Clone a recipe (useful for customizing system recipes)."""
    try:
        with get_session_sync() as session:
            original_recipe = session.get(CookingRecipe, recipe_id)
            if not original_recipe:
                raise HTTPException(status_code=404, detail="Recipe not found")
            
            # Create new recipe with same phases
            new_name = name if name else f"{original_recipe.name} (Copy)"
            new_recipe = CookingRecipe(
                name=new_name,
                description=original_recipe.description,
                phases=original_recipe.phases,  # Copy JSON as-is
                is_system=False
            )
            session.add(new_recipe)
            session.commit()
            session.refresh(new_recipe)
            
            logger.info(f"Cloned recipe {original_recipe.name} -> {new_name} (ID={new_recipe.id})")
            
            return {
                "status": "success",
                "message": f"Recipe cloned as '{new_name}'",
                "recipe": {
                    "id": new_recipe.id,
                    "name": new_recipe.name,
                    "description": new_recipe.description,
                    "phases": json.loads(new_recipe.phases),
                    "is_system": new_recipe.is_system
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clone recipe: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clone recipe: {str(e)}")


def seed_default_recipes():
    """Create default system recipes if they don't exist."""
    try:
        with get_session_sync() as session:
            # Check if we already have system recipes
            statement = select(CookingRecipe).where(CookingRecipe.is_system == True)
            existing = session.exec(statement).first()
            if existing:
                logger.info("System recipes already exist, skipping seed")
                return
            
            # Define default recipes
            default_recipes = [
                {
                    "name": "Brisket",
                    "description": "Low and slow brisket - 12-16 hours at 225°F",
                    "phases": [
                        {
                            "phase_name": "preheat",
                            "phase_order": 0,
                            "target_temp_f": 270.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 10,
                                "max_duration_min": 60
                            }
                        },
                        {
                            "phase_name": "load_recover",
                            "phase_order": 1,
                            "target_temp_f": 225.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 5,
                                "max_duration_min": 30
                            }
                        },
                        {
                            "phase_name": "smoke",
                            "phase_order": 2,
                            "target_temp_f": 225.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 165.0,
                                "max_duration_min": 600
                            }
                        },
                        {
                            "phase_name": "stall",
                            "phase_order": 3,
                            "target_temp_f": 240.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 180.0,
                                "max_duration_min": 360
                            }
                        },
                        {
                            "phase_name": "finish_hold",
                            "phase_order": 4,
                            "target_temp_f": 160.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 203.0,
                                "max_duration_min": 240
                            }
                        }
                    ]
                },
                {
                    "name": "Ribs",
                    "description": "Competition style ribs - 5-6 hours at 225-250°F",
                    "phases": [
                        {
                            "phase_name": "preheat",
                            "phase_order": 0,
                            "target_temp_f": 265.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 5,
                                "max_duration_min": 45
                            }
                        },
                        {
                            "phase_name": "load_recover",
                            "phase_order": 1,
                            "target_temp_f": 225.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 5,
                                "max_duration_min": 20
                            }
                        },
                        {
                            "phase_name": "smoke",
                            "phase_order": 2,
                            "target_temp_f": 225.0,
                            "completion_conditions": {
                                "max_duration_min": 180
                            }
                        },
                        {
                            "phase_name": "finish_hold",
                            "phase_order": 3,
                            "target_temp_f": 250.0,
                            "completion_conditions": {
                                "max_duration_min": 120
                            }
                        }
                    ]
                },
                {
                    "name": "Pork Shoulder",
                    "description": "Pulled pork - 12-14 hours at 225°F",
                    "phases": [
                        {
                            "phase_name": "preheat",
                            "phase_order": 0,
                            "target_temp_f": 270.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 10,
                                "max_duration_min": 60
                            }
                        },
                        {
                            "phase_name": "load_recover",
                            "phase_order": 1,
                            "target_temp_f": 225.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 5,
                                "max_duration_min": 30
                            }
                        },
                        {
                            "phase_name": "smoke",
                            "phase_order": 2,
                            "target_temp_f": 225.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 160.0,
                                "max_duration_min": 540
                            }
                        },
                        {
                            "phase_name": "stall",
                            "phase_order": 3,
                            "target_temp_f": 240.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 180.0,
                                "max_duration_min": 300
                            }
                        },
                        {
                            "phase_name": "finish_hold",
                            "phase_order": 4,
                            "target_temp_f": 160.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 195.0,
                                "max_duration_min": 180
                            }
                        }
                    ]
                },
                {
                    "name": "Chicken",
                    "description": "Smoked whole chicken - 3-4 hours at 250°F",
                    "phases": [
                        {
                            "phase_name": "preheat",
                            "phase_order": 0,
                            "target_temp_f": 265.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 5,
                                "max_duration_min": 45
                            }
                        },
                        {
                            "phase_name": "load_recover",
                            "phase_order": 1,
                            "target_temp_f": 250.0,
                            "completion_conditions": {
                                "stability_range_f": 5.0,
                                "stability_duration_min": 5,
                                "max_duration_min": 20
                            }
                        },
                        {
                            "phase_name": "smoke",
                            "phase_order": 2,
                            "target_temp_f": 250.0,
                            "completion_conditions": {
                                "meat_temp_threshold_f": 165.0,
                                "max_duration_min": 240
                            }
                        }
                    ]
                }
            ]
            
            # Create each recipe
            for recipe_data in default_recipes:
                recipe = CookingRecipe(
                    name=recipe_data["name"],
                    description=recipe_data["description"],
                    phases=json.dumps(recipe_data["phases"]),
                    is_system=True
                )
                session.add(recipe)
            
            session.commit()
            logger.info(f"Created {len(default_recipes)} default system recipes")
            
    except Exception as e:
        logger.error(f"Failed to seed default recipes: {e}")

