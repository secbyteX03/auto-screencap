import os
import time
import shutil
import logging
from datetime import datetime, timedelta
import pytest
import json
from unittest.mock import patch, MagicMock, ANY

# Add parent directory to path so we can import main
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import ScreenshotTool, load_config, save_config, setup_logging

# Test data
TEST_CONFIG = {
    "interval": 300,
    "mode": "fullscreen",
    "target_window": "",
    "custom_region": None,
    "save_path": "test_screenshots",
    "image_format": "png",
    "jpg_quality": 85,
    "max_retention_days": 1,  # 1 day for testing
    "work_hours": {
        "enabled": False,
        "start": "09:00",
        "end": "17:00"
    },
    "enable_tray": False,
    "enable_notifications": False,
    "enable_face_blur": False,
    "log_level": "DEBUG"
}

# Fixtures
@pytest.fixture
def test_config_file(tmp_path):
    config_path = tmp_path / "test_config.json"
    with open(config_path, 'w') as f:
        json.dump(TEST_CONFIG, f)
    return config_path

@pytest.fixture
def test_save_dir():
    """Fixture that provides a test directory for saving screenshots"""
    test_dir = "test_screenshots"
    os.makedirs(test_dir, exist_ok=True)
    yield test_dir
    # Cleanup after test
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)

