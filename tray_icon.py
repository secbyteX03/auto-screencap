"""
System tray icon and notification functionality for auto-screencap.
"""
import logging
import os
import sys
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger("auto-screencap.tray")

# Try to import optional dependencies
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("Pillow not available. Tray icon will be disabled.")

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    logger.warning("pystray not available. System tray will be disabled.")

try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False
    logger.warning("plyer not available. Desktop notifications will be disabled.")

class TrayIcon:
    """Handles system tray icon and notifications."""
    
    def __init__(self, config: Dict[str, Any], on_quit: Callable[[], None]):
        """Initialize the tray icon.
        
        Args:
            config: Application configuration
            on_quit: Callback function to call when quitting from the tray
        """
        self.config = config
        self.on_quit_callback = on_quit
        self._icon = None
        self._enabled = False
        
    @property
    def available(self) -> bool:
        """Check if system tray functionality is available."""
        return HAS_PIL and HAS_PYSTRAY and self.config.get("enable_tray", True)
    
    def start(self) -> bool:
        """Start the system tray icon.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if not self.available:
            logger.debug("Tray icon not available (missing dependencies or disabled in config)")
            return False
            
        try:
            # Create an image for the icon
            image = self._create_icon_image()
            
            # Create the menu
            menu = self._create_menu()
            
            # Create the icon
            self._icon = pystray.Icon("auto-screencap", image, "Auto Screenshot", menu)
            
            # Start the icon in a separate thread
            import threading
            thread = threading.Thread(target=self._run_icon, daemon=True)
            thread.start()
            
            self._enabled = True
            logger.info("Started system tray icon")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start system tray: {e}", exc_info=True)
            return False
    
    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        self._enabled = False
        logger.info("Stopped system tray icon")
    
    def show_notification(self, title: str, message: str) -> bool:
        """Show a desktop notification.
        
        Args:
            title: Notification title
            message: Notification message
            
        Returns:
            bool: True if notification was shown, False otherwise
        """
        if not HAS_PLYER or not self.config.get("enable_notifications", True):
            return False
            
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Auto Screenshot",
                timeout=5  # seconds
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to show notification: {e}")
            return False
    
    def _run_icon(self) -> None:
        """Run the system tray icon (blocking)."""
        try:
            self._icon.run()
        except Exception as e:
            logger.error(f"Error in tray icon thread: {e}", exc_info=True)
    
    def _create_icon_image(self):
        """Create an image for the system tray icon."""
        # Create a new image with a transparent background
        width = 64
        height = 64
        color = "#3498db"  # Blue color
        
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # Draw a simple camera icon
        dc.ellipse((10, 10, width-10, height-10), fill=color)
        dc.ellipse((20, 20, width-20, height-20), fill="white")
        
        return image
    
    def _create_menu(self) -> pystray.Menu:
        """Create the system tray menu."""
        from pystray import MenuItem as item
        
        # Define menu items
        menu_items = [
            item('Auto Screenshot', None, enabled=False),  # Title
            item('---', None, enabled=False),  # Separator
            item('Pause Capture', self._on_pause_resume),
            item('Take Screenshot Now', self._on_capture_now),
            item('Open Screenshots Folder', self._on_open_folder),
            item('---', None, enabled=False),  # Separator
            item('Quit', self._on_quit)
        ]
        
        return pystray.Menu(*menu_items)
    
    def _on_pause_resume(self, icon, item) -> None:
        """Handle pause/resume menu item click."""
        # This will be implemented in the main application
        logger.debug("Pause/Resume clicked")
        self.show_notification("Pause/Resume", "This feature will be implemented in the main application")
    
    def _on_capture_now(self, icon, item) -> None:
        """Handle capture now menu item click."""
        # This will be implemented in the main application
        logger.debug("Capture Now clicked")
        self.show_notification("Capture Now", "Taking screenshot now...")
    
    def _on_open_folder(self, icon, item) -> None:
        """Handle open folder menu item click."""
        try:
            import subprocess
            import platform
            import os
            
            screenshots_dir = os.path.expanduser(self.config.get("save_path", "screenshots"))
            
            # Create the directory if it doesn't exist
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Open the folder using the appropriate command for the OS
            if platform.system() == 'Windows':
                os.startfile(screenshots_dir)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', screenshots_dir])
            else:  # Linux and others
                subprocess.Popen(['xdg-open', screenshots_dir])
                
        except Exception as e:
            logger.error(f"Failed to open screenshots folder: {e}")
            self.show_notification("Error", f"Failed to open folder: {e}")
    
    def _on_quit(self, icon, item) -> None:
        """Handle quit menu item click."""
        logger.info("Quit requested from system tray")
        self.stop()
        if callable(self.on_quit_callback):
            self.on_quit_callback()
