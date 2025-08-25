"""
Unit tests for services layer and dependency management.
"""
import pytest
from unittest.mock import patch, MagicMock
import os

from app import services
from app.config import get_settings


class TestServicesInitialization:
    """Test services are properly initialized."""
    
    def test_settings_initialized(self):
        """Test that settings are properly loaded."""
        settings = get_settings()
        
        assert settings is not None
        assert hasattr(settings, 'environment')
        assert hasattr(settings, 'database_url')
        assert hasattr(settings, 'surge_api_key')
    
    def test_surge_client_initialization(self):
        """Test Surge SMS client initialization."""
        assert services.surge_client is not None
        assert hasattr(services.surge_client, 'send_message')
        assert hasattr(services.surge_client, 'api_key')
        assert hasattr(services.surge_client, 'account_id')
    
    def test_calendar_client_initialization(self):
        """Test calendar client initialization."""
        assert services.calendar_client is not None
        # Should be DirectGoogleCalendarClient based on current implementation
        assert hasattr(services.calendar_client, 'create_event')
    
    def test_meet_client_initialization(self):
        """Test Google Meet client initialization."""
        assert services.meet_client is not None
        assert hasattr(services.meet_client, 'create_meeting')
    
    def test_command_processor_initialization(self):
        """Test LLM command processor initialization."""
        assert services.command_processor is not None
        assert hasattr(services.command_processor, 'process_command_with_llm')
        
        # Should have references to other clients
        assert services.command_processor.sms_client == services.surge_client
        assert services.command_processor.calendar_client == services.calendar_client
        assert services.command_processor.meet_client == services.meet_client
    
    def test_strava_client_placeholder(self):
        """Test that Strava client is properly set as placeholder."""
        assert services.strava_client is None  # Currently a placeholder


class TestConfigurationManagement:
    """Test configuration management and environment handling."""
    
    def test_environment_specific_settings(self):
        """Test that settings respond to environment variables."""
        settings = get_settings()
        
        # Should have testing environment from conftest.py
        assert settings.environment == "testing"
    
    @patch.dict(os.environ, {
        'SURGE_SMS_API_KEY': 'test_surge_key',
        'SURGE_ACCOUNT_ID': 'test_account_id',
        'ANTHROPIC_API_KEY': 'test_anthropic_key'
    })
    def test_api_key_configuration(self):
        """Test API key configuration from environment."""
        # Need to reload settings to pick up new environment
        from app.config import Settings
        test_settings = Settings()
        
        assert test_settings.surge_api_key == 'test_surge_key'
        assert test_settings.surge_account_id == 'test_account_id'
        assert test_settings.anthropic_api_key == 'test_anthropic_key'
    
    def test_database_url_fallback(self):
        """Test database URL fallback behavior."""
        settings = get_settings()
        
        # In testing, should have SQLite fallback or testing URL
        assert settings.database_url is not None
    
    def test_feature_flags(self):
        """Test feature flag configuration."""
        settings = get_settings()
        
        # Test feature flags have proper defaults
        assert isinstance(settings.enable_mcp_calendar, bool)
        assert isinstance(settings.use_real_mcp_calendar, bool)
        assert isinstance(settings.use_direct_google_calendar, bool)


class TestServiceDependencies:
    """Test service dependencies and interactions."""
    
    def test_command_processor_dependencies(self):
        """Test that command processor has all required dependencies."""
        processor = services.command_processor
        
        # Should have all required client dependencies
        assert processor.sms_client is not None
        assert processor.calendar_client is not None
        assert processor.meet_client is not None
        
        # Strava client can be None (optional)
        assert processor.strava_client is None  # Currently None
    
    def test_llm_integration_status(self):
        """Test LLM integration enablement status."""
        processor = services.command_processor
        
        # Should indicate whether LLM is enabled
        assert hasattr(processor, 'llm_enabled')
        assert isinstance(processor.llm_enabled, bool)
        
        # If Anthropic key is available, should be enabled
        if os.getenv('ANTHROPIC_API_KEY'):
            assert processor.llm_enabled
        
        # Should have available tools defined
        assert hasattr(processor, 'available_tools')
        assert isinstance(processor.available_tools, list)
    
    def test_client_configurations(self):
        """Test that clients are configured with proper settings."""
        # Surge client should have API credentials
        surge = services.surge_client
        assert hasattr(surge, 'api_key')
        assert hasattr(surge, 'account_id')
        
        # Calendar client should be properly initialized
        calendar = services.calendar_client
        assert hasattr(calendar, 'create_event')
        
        # Meet client should be properly initialized
        meet = services.meet_client
        assert hasattr(meet, 'create_meeting')


