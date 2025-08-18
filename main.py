#!/usr/bin/env python3
"""
Automatic Screenshot Tool
Captures screenshots at regular intervals with various options:
- Full screen capture
- Specific application window
- Custom region selection
- Configurable save paths and formats
- Retention policy for old screenshots
- Work hours scheduling
- Optional face blurring for privacy
"""

import os
import sys
import time
import json
import logging
import argparse
import threading

# GUI dependencies
try:
    import tkinter as tk
    from tkinter import messagebox, ttk
    import pyautogui
    import pygetwindow as gw
    from PIL import Image, ImageTk
    HAS_GUI_DEPS = True
except ImportError as e:
    HAS_GUI_DEPS = False
    print(f"Warning: GUI dependencies not available: {e}")
    if '--nogui' not in sys.argv:
        print("Run with --nogui to use command-line mode")
        sys.exit(1)
from datetime import datetime, time as dtime, timedelta
from typing import Optional, Tuple, Dict, Any, Union, List
import platform

def setup_logging(log_level: str = "INFO"):
    """Set up logging configuration with rotation
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    import logging.handlers
    import os
    
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'auto_screencap.log')
    
    # Clear any existing handlers
    logger = logging.getLogger()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Set log level
    log_level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation (10MB per file, keep 5 backups)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info(f"Logging to {log_file}")
    except Exception as e:
        logger.error(f"Failed to set up file logging: {e}")
        logger.warning("Logging to console only")
    
    return logger

# Add TRACE level (level 5, between DEBUG and INFO)
TRACE_LEVEL_NUM = 5
def trace(self, message, *args, **kws):
    if self.isEnabledFor(TRACE_LEVEL_NUM):
        self._log(TRACE_LEVEL_NUM, message, args, **kws)
logging.addLevelName(TRACE_LEVEL_NUM, "TRACE")
logging.Logger.trace = trace

# Initialize logger
logger = logging.getLogger("auto-screencap")

# Optional imports with graceful degradation
try:
    import pyautogui
    import pygetwindow as gw
    from PIL import Image, ImageTk, ImageFilter
    HAS_GUI_DEPS = True
except ImportError as e:
    logger.warning(f"GUI dependencies not available: {e}")
    HAS_GUI_DEPS = False

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    logger.warning("OpenCV not installed. Face blurring will be disabled.")

try:
    import pystray
    from pystray import MenuItem as item
    from PIL import Image as PILImage
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False
    logger.warning("pystray not installed. System tray will be disabled.")

try:
    from plyer import notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False
    logger.warning("plyer not installed. Desktop notifications will be disabled.")

# Default configuration
DEFAULT_CONFIG = {
    "interval": 300,  # 5 minutes
    "mode": "fullscreen",  # fullscreen, window, region
    "target_window": "",
    "custom_region": None,  # [x, y, width, height]
    "save_path": "screenshots",
    "image_format": "png",  # png or jpg
    "jpg_quality": 85,  # 1-100, only for jpg
    "max_retention_days": 30,  # 0 to disable
    "work_hours": {
        "enabled": False,
        "start": "09:00",
        "end": "17:00"
    },
    "enable_tray": True,
    "enable_notifications": True,
    "enable_face_blur": False,
    "log_level": "INFO"
}

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from file or create with defaults if not exists"""
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            # Ensure all default keys exist
            for key, value in DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    # Create default config if file doesn't exist or error occurred
    save_config(DEFAULT_CONFIG, config_path)
    return DEFAULT_CONFIG.copy()

