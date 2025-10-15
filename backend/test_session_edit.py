"""
Test script for session edit functionality.
Run this with an active session to verify the edit feature works.
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api"


def test_session_edit():
    """Test editing session parameters."""
    
    # 1. Get current smokes
    logger.info("1. Fetching current smoke sessions...")
    response = requests.get(f"{BASE_URL}/smokes?limit=10")
    if response.status_code != 200:
        logger.error(f"Failed to get smokes: {response.status_code}")
        return False
    
    smokes_data = response.json()
    logger.info(f"Found {len(smokes_data['smokes'])} smoke sessions")
    
    # Find active session
    active_smoke = None
    for smoke in smokes_data['smokes']:
        if smoke.get('is_active'):
            active_smoke = smoke
            break
    
    if not active_smoke:
        logger.warning("No active session found. Creating a test session...")
        
        # Get recipes first
        recipes_response = requests.get(f"{BASE_URL}/recipes")
        if recipes_response.status_code != 200:
            logger.error("Failed to get recipes")
            return False
        
        recipes = recipes_response.json()['recipes']
        if not recipes:
            logger.error("No recipes available")
            return False
        
        # Create a test session
        create_data = {
            "name": "Test Session for Edit Feature",
            "description": "Testing session edit functionality",
            "recipe_id": recipes[0]['id'],
            "preheat_temp_f": 270.0,
            "cook_temp_f": 225.0,
            "finish_temp_f": 160.0,
            "meat_target_temp_f": 195.0,
            "meat_probe_tc_id": None,
            "enable_stall_detection": True
        }
        
        create_response = requests.post(f"{BASE_URL}/smokes", json=create_data)
        if create_response.status_code != 200:
            logger.error(f"Failed to create test session: {create_response.status_code}")
            logger.error(create_response.text)
            return False
        
        result = create_response.json()
        active_smoke = result['smoke']
        logger.info(f"Created test session: {active_smoke['name']} (ID: {active_smoke['id']})")
    else:
        logger.info(f"Found active session: {active_smoke['name']} (ID: {active_smoke['id']})")
    
    smoke_id = active_smoke['id']
    
    # 2. Display current settings
    logger.info("\n2. Current session settings:")
    logger.info(f"   Name: {active_smoke['name']}")
    logger.info(f"   Description: {active_smoke.get('description', 'None')}")
    logger.info(f"   Meat Target Temp: {active_smoke.get('meat_target_temp_f', 'Not set')}°F")
    logger.info(f"   Meat Probe TC ID: {active_smoke.get('meat_probe_tc_id', 'Not set')}")
    
    # 3. Update session settings
    logger.info("\n3. Updating session settings...")
    update_data = {
        "name": f"{active_smoke['name']} (Updated)",
        "description": "This session was updated via API test",
        "meat_target_temp_f": 203.0,
        "meat_probe_tc_id": 1,  # Assuming thermocouple 1 exists
        "preheat_temp_f": 275.0,
        "cook_temp_f": 230.0,
        "finish_temp_f": 165.0,
        "enable_stall_detection": True
    }
    
    update_response = requests.put(f"{BASE_URL}/smokes/{smoke_id}", json=update_data)
    if update_response.status_code != 200:
        logger.error(f"Failed to update session: {update_response.status_code}")
        logger.error(update_response.text)
        return False
    
    updated_smoke = update_response.json()['smoke']
    logger.info("✓ Session updated successfully")
    
    # 4. Verify changes
    logger.info("\n4. Verifying updated settings:")
    logger.info(f"   Name: {updated_smoke['name']}")
    logger.info(f"   Description: {updated_smoke.get('description', 'None')}")
    logger.info(f"   Meat Target Temp: {updated_smoke.get('meat_target_temp_f', 'Not set')}°F")
    logger.info(f"   Meat Probe TC ID: {updated_smoke.get('meat_probe_tc_id', 'Not set')}")
    logger.info(f"   Preheat Temp: {updated_smoke.get('preheat_temp_f', 'Not set')}°F")
    logger.info(f"   Cook Temp: {updated_smoke.get('cook_temp_f', 'Not set')}°F")
    logger.info(f"   Finish Temp: {updated_smoke.get('finish_temp_f', 'Not set')}°F")
    logger.info(f"   Stall Detection: {updated_smoke.get('enable_stall_detection', 'Not set')}")
    
    # Validate changes
    success = True
    if "(Updated)" not in updated_smoke['name']:
        logger.error("✗ Name was not updated")
        success = False
    if updated_smoke.get('meat_target_temp_f') != 203.0:
        logger.error("✗ Meat target temp was not updated")
        success = False
    if updated_smoke.get('meat_probe_tc_id') != 1:
        logger.error("✗ Meat probe ID was not updated")
        success = False
    if updated_smoke.get('preheat_temp_f') != 275.0:
        logger.error("✗ Preheat temp was not updated")
        success = False
    if updated_smoke.get('cook_temp_f') != 230.0:
        logger.error("✗ Cook temp was not updated")
        success = False
    if updated_smoke.get('finish_temp_f') != 165.0:
        logger.error("✗ Finish temp was not updated")
        success = False
    if updated_smoke.get('enable_stall_detection') != True:
        logger.error("✗ Stall detection was not updated")
        success = False
    
    if success:
        logger.info("\n✓ All tests passed! Session edit feature is working correctly.")
    else:
        logger.error("\n✗ Some tests failed. Check the logs above.")
    
    return success


def test_partial_update():
    """Test updating only specific fields."""
    logger.info("\n5. Testing partial updates (only meat target temp)...")
    
    # Get active session
    response = requests.get(f"{BASE_URL}/smokes?limit=1")
    if response.status_code != 200:
        logger.error("Failed to get smokes")
        return False
    
    smokes_data = response.json()
    active_smoke = None
    for smoke in smokes_data['smokes']:
        if smoke.get('is_active'):
            active_smoke = smoke
            break
    
    if not active_smoke:
        logger.warning("No active session for partial update test")
        return True  # Skip this test
    
    smoke_id = active_smoke['id']
    original_name = active_smoke['name']
    
    # Update only meat target temp
    update_data = {
        "meat_target_temp_f": 200.0
    }
    
    update_response = requests.put(f"{BASE_URL}/smokes/{smoke_id}", json=update_data)
    if update_response.status_code != 200:
        logger.error(f"Failed to update session: {update_response.status_code}")
        return False
    
    updated_smoke = update_response.json()['smoke']
    
    # Verify only target temp changed
    if updated_smoke['name'] != original_name:
        logger.error("✗ Name changed when it shouldn't have")
        return False
    
    if updated_smoke.get('meat_target_temp_f') != 200.0:
        logger.error("✗ Meat target temp was not updated")
        return False
    
    logger.info("✓ Partial update works correctly")
    return True


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Session Edit Feature Test")
    logger.info("=" * 60)
    logger.info("Make sure the backend server is running on localhost:8000")
    logger.info("")
    
    try:
        # Run tests
        test1_passed = test_session_edit()
        test2_passed = test_partial_update()
        
        logger.info("\n" + "=" * 60)
        if test1_passed and test2_passed:
            logger.info("ALL TESTS PASSED ✓")
        else:
            logger.info("SOME TESTS FAILED ✗")
        logger.info("=" * 60)
        
    except requests.exceptions.ConnectionError:
        logger.error("\n✗ Cannot connect to backend server.")
        logger.error("Make sure the server is running: cd backend && poetry run python app.py")
    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

