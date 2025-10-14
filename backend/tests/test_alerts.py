"""Tests for alert system."""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from core.alerts import AlertManager


class TestAlertManager:
    """Test alert manager functionality."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create an alert manager instance for testing."""
        return AlertManager()
    
    @pytest.mark.asyncio
    async def test_high_temp_alert(self, alert_manager):
        """Test high temperature alert creation."""
        # Mock database session
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Test high temperature condition
            status = {
                'current_temp_c': 140.0,  # Above threshold
                'relay_state': True
            }
            
            await alert_manager.check_alerts(status)
            
            # Should create an alert
            assert 'high_temp' in alert_manager.active_alerts
    
    @pytest.mark.asyncio
    async def test_low_temp_alert(self, alert_manager):
        """Test low temperature alert creation."""
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Test low temperature condition
            status = {
                'current_temp_c': 60.0,  # Below threshold
                'relay_state': False
            }
            
            await alert_manager.check_alerts(status)
            
            # Should create an alert
            assert 'low_temp' in alert_manager.active_alerts
    
    @pytest.mark.asyncio
    async def test_sensor_fault_alert(self, alert_manager):
        """Test sensor fault alert creation."""
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Test sensor fault condition
            status = {
                'current_temp_c': None,  # Sensor fault
                'relay_state': False
            }
            
            await alert_manager.check_alerts(status)
            
            # Should create an alert
            assert 'sensor_fault' in alert_manager.active_alerts
    
    @pytest.mark.asyncio
    async def test_alert_acknowledgment(self, alert_manager):
        """Test alert acknowledgment."""
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_alert = Mock()
            mock_alert.id = 1
            mock_alert.active = True
            mock_alert.acknowledged = False
            mock_db.get.return_value = mock_alert
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Acknowledge alert
            result = await alert_manager.acknowledge_alert(1)
            
            assert result is True
            assert mock_alert.acknowledged is True
    
    @pytest.mark.asyncio
    async def test_alert_clearing(self, alert_manager):
        """Test alert clearing."""
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_alert = Mock()
            mock_alert.id = 1
            mock_alert.active = True
            mock_db.get.return_value = mock_alert
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Clear alert
            result = await alert_manager.clear_alert(1)
            
            assert result is True
            assert mock_alert.active is False
            assert mock_alert.cleared_ts is not None
    
    @pytest.mark.asyncio
    async def test_alert_debouncing(self, alert_manager):
        """Test alert debouncing."""
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # First alert creation
            status = {'current_temp_c': 140.0, 'relay_state': True}
            await alert_manager.check_alerts(status)
            
            # Immediate second check should not create another alert
            initial_count = len(alert_manager.active_alerts)
            await alert_manager.check_alerts(status)
            
            # Should still have same number of alerts (debounced)
            assert len(alert_manager.active_alerts) == initial_count
    
    @pytest.mark.asyncio
    async def test_alert_auto_clear(self, alert_manager):
        """Test automatic alert clearing when condition resolves."""
        with patch('backend.core.alerts.get_session_sync') as mock_session:
            mock_db = Mock()
            mock_session.return_value.__enter__.return_value = mock_db
            
            # Create high temp alert
            status = {'current_temp_c': 140.0, 'relay_state': True}
            await alert_manager.check_alerts(status)
            assert 'high_temp' in alert_manager.active_alerts
            
            # Resolve condition
            status = {'current_temp_c': 120.0, 'relay_state': True}
            await alert_manager.check_alerts(status)
            
            # Alert should be cleared
            assert 'high_temp' not in alert_manager.active_alerts
    
    @pytest.mark.asyncio
    async def test_alert_summary(self, alert_manager):
        """Test alert summary generation."""
        # Mock some active alerts
        alert_manager.active_alerts = {
            'alert1': Mock(severity='critical'),
            'alert2': Mock(severity='error'),
            'alert3': Mock(severity='warning'),
            'alert4': Mock(severity='info', acknowledged=False),
            'alert5': Mock(severity='info', acknowledged=True),
        }
        
        summary = await alert_manager.get_alert_summary()
        
        assert summary['count'] == 5
        assert summary['critical'] == 1
        assert summary['error'] == 1
        assert summary['warning'] == 1
        assert summary['info'] == 2
        assert summary['unacknowledged'] == 4  # All except alert5