def save_config(config: Dict[str, Any], config_path: str = "config.json"):
    """Save configuration to file"""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Automatic Screenshot Tool')
    
    # General options
    parser.add_argument('--nogui', action='store_true', help='Run in command-line mode without GUI')
    parser.add_argument('--config', default='config.json', help='Path to config file')
    
    # Screenshot options
    parser.add_argument('--interval', type=int, help='Screenshot interval in seconds')
    parser.add_argument('--mode', choices=['fullscreen', 'window', 'region'], help='Screenshot mode')
    parser.add_argument('--window', help='Target window title (for window mode)')
    parser.add_argument('--region', nargs=4, type=int, metavar=('X', 'Y', 'WIDTH', 'HEIGHT'), 
                       help='Custom region coordinates (for region mode)')
    parser.add_argument('--save-path', help='Directory to save screenshots')
    parser.add_argument('--format', choices=['png', 'jpg'], help='Image format')
    parser.add_argument('--quality', type=int, help='JPEG quality (1-100)')
    
    # Schedule options
    parser.add_argument('--work-hours', nargs=2, metavar=('START', 'END'), 
                       help='Work hours in 24h format (e.g., 09:00 17:00)')
    parser.add_argument('--enable-work-hours', action='store_true', 
                       help='Enable work hours filtering')
    
    # Feature toggles
    parser.add_argument('--enable-tray', action='store_true', help='Enable system tray icon')
    parser.add_argument('--disable-tray', action='store_true', help='Disable system tray icon')
    parser.add_argument('--enable-notifications', action='store_true', help='Enable notifications')
    parser.add_argument('--disable-notifications', action='store_true', 
                       help='Disable notifications')
    parser.add_argument('--enable-face-blur', action='store_true', help='Enable face blurring')
    parser.add_argument('--disable-face-blur', action='store_true', 
                       help='Disable face blurring')
    
    # Retention policy
    parser.add_argument('--retention-days', type=int, 
                       help='Maximum days to keep screenshots (0 to disable)')
    
    # Logging
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       help='Set the logging level')
    
    return parser.parse_args()