class TestServiceSingletons:
    """Test that services are properly implemented as singletons."""
    
    def test_settings_singleton_behavior(self):
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # Should be the same object due to lru_cache
        assert settings1 is settings2
    
    def test_service_instances_consistency(self):
        """Test that service instances are consistent across imports."""
        # Import services again to test singleton behavior
        from app import services as services2
        
        assert services.surge_client is services2.surge_client
        assert services.calendar_client is services2.calendar_client
        assert services.meet_client is services2.meet_client
        assert services.command_processor is services2.command_processor


class TestServiceErrorHandling:
    """Test service error handling and graceful degradation."""
    
    @patch.dict(os.environ, {'SURGE_SMS_API_KEY': '', 'SURGE_ACCOUNT_ID': ''})
    def test_missing_surge_credentials(self):
        """Test handling of missing Surge SMS credentials."""
        # This should not crash during import, but should handle missing credentials
        from sms_coordinator.surge_client import SurgeSMSClient
        
        # Should initialize with empty strings but not crash
        client = SurgeSMSClient(api_key="", account_id="")
        assert client.api_key == ""
        assert client.account_id == ""
    
    @patch.dict(os.environ, {'ANTHROPIC_API_KEY': ''})
    def test_missing_anthropic_key(self):
        """Test handling of missing Anthropic API key."""
        from llm_integration.enhanced_command_processor import LLMCommandProcessor
        
        # Should gracefully disable LLM features
        processor = LLMCommandProcessor(None, None, None, None)
        assert processor.llm_enabled is False
        assert processor.claude_client is None
    
    def test_service_initialization_with_mocks(self):
        """Test service initialization with mocked dependencies."""
        with patch('sms_coordinator.surge_client.SurgeSMSClient') as mock_surge, \
             patch('google_integrations.direct_google_calendar.DirectGoogleCalendarClient') as mock_calendar, \
             patch('google_integrations.meet_client.GoogleMeetClient') as mock_meet:
            
            # Mock the classes
            mock_surge.return_value = MagicMock()
            mock_calendar.return_value = MagicMock()
            mock_meet.return_value = MagicMock()
            
            # Re-import services to test with mocks
            import importlib
            importlib.reload(services)
            
            # Should not raise any exceptions
            assert services.surge_client is not None
            assert services.calendar_client is not None
            assert services.meet_client is not None


class TestServiceHealthChecks:
    """Test service health check capabilities."""
    
    @pytest.mark.asyncio
    async def test_surge_client_health(self):
        """Test Surge SMS client health check."""
        surge = services.surge_client
        
        # Should have methods for checking health
        assert hasattr(surge, 'api_key')
        assert hasattr(surge, 'account_id')
        
        # API key should be configured (even if test key)
        assert surge.api_key is not None
        assert surge.account_id is not None
    
    def test_calendar_client_health(self):
        """Test calendar client health."""
        calendar = services.calendar_client
        
        # Should have required methods
        assert hasattr(calendar, 'create_event')
        # May have additional methods depending on implementation
    
    def test_llm_processor_health(self):
        """Test LLM processor health."""
        processor = services.command_processor
        
        # Should have proper initialization
        assert hasattr(processor, 'llm_enabled')
        assert hasattr(processor, 'available_tools')
        
        # Should have fallback processing available
        assert hasattr(processor, '_basic_command_processing')