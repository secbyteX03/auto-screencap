"""
Retention and cleanup functionality for auto-screencap.
Handles automatic deletion of old screenshots based on retention policy.
"""
import os
import time
from datetime import datetime, timedelta
import logging
from typing import Optional

logger = logging.getLogger("auto-screencap.retention")

class RetentionManager:
    """Manages retention and cleanup of screenshot files."""
    
    def __init__(self, screenshots_dir: str, max_retention_days: int = 30):
        """Initialize the retention manager.
        
        Args:
            screenshots_dir: Directory where screenshots are stored
            max_retention_days: Maximum age of screenshots to keep (in days)
        """
        self.screenshots_dir = screenshots_dir
        self.max_retention_days = max_retention_days
        self._running = False
        self._cleanup_thread = None
        
    def start_cleanup_thread(self, interval_hours: int = 1) -> None:
        """Start a background thread to periodically clean up old screenshots.
        
        Args:
            interval_hours: How often to run cleanup (in hours)
        """
        if self._running:
            logger.warning("Cleanup thread is already running")
            return
            
        self._running = True
        
        def cleanup_loop():
            while self._running:
                try:
                    self.cleanup_old_screenshots()
                    # Sleep for the interval, checking for stop every minute
                    for _ in range(interval_hours * 60):
                        if not self._running:
                            break
                        time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying on error
        
        import threading
        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            daemon=True,
            name="ScreenshotCleanup"
        )
        self._cleanup_thread.start()
        logger.info(f"Started cleanup thread (runs every {interval_hours} hours)")
    
    def stop_cleanup_thread(self) -> None:
        """Stop the background cleanup thread."""
        if not self._running:
            return
            
        self._running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            self._cleanup_thread = None
        logger.info("Stopped cleanup thread")
    
    def cleanup_old_screenshots(self) -> int:
        """Delete screenshots older than the retention period.
        
        Returns:
            int: Number of files deleted
        """
        if self.max_retention_days <= 0:
            logger.debug("Retention policy disabled (max_retention_days <= 0)")
            return 0
            
        try:
            now = datetime.now()
            cutoff_date = now - timedelta(days=self.max_retention_days)
            deleted_count = 0
            
            if not os.path.exists(self.screenshots_dir):
                logger.warning(f"Screenshots directory does not exist: {self.screenshots_dir}")
                return 0
            
            for filename in os.listdir(self.screenshots_dir):
                if not any(filename.lower().endswith(ext) for ext in ('.png', '.jpg', '.jpeg')):
                    continue
                    
                filepath = os.path.join(self.screenshots_dir, filename)
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < cutoff_date:
                        os.remove(filepath)
                        logger.debug(f"Deleted old screenshot: {filename}")
                        deleted_count += 1
                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old screenshot(s)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
            raise