class ScreenshotTool:
    def __init__(self, config_path: str = "config.json", nogui: bool = False):
        """Initialize the screenshot tool with configuration
        
        Args:
            config_path: Path to the configuration file
            nogui: Whether to run in command-line mode without GUI
        """
        self.running = False
        self.screenshot_thread = None
        self.cleanup_thread = None
        self.config_path = os.path.abspath(config_path)
        self.config = load_config(config_path)
        
        # Apply command line args
        self.nogui = nogui
        
        # Set up logging first
        log_level = self.config.get("log_level", "INFO")
        setup_logging(log_level)
        
        logger.info(f"Starting Auto Screenshot (GUI: {not nogui})")
        logger.debug(f"Configuration loaded from {os.path.abspath(config_path)}")
        
        # Initialize attributes from config
        self.interval = self.config["interval"]
        self.mode = self.config["mode"]
        self.target_window = self.config["target_window"]
        self.custom_region = self.config["custom_region"]
        self.screenshots_dir = os.path.expanduser(self.config["save_path"])
        self.image_format = self.config["image_format"].lower()
        self.jpg_quality = max(1, min(100, self.config["jpg_quality"]))  # Clamp 1-100
        
        # Create screenshots directory
        try:
            os.makedirs(self.screenshots_dir, exist_ok=True)
            logger.debug(f"Screenshots will be saved to: {self.screenshots_dir}")
        except Exception as e:
            logger.error(f"Failed to create screenshots directory: {e}")
            raise
        
        # Disable pyautogui failsafe for smoother operation
        if HAS_GUI_DEPS:
            pyautogui.FAILSAFE = False
        
        # Initialize tray icon
        self.tray_icon = None
        
        # Setup GUI unless running in nogui mode
        if not self.nogui and HAS_GUI_DEPS:
            self.setup_gui()
        elif self.nogui:
            logger.info("Running in command-line mode")
            self.start_capture()
        else:
            logger.error("GUI dependencies not available. Run with --nogui")
            sys.exit(1)
        
        # Start cleanup thread if retention is enabled
        if self.config["max_retention_days"] > 0:
            self._start_cleanup_thread()
    
    def setup_gui(self):
        """Create the main GUI interface"""
        self.root = tk.Tk()
        self.root.title("Automatic Screenshot Tool")
        self.root.geometry("500x600")
        
        # Main frame
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(main_frame, text="Screenshot Tool", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Interval setting
        interval_frame = tk.Frame(main_frame)
        interval_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(interval_frame, text="Interval (seconds):").pack(side=tk.LEFT)
        self.interval_var = tk.StringVar(value="5")
        interval_entry = tk.Entry(interval_frame, textvariable=self.interval_var, width=10)
        interval_entry.pack(side=tk.RIGHT)
        
        # Mode selection
        mode_frame = tk.LabelFrame(main_frame, text="Screenshot Mode", padx=10, pady=10)
        mode_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.mode_var = tk.StringVar(value="fullscreen")
        
        tk.Radiobutton(mode_frame, text="Full Screen", 
                      variable=self.mode_var, value="fullscreen").pack(anchor=tk.W)
        tk.Radiobutton(mode_frame, text="Specific Window", 
                      variable=self.mode_var, value="window").pack(anchor=tk.W)
        tk.Radiobutton(mode_frame, text="Custom Region", 
                      variable=self.mode_var, value="region").pack(anchor=tk.W)
        
        # Window selection
        window_frame = tk.Frame(main_frame)
        window_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(window_frame, text="Select Window", 
                 command=self.select_window).pack(side=tk.LEFT)
        self.window_label = tk.Label(window_frame, text="No window selected", 
                                   wraplength=300)
        self.window_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Region selection
        region_frame = tk.Frame(main_frame)
        region_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Button(region_frame, text="Select Region", 
                 command=self.select_region).pack(side=tk.LEFT)
        self.region_label = tk.Label(region_frame, text="No region selected")
        self.region_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Control buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        self.start_button = tk.Button(button_frame, text="Start Capture", 
                                     command=self.start_capture, 
                                     bg="#4CAF50", fg="white", font=("Arial", 12))
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.stop_button = tk.Button(button_frame, text="Stop Capture", 
                                    command=self.stop_capture, 
                                    bg="#f44336", fg="white", font=("Arial", 12),
                                    state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(button_frame, text="Test Screenshot", 
                 command=self.test_screenshot, 
                 bg="#2196F3", fg="white", font=("Arial", 12)).pack(side=tk.LEFT)
        
        # Status display
        self.status_label = tk.Label(main_frame, text="Ready", 
                                   font=("Arial", 10), fg="green")
        self.status_label.pack(pady=(20, 0))
        
        # Screenshot counter
        self.counter_label = tk.Label(main_frame, text="Screenshots taken: 0", 
                                    font=("Arial", 10))
        self.counter_label.pack(pady=(5, 0))
        
        self.screenshot_count = 0
    
    def select_window(self):
        """Allow user to select a specific window"""
        windows = gw.getAllWindows()
        window_titles = [w.title for w in windows if w.title.strip()]
        
        if not window_titles:
            messagebox.showwarning("No Windows", "No windows found!")
            return
        
        # Create window selection dialog
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Window")
        selection_window.geometry("400x300")
        selection_window.grab_set()  # Make it modal
        
        tk.Label(selection_window, text="Select a window:", 
                font=("Arial", 12, "bold")).pack(pady=10)
        
        # Create listbox with scrollbar
        list_frame = tk.Frame(selection_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)
        
        for title in window_titles:
            listbox.insert(tk.END, title)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_title = window_titles[selection[0]]
                self.target_window = selected_title
                self.window_label.config(text=f"Selected: {selected_title[:50]}...")
                selection_window.destroy()
        
        tk.Button(selection_window, text="Select", 
                 command=on_select, bg="#4CAF50", fg="white").pack(pady=10)
    
    def select_region(self):
        """Allow user to select a custom region"""
        messagebox.showinfo("Region Selection", 
                          "Click and drag to select the region you want to capture.\n"
                          "The selection window will appear shortly.")
        
        # Hide main window temporarily
        self.root.withdraw()
        
        # Create region selection overlay
        self.create_region_selector()
    
    def create_region_selector(self):
        """Create an overlay for region selection"""
        # Store references to avoid garbage collection
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.configure(bg='black')
        self.overlay.attributes('-topmost', True)
        
        # Create canvas for drawing selection
        self.selection_canvas = tk.Canvas(
            self.overlay, 
            highlightthickness=0,
            cursor='crosshair'
        )
        self.selection_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables for selection
        self.selection_start = None
        self.selection_rect = None
        
        # Bind events
        self.selection_canvas.bind('<ButtonPress-1>', self._on_region_select_start)
        self.selection_canvas.bind('<B1-Motion>', self._on_region_select_drag)
        self.selection_canvas.bind('<ButtonRelease-1>', self._on_region_select_end)
        self.overlay.bind('<Escape>', lambda e: self._cancel_region_selection())
        
        # Make sure overlay gets focus
        self.overlay.focus_force()
        
    def _on_region_select_start(self, event):
        """Handle mouse button press for region selection"""
        self.selection_start = (event.x, event.y)
        if self.selection_rect:
            self.selection_canvas.delete(self.selection_rect)
            
    def _on_region_select_drag(self, event):
        """Handle mouse drag for region selection"""
        if not self.selection_start:
            return
            
        x0, y0 = self.selection_start
        x1, y1 = event.x, event.y
        
        # Delete previous rectangle if it exists
        if self.selection_rect:
            self.selection_canvas.delete(self.selection_rect)
            
        # Draw new rectangle
        self.selection_rect = self.selection_canvas.create_rectangle(
            x0, y0, x1, y1,
            outline='red',
            width=2,
            dash=(4, 4)
        )
        
    def _on_region_select_end(self, event):
        """Handle mouse button release for region selection"""
        if not self.selection_start:
            return
            
        x0, y0 = self.selection_start
        x1, y1 = event.x, event.y
        
        # Ensure coordinates are in the correct order
        x0, x1 = sorted([x0, x1])
        y0, y1 = sorted([y0, y1])
        
        # Store the selected region
        self.custom_region = (x0, y0, x1 - x0, y1 - y0)
        logger.info(f"Selected region: {self.custom_region}")
        
        # Clean up
        self._cancel_region_selection()
        
        # Show main window again
        if hasattr(self, 'root') and self.root:
            self.root.deiconify()
            
    def _cancel_region_selection(self):
        """Cancel region selection and clean up"""
        if hasattr(self, 'overlay') and self.overlay:
            self.overlay.destroy()
            self.overlay = None
        self.selection_start = None
        self.selection_rect = None
    
    def _cleanup_old_screenshots(self):
        """Delete screenshots older than max_retention_days"""
        if self.config["max_retention_days"] <= 0:
            return
                
        try:
            now = datetime.now()
            cutoff_date = now - timedelta(days=self.config["max_retention_days"])
                
            for filename in os.listdir(self.screenshots_dir):
                if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    continue
                        
                filepath = os.path.join(self.screenshots_dir, filename)
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    
                if mtime < cutoff_date:
                    try:
                        os.remove(filepath)
                        logger.debug(f"Deleted old screenshot: {filename}")
                    except Exception as e:
                        logger.error(f"Error deleting {filename}: {e}")
                        
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise  # Re-raise the exception to be caught by the cleanup loop

    def _start_cleanup_thread(self):
        """Start a background thread for cleanup tasks"""
        def cleanup_loop():
            while self.running:
                try:
                    self._cleanup_old_screenshots()
                    # Run cleanup once per hour
                    for _ in range(3600):  # Check every second for 1 hour
                        if not self.running:
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Error in cleanup thread: {e}")
                    time.sleep(60)  # Wait a minute before retrying
        
        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()

    def capture_screenshot(self):
        """Capture a single screenshot based on current settings"""
        try:
            # Skip if not within work hours (if work hours are enabled)
            if self.config["work_hours"]["enabled"] and not self._is_within_work_hours():
                logger.debug("Skipping capture: outside of work hours")
                return False, "Skipped: outside of work hours"
                
            # Get the filename for this screenshot
            filename = self._get_screenshot_filename()
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Take the screenshot based on the current mode
            if self.mode == "fullscreen":
                screenshot = pyautogui.screenshot()
            elif self.mode == "window" and self.target_window:
                try:
                    # Try to get the window by title
                    window = gw.getWindowsWithTitle(self.target_window)[0]
                    if window:
                        screenshot = pyautogui.screenshot(region=(
                            window.left, window.top, 
                            window.width, window.height
                        ))
                    else:
                        logger.warning(f"Window not found: {self.target_window}")
                        return False, f"Window not found: {self.target_window}"
                except Exception as e:
                    logger.error(f"Error capturing window: {e}")
                    return False, f"Error capturing window: {e}"
            elif self.mode == "region" and self.custom_region:
                try:
                    x, y, width, height = self.custom_region
                    screenshot = pyautogui.screenshot(region=(x, y, width, height))
                except Exception as e:
                    logger.error(f"Error capturing region: {e}")
                    return False, f"Error capturing region: {e}"
            else:
                logger.error(f"Invalid capture mode or missing parameters: {self.mode}")
                return False, f"Invalid capture mode or missing parameters: {self.mode}"
            
            # Apply face blur if enabled
            if self.config["enable_face_blur"] and HAS_OPENCV:
                screenshot = self._blur_faces(screenshot)
            
            # Save the screenshot in the requested format
            save_kwargs = {}
            if self.image_format == "jpg":
                save_kwargs["quality"] = self.jpg_quality
                save_kwargs["optimize"] = True
                
            screenshot.save(filename, format=self.image_format.upper(), **save_kwargs)
            logger.info(f"Screenshot saved: {filename}")
            return True, filename
            
        except Exception as e:
            error_msg = f"Error capturing screenshot: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _get_screenshot_filename(self) -> str:
        """Generate a filename for the screenshot"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"screenshot_{timestamp}.{self.image_format}"
        return os.path.join(self.screenshots_dir, filename)
    
    def _is_within_work_hours(self) -> bool:
        """Check if current time is within configured work hours"""
        if not self.config["work_hours"]["enabled"]:
            return True
            
        try:
            now = datetime.now().time()
            start = datetime.strptime(self.config["work_hours"]["start"], "%H:%M").time()
            end = datetime.strptime(self.config["work_hours"]["end"], "%H:%M").time()
            
            # Handle overnight work hours
            if start < end:
                return start <= now <= end
            else:
                return now >= start or now <= end
        except Exception as e:
            logger.error(f"Error checking work hours: {e}")
            return True  # Default to allowing captures if there's an error
    
    def _blur_faces(self, image):
        """Apply face blurring to the image if OpenCV is available"""
        if not HAS_OPENCV:
            logger.warning("OpenCV not available, skipping face blur")
            return image
            
        try:
            import cv2
            import numpy as np
            from PIL import Image
            
            # Convert PIL Image to OpenCV format
            img_array = np.array(image)
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Load the pre-trained face detector
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            # Detect faces in the image
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            
            # Blur each detected face
            for (x, y, w, h) in faces:
                # Extract the region of interest (face)
                face_roi = img_array[y:y+h, x:x+w]
                
                # Apply Gaussian blur to the face region
                face_roi = cv2.GaussianBlur(face_roi, (99, 99), 30)
                
                # Put the blurred face back into the image
                img_array[y:y+h, x:x+w] = face_roi
            
            # Convert back to PIL Image
            img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
            return Image.fromarray(img_array)
            
        except Exception as e:
            logger.error(f"Error applying face blur: {e}")
            return image  # Return original image if there's an error
    
    def _capture_loop(self):
        """Main capture loop"""
        while self.running:
            try:
                self.capture_screenshot()
                
                # Sleep for the interval, but check for stop every second
                for _ in range(self.interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                time.sleep(5)  # Prevent tight loop on error
                
    def _show_notification(self, title: str, message: str):
        """Show a desktop notification if enabled and available"""
        if not self.config["enable_notifications"] or not HAS_PLYER:
            return
            
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Auto Screenshot",
                timeout=5
            )
        except Exception as e:
            logger.warning(f"Could not show notification: {e}")
        
    def _setup_tray_icon(self):
        """Set up the system tray icon"""
        if not HAS_PYSTRAY or self.nogui or not self.config["enable_tray"]:
            return
            
        try:
            from PIL import Image, ImageDraw
            
            # Create a simple icon
            width = 64
            height = 64
            color = "#3498db"
            
            # Create a new image with a transparent background
            image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            dc = ImageDraw.Draw(image)
            
            # Draw a simple camera icon
            dc.ellipse((10, 10, width-10, height-10), fill=color)
            dc.ellipse((20, 20, width-20, height-20), fill="white")
            
            # Create menu items
            menu_items = []
            
            if self.running:
                menu_items.append(
                    pystray.MenuItem(
                        'Stop Capture',
                        lambda: self.stop_capture()
                    )
                )
            else:
                menu_items.append(
                    pystray.MenuItem(
                        'Start Capture',
                        lambda: self.start_capture()
                    )
                )
                
            menu_items.extend([
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Exit', lambda: self.on_close())
            ])
            
            # Create the tray icon
            self.tray_icon = pystray.Icon(
                "auto_screencap",
                image,
                "Auto Screenshot",
                menu=pystray.Menu(*menu_items)
            )
            
            # Start the tray icon in a separate thread
            threading.Thread(
                target=self.tray_icon.run,
                daemon=True
            ).start()
            
            logger.debug("Tray icon started")
            
        except Exception as e:
            logger.error(f"Error setting up tray icon: {e}")
            self.tray_icon = None
        
    def on_close(self):
        """Handle application close"""
        if hasattr(self, 'tray_icon') and self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception as e:
                logger.debug(f"Error stopping tray icon: {e}")
                
        if hasattr(self, 'root'):
            try:
                self.root.quit()
                self.root.destroy()
            except Exception as e:
                logger.debug(f"Error closing root window: {e}")
                
        self.running = False
        
    def start_capture(self):
        """Start the screenshot capture loop"""
        if self.running:
            return
            
        try:
            # Update settings from UI if available
            if hasattr(self, 'interval_var'):
                self.interval = int(self.interval_var.get())
                self.config["interval"] = self.interval
            if hasattr(self, 'mode_var'):
                self.mode = self.mode_var.get()
                self.config["mode"] = self.mode
            
            if self.interval < 1:
                error_msg = "Interval must be at least 1 second"
                if not self.nogui:
                    messagebox.showerror("Error", error_msg)
                logger.error(error_msg)
                return
                
            self.running = True
            self.screenshot_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.screenshot_thread.start()
            logger.info("Screenshot capture started")
            
            if hasattr(self, 'start_button'):
                self.start_button.config(state=tk.DISABLED)
                if hasattr(self, 'stop_button'):
                    self.stop_button.config(state=tk.NORMAL)
            
            # Start tray icon if enabled (only if not already started)
            if not hasattr(self, '_tray_icon_started') and self.config.get("enable_tray", True):
                try:
                    self._setup_tray_icon()
                    self._tray_icon_started = True
                except Exception as e:
                    logger.warning(f"Failed to start tray icon: {e}")
                    
            self._show_notification("Capture Started", f"Taking screenshots every {self.interval} seconds")
            
        except Exception as e:
            error_msg = f"Error starting capture: {e}"
            logger.error(error_msg, exc_info=True)
            if not self.nogui:
                messagebox.showerror("Error", error_msg)
            self.running = False
    
    def stop_capture(self):
        """Stop the screenshot capture loop"""
        if self.running:
            self.running = False
            if self.screenshot_thread and self.screenshot_thread.is_alive():
                self.screenshot_thread.join(timeout=2.0)
            logger.info("Screenshot capture stopped")
            
            if hasattr(self, 'start_button'):
                self.start_button.config(state=tk.NORMAL)
                if hasattr(self, 'stop_button'):
                    self.stop_button.config(state=tk.DISABLED)
            
            self._show_notification("Capture Stopped", "Screenshot capture has been stopped")
    
    def test_screenshot(self):
        """Take a single test screenshot to verify settings"""
        try:
            # Save the current running state
            was_running = self.running
            
            # If currently running, pause the capture
            if was_running:
                self.stop_capture()
            
            # Take a single screenshot
            success, filename = self.capture_screenshot()
            
            if success:
                message = f"Test screenshot saved to:\n{filename}"
                logger.info(message)
                if not self.nogui:
                    messagebox.showinfo("Test Screenshot", message)
                self._show_notification("Test Screenshot", "Test screenshot captured successfully!")
            else:
                error_msg = f"Failed to capture test screenshot: {filename}"
                logger.error(error_msg)
                if not self.nogui:
                    messagebox.showerror("Error", error_msg)
            
            # Restore the previous running state
            if was_running:
                self.start_capture()
                
        except Exception as e:
            error_msg = f"Error taking test screenshot: {e}"
            logger.error(error_msg, exc_info=True)
            if not self.nogui:
                messagebox.showerror("Error", error_msg)

def main():
    """Main entry point for the application"""
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Initialize and run the application
        app = ScreenshotTool(
            config_path=args.config,
            nogui=args.nogui
        )
        
        # Start the main loop if in GUI mode
        if not args.nogui and HAS_GUI_DEPS:
            app.root.mainloop()
        
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        if not args.nogui and HAS_GUI_DEPS:
            messagebox.showerror("Error", f"An error occurred: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())