class TestScreenshotTool:
    def test_config_loading(self, test_config_file):
        """Test that config loads correctly from file"""
        config = load_config(test_config_file)
        assert config["interval"] == 300
        assert config["image_format"] == "png"
        assert config["work_hours"]["enabled"] is False

    def test_config_saving(self, tmp_path):
        """Test that config saves correctly to file"""
        config_path = tmp_path / "test_save_config.json"
        save_config(TEST_CONFIG, config_path)
        
        assert os.path.exists(config_path)
        with open(config_path, 'r') as f:
            saved_config = json.load(f)
        assert saved_config["interval"] == TEST_CONFIG["interval"]

    def test_retention_cleanup(self, tmp_path):
        """Test that old screenshots are cleaned up"""
        # Create test directory
        test_dir = tmp_path / "screenshots"
        test_dir.mkdir()
        
        # Create test files with different modification times
        now = time.time()
        
        # File older than retention period (2 days old)
        old_file = test_dir / "old_screenshot.png"
        old_file.touch()
        old_time = now - (2 * 24 * 3600)  # 2 days old
        os.utime(old_file, (old_time, old_time))
        
        # File within retention period (6 hours old)
        new_file = test_dir / "new_screenshot.png"
        new_file.touch()
        new_time = now - (6 * 3600)  # 6 hours old
        os.utime(new_file, (new_time, new_time))
        
        # Initialize tool with test config
        config = TEST_CONFIG.copy()
        config["save_path"] = str(test_dir)
        config["max_retention_days"] = 1  # 1 day retention
        
        tool = ScreenshotTool()
        tool.config = config
        tool.screenshots_dir = str(test_dir)
        
        # Run cleanup
        tool._cleanup_old_screenshots()
        
        # Verify old file was deleted, new file remains
        assert not os.path.exists(old_file)
        assert os.path.exists(new_file)

    def test_filename_format(self):
        """Test screenshot filename formatting"""
        tool = ScreenshotTool()
        tool.config = TEST_CONFIG
        tool.screenshots_dir = "screenshots"
        
        # Test with current time
        test_time = datetime(2023, 1, 1, 12, 30, 45)
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time
            filename = tool._get_screenshot_filename()
            
        assert filename.startswith("screenshots/screenshot_2023-01-01_12-30-45")
        assert filename.endswith(".png")  # Default format
        
        # Test with custom format
        tool.config["image_format"] = "jpg"
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = test_time
            filename = tool._get_screenshot_filename()
        assert filename.endswith(".jpg")

    def test_work_hours_check(self):
        """Test work hours checking logic"""
        tool = ScreenshotTool()
        tool.config = TEST_CONFIG.copy()
        tool.config["work_hours"]["enabled"] = True
        
        # Test during work hours
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 12, 0)  # 12 PM
            assert tool._is_within_work_hours() is True
        
        # Test before work hours
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 8, 0)  # 8 AM
            assert tool._is_within_work_hours() is False
        
        # Test after work hours
        with patch('datetime.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 18, 0)  # 6 PM
            assert tool._is_within_work_hours() is False

    def test_face_blur_optional(self):
        """Test that face blur is optional and fails gracefully"""
        tool = ScreenshotTool()
        tool.config = TEST_CONFIG.copy()
        tool.config["enable_face_blur"] = True
        
        # Mock OpenCV import error
        with patch.dict('sys.modules', {'cv2': None}), \
             patch.object(logging.Logger, 'warning') as mock_warning:
            # Create a test image
            from PIL import Image
            test_img = Image.new('RGB', (100, 100), color='white')
            
            # Should not raise an exception
            result = tool._blur_faces(test_img)
            
            # Should return the original image
            assert result == test_img
            # Should log a warning about missing OpenCV
            mock_warning.assert_called_with(ANY)

    def test_tray_icon_optional(self):
        """Test that tray icon is optional and fails gracefully"""
        tool = ScreenshotTool()
        tool.config = TEST_CONFIG.copy()
        tool.config["enable_tray"] = True
        
        # Mock pystray import error
        with patch.dict('sys.modules', {'pystray': None}), \
             patch.object(logging.Logger, 'error') as mock_error:
            # Should not raise an exception
            tool._setup_tray_icon()
            assert tool.tray_icon is None  # Tray should be disabled
            # Should log an error about missing pystray
            mock_error.assert_called_with(ANY)

def test_logging_setup(tmp_path):
    """Test logging setup with rotation"""
    # Test with debug level
    logger = setup_logging("DEBUG")
    assert logger.level == logging.DEBUG
    
    # Test log file creation
    log_dir = tmp_path / "logs"
    log_file = log_dir / "test.log"
    
    with patch('os.path.join', return_value=str(log_file)) as mock_join, \
         patch('os.makedirs') as mock_makedirs:
        setup_logging()
        mock_makedirs.assert_called_once_with(str(log_dir), exist_ok=True)
    
    # Test invalid log level falls back to INFO
    logger = setup_logging("INVALID_LEVEL")
    assert logger.level == logging.INFO


def test_cleanup_thread_lifecycle():
    """Test the cleanup thread starts and stops correctly"""
    tool = ScreenshotTool()
    tool.config = TEST_CONFIG.copy()
    
    # Mock the cleanup method to avoid actual file operations
    with patch.object(tool, '_cleanup_old_screenshots') as mock_cleanup:
        # Start the cleanup thread
        tool._start_cleanup_thread()
        
        # Verify thread started
        assert tool.cleanup_thread is not None
        assert tool.cleanup_thread.is_alive()
        
        # Stop the thread
        tool.running = False
        tool.cleanup_thread.join(timeout=1.0)
        
        # Verify thread stopped
        assert not tool.cleanup_thread.is_alive()


def test_notification_system():
    """Test the notification system"""
    tool = ScreenshotTool()
    tool.config = TEST_CONFIG.copy()
    tool.config["enable_notifications"] = True
    
    # Mock the notification module
    with patch('plyer.notification.notify') as mock_notify:
        # Test notification with plyer available
        tool._show_notification("Test Title", "Test Message")
        mock_notify.assert_called_once_with(
            title="Test Title",
            message="Test Message",
            app_name="Auto Screenshot",
            timeout=5
        )
    
    # Test with notifications disabled
    tool.config["enable_notifications"] = False
    with patch('plyer.notification.notify') as mock_notify:
        tool._show_notification("Test", "Should not show")
        mock_notify.assert_not_called()


# Helper function tests
def test_load_config_missing_file():
    """Test loading config from non-existent file returns default config"""
    with patch('builtins.open', side_effect=FileNotFoundError()), \
         patch('json.load', side_effect=FileNotFoundError()):
        config = load_config("nonexistent_file.json")
        assert isinstance(config, dict)
        assert "interval" in config

def test_save_config_creates_dir(tmp_path):
    """Test that save_config creates parent directories if needed"""
    config_path = tmp_path / "nonexistent" / "config.json"
    save_config(TEST_CONFIG, config_path)
    assert os.path.exists(config_path)


def test_work_hours_overnight():
    """Test work hours that span midnight"""
    tool = ScreenshotTool()
    tool.config = TEST_CONFIG.copy()
    tool.config["work_hours"]["enabled"] = True
    tool.config["work_hours"]["start"] = "22:00"  # 10 PM
    tool.config["work_hours"]["end"] = "06:00"    # 6 AM
    
    # Test during work hours (overnight)
    with patch('datetime.datetime') as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 1, 23, 0)  # 11 PM
        assert tool._is_within_work_hours() is True
        
        # Test before work hours (evening)
        mock_datetime.now.return_value = datetime(2023, 1, 1, 21, 0)  # 9 PM
        assert tool._is_within_work_hours() is False
        
        # Test after work hours (morning)
        mock_datetime.now.return_value = datetime(2023, 1, 2, 7, 0)  # 7 AM
        assert tool._is_within_work_hours() is False
        
        # Test early morning still in work hours
        mock_datetime.now.return_value = datetime(2023, 1, 2, 5, 0)  # 5 AM
        assert tool._is_within_work_hours() is True


def test_image_format_handling():
    """Test image format handling and quality settings"""
    tool = ScreenshotTool()
    tool.config = TEST_CONFIG.copy()
    
    # Test default format (PNG)
    tool.config["image_format"] = "png"
    filename = tool._get_screenshot_filename()
    assert filename.endswith(".png")
    
    # Test JPG format with quality
    tool.config["image_format"] = "jpg"
    tool.config["jpg_quality"] = 90
    filename = tool._get_screenshot_filename()
    assert filename.endswith(".jpg")
    
    # Test case insensitivity
    tool.config["image_format"] = "JPG"
    filename = tool._get_screenshot_filename()
    assert filename.lower().endswith(".jpg")
