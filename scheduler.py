"""
Scheduling functionality for auto-screencap.
Handles work hours and scheduling of screenshot captures.
"""
import time
from datetime import datetime, time as dt_time, timedelta
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("auto-screencap.scheduler")

class Scheduler:
    """Handles scheduling of screenshot captures based on work hours."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the scheduler with configuration.
        
        Args:
            config: Configuration dictionary with work_hours settings
        """
        self.config = config
        self._last_capture_time: Optional[datetime] = None
        
    def is_within_work_hours(self) -> bool:
        """Check if current time is within configured work hours.
        
        Returns:
            bool: True if within work hours, False otherwise
        """
        work_hours = self.config.get("work_hours", {})
        if not work_hours.get("enabled", False):
            return True
            
        try:
            now = datetime.now().time()
            start_time = self._parse_time(work_hours.get("start", "09:00"))
            end_time = self._parse_time(work_hours.get("end", "17:00"))
            
            # Handle overnight work hours (e.g., 22:00-06:00)
            if start_time < end_time:
                return start_time <= now <= end_time
            else:
                return now >= start_time or now <= end_time
                
        except Exception as e:
            logger.error(f"Error checking work hours: {e}")
            return True  # Default to allowing captures if there's an error
    
    def should_capture(self, interval: int) -> bool:
        """Determine if a screenshot should be captured now.
        
        Args:
            interval: Capture interval in seconds
            
        Returns:
            bool: True if a screenshot should be captured, False otherwise
        """
        if not self.is_within_work_hours():
            return False
            
        current_time = datetime.now()
        
        # If we've never captured before, capture now
        if self._last_capture_time is None:
            self._last_capture_time = current_time
            return True
            
        # Check if enough time has passed since the last capture
        time_since_last = (current_time - self._last_capture_time).total_seconds()
        if time_since_last >= interval:
            self._last_capture_time = current_time
            return True
            
        return False
    
    def time_until_next_capture(self, interval: int) -> float:
        """Calculate time in seconds until the next scheduled capture.
        
        Args:
            interval: Capture interval in seconds
            
        Returns:
            float: Seconds until next capture, or 0 if should capture now
        """
        if self._last_capture_time is None:
            return 0
            
        if not self.is_within_work_hours():
            return self._time_until_work_hours_start()
            
        current_time = datetime.now()
        time_since_last = (current_time - self._last_capture_time).total_seconds()
        
        if time_since_last >= interval:
            return 0
            
        return interval - time_since_last
    
    def _time_until_work_hours_start(self) -> float:
        """Calculate time in seconds until work hours start.
        
        Returns:
            float: Seconds until work hours start, or 0 if already in work hours
        """
        work_hours = self.config.get("work_hours", {})
        if not work_hours.get("enabled", False):
            return 0
            
        try:
            now = datetime.now()
            start_time = self._parse_time(work_hours.get("start", "09:00"))
            
            # Create a datetime for today with the start time
            start_dt = datetime.combine(now.date(), start_time)
            
            # If we're already past the start time today, check if we need to wrap to tomorrow
            if now.time() > start_time:
                start_dt += timedelta(days=1)
                
            return (start_dt - now).total_seconds()
            
        except Exception as e:
            logger.error(f"Error calculating time until work hours: {e}")
            return 300  # Default to 5 minutes if there's an error
    
    @staticmethod
    def _parse_time(time_str: str) -> dt_time:
        """Parse a time string in HH:MM format to a time object.
        
        Args:
            time_str: Time string in HH:MM format
            
        Returns:
            time: Parsed time object
            
        Raises:
            ValueError: If the time string is in an invalid format
        """
        try:
            return dt_time(*map(int, time_str.split(':')))
        except (ValueError, AttributeError) as e:
            logger.error(f"Invalid time format: {time_str}. Expected HH:MM")
            raise ValueError(f"Invalid time format: {time_str}. Expected HH:MM") from e
