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
import tkinter as tk
from datetime import datetime, time as dtime, timedelta
from tkinter import messagebox, ttk
import pyautogui
import pygetwindow as gw
from PIL import Image, ImageTk
from typing import Optional, Tuple, Dict, Any, Union, List
import platform

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

# Try to import Rust worker integration
try:
    from rust_integration import process_image_with_rust, RustWorkerError
    HAS_RUST_WORKER = True
except ImportError:
    HAS_RUST_WORKER = False

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
    # Core settings
    "interval": 300,  # 5 minutes
    "mode": "fullscreen",  # fullscreen, window, region
    "target_window": "",
    "custom_region": None,  # [x, y, width, height]
    "save_path": "screenshots",
    "image_format": "png",  # png or jpg
    "jpg_quality": 85,  # 1-100, only for jpg
    "max_retention_days": 30,  # 0 to disable
    
    # Work hours settings
    "work_hours": {
        "enabled": False,
        "start": "09:00",
        "end": "17:00"
    },
    
    # UI settings
    "enable_tray": True,
    "enable_notifications": True,
    
    # Face blur settings
    "enable_face_blur": False,
    "enable_rust_worker": False,  # Use Rust worker for face blur if available
    "blur_sigma": 5.0,  # Sigma value for gaussian blur
    
    # Notes and metadata settings
    "enable_notes": False,  # Master switch for notes feature
    "note_mode": "disabled",  # "prompt" | "auto" | "disabled"
    "note_timeout_seconds": 8,  # Timeout for note prompt in seconds
    "metadata_store": "json",  # "json" | "csv" | "sqlite"
    "auto_summary_ocr": False,  # Enable OCR for automatic summaries
    "enable_metadata_encryption": False,  # Encrypt metadata files
    "metadata_encryption_key": "",  # Passphrase for encryption (if enabled)
    
    # Logging
    "log_level": "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
}

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
    parser = argparse.ArgumentParser(description="Automatic screenshot capture tool")
    
    # Basic configuration
    parser.add_argument("--config", default="config.json", help="Path to configuration file")
    parser.add_argument("--nogui", action="store_true", help="Run in command-line mode without GUI")
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--fullscreen", action="store_const", dest="mode", const="fullscreen", 
                          help="Capture full screen (default)")
    mode_group.add_argument("--window", metavar="TITLE", type=str, 
                          help="Capture specific window by title")
    mode_group.add_argument("--region", nargs=4, metavar=("X", "Y", "WIDTH", "HEIGHT"), type=int,
                          help="Capture custom region (x, y, width, height)")
    
    # Basic options
    parser.add_argument("--interval", type=int, help="Capture interval in seconds")
    parser.add_argument("--output", "-o", help="Output directory for screenshots")
    parser.add_argument("--format", choices=["png", "jpg", "jpeg"], help="Image format (png/jpg)")
    parser.add_argument("--quality", type=int, choices=range(1, 101), metavar="1-100",
                      help="JPEG quality (1-100, default: 90)")
    
    # Features
    parser.add_argument("--no-tray", action="store_true", help="Disable system tray icon")
    parser.add_argument("--no-notifications", action="store_true", help="Disable desktop notifications")
    parser.add_argument("--face-blur", action="store_true", help="Enable face blur")
    parser.add_argument("--no-face-blur", action="store_true", help="Disable face blur")
    parser.add_argument("--rust-worker", action="store_true", help="Use Rust worker for face blur")
    parser.add_argument("--no-rust-worker", action="store_true", help="Disable Rust worker")
    
    # Notes and metadata
    notes_group = parser.add_argument_group('Notes and Metadata')
    notes_group.add_argument("--note", type=str, help="Add a note to the next screenshot")
    notes_group.add_argument("--no-notes", action="store_true", help="Disable notes and metadata features")
    notes_group.add_argument("--note-mode", choices=["prompt", "auto", "disabled"], 
                           help="Note mode: prompt for notes, auto-capture metadata, or disabled")
    notes_group.add_argument("--note-timeout", type=int, metavar="SECONDS",
                           help="Timeout in seconds for note prompt")
    notes_group.add_argument("--no-ocr", action="store_true", 
                           help="Disable OCR for automatic text extraction")
    notes_group.add_argument("--metadata-format", choices=["json", "csv", "sqlite"],
                           help="Format for metadata storage")
    notes_group.add_argument("--encrypt-metadata", action="store_true",
                           help="Enable encryption for metadata")
    notes_group.add_argument("--encryption-key", type=str,
                           help="Passphrase for metadata encryption (use with --encrypt-metadata)")
    
    # Work hours
    parser.add_argument("--work-hours", metavar="HH:MM-HH:MM", help="Set work hours (e.g., 09:00-17:00)")
    parser.add_argument("--no-work-hours", action="store_true", help="Disable work hours restriction")
    parser.add_argument("--max-retention-days", type=int, default=30,
                      help='Maximum days to keep screenshots (0 to disable)')
    
    # Logging
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       help='Set the logging level')
    
    # Testing
    parser.add_argument('--test', action='store_true',
                      help='Take a single test screenshot and exit')
    
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
        
        # Initialize metadata and notes
        self.pending_metadata = {}  # Store metadata for screenshots with pending notes
        
        # Try to import metadata utilities
        try:
            from metadata_utils import save_metadata, MetadataStorageError, MetadataEncryptionError
            self.has_metadata = True
        except ImportError as e:
            self.has_metadata = False
            logger.warning(f"Metadata features disabled: {e}")
        
        # Try to import note prompt
        self.has_note_prompt = False
        if HAS_GUI_DEPS and not nogui:
            try:
                from note_prompt import NotePrompt
                self.has_note_prompt = True
            except ImportError as e:
                logger.warning(f"Note prompt disabled: {e}")
        
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
            
        # Setup tray icon if in GUI mode
        if not self.nogui and HAS_GUI_DEPS:
            self._setup_tray_icon()
    
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
        
    def _cancel_region_selection(self):
        """Cancel region selection and clean up the UI"""
        # Clean up selection UI elements
        if hasattr(self, 'selection_rect') and self.selection_rect:
            try:
                self.selection_canvas.delete(self.selection_rect)
            except Exception as e:
                logger.debug(f"Error cleaning up selection rectangle: {e}")
        
        # Reset selection state
        if hasattr(self, 'selection_canvas'):
            try:
                self.selection_canvas.unbind("<ButtonPress-1>")
                self.selection_canvas.unbind("<B1-Motion>")
                self.selection_canvas.unbind("<ButtonRelease-1>")
            except Exception as e:
                logger.debug(f"Error unbinding canvas events: {e}")
        
        # Close the selector window if it exists
        if hasattr(self, 'selector_window') and self.selector_window:
            try:
                self.selector_window.destroy()
                del self.selector_window
            except Exception as e:
                logger.debug(f"Error closing selector window: {e}")
        
        # Reset selection attributes
        if hasattr(self, 'selection_start'):
            del self.selection_start
        if hasattr(self, 'selection_rect'):
            del self.selection_rect
            
        # Update status if available
        if hasattr(self, 'status_var'):
            self.status_var.set("Region selection cancelled")
            
    def _on_region_select_end(self, event):
        """Handle mouse button release for region selection"""
        if not hasattr(self, 'selection_start') or not self.selection_start:
            return
            
        x0, y0 = self.selection_start
        x1, y1 = event.x, event.y
        
        # Ensure x1,y1 is bottom-right and x0,y0 is top-left
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
            
        # Ensure minimum size
        min_size = 10
        if x1 - x0 < min_size or y1 - y0 < min_size:
            messagebox.showwarning("Selection Too Small", 
                                f"Please select a region at least {min_size}x{min_size} pixels")
            self._cancel_region_selection()
            return
            
        # Save the selected region
        self.custom_region = (x0, y0, x1 - x0, y1 - y0)
        logger.info(f"Selected region: {self.custom_region}")
        
        # Update the mode to region
        if hasattr(self, 'mode_var'):
            self.mode_var.set("region")
            self.mode = "region"
        
        # Update the status
        if hasattr(self, 'status_var'):
            self.status_var.set(f"Region selected: {x0},{y0} to {x1},{y1} ({(x1-x0)}x{(y1-y0)})")
        
        # Clean up the selection UI
        self._cleanup_region_selection()
        
        # Update the config
        self.config["mode"] = "region"
        self.config["custom_region"] = self.custom_region
        save_config(self.config, self.config_path)
        
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
                    time.sleep(60)  # Wait a minute before retrying on error
        
        # Start the cleanup thread
        self.cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        logger.info("Started cleanup thread")

    def _blur_faces(self, image, image_path=None):
        """
        Apply face blurring to the image.
        
        Args:
            image: PIL Image to process
            image_path: Optional path to the image file (used for Rust worker)
            
        Returns:
            Processed PIL Image with faces blurred
        """
        # Try to use Rust worker if enabled and available
        if self.config.get("enable_rust_worker", False) and image_path and HAS_RUST_WORKER:
            try:
                # Save the image temporarily if it's not already saved
                if not image_path:
                    temp_path = Path("temp_screenshot.png")
                    image.save(temp_path, "PNG")
                    temp_file = True
                else:
                    temp_path = Path(image_path)
                    temp_file = False
                
                # Process with Rust worker
                result_path = process_image_with_rust(
                    image_path=temp_path,
                    blur_sigma=self.config.get("blur_sigma", 5.0),
                    resize=None  # Don't resize, just blur
                )
                
                # Clean up temp file if we created one
                if temp_file and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to delete temp file: {e}")
                
                # If Rust worker succeeded, return the processed image
                if result_path and result_path.exists():
                    result_image = Image.open(result_path)
                    # Clean up the processed file if it's not the original
                    if str(result_path) != str(temp_path):
                        try:
                            result_path.unlink()
                        except Exception as e:
                            logger.warning(f"Failed to delete processed file: {e}")
                    return result_image
                
                # Fall through to Python implementation if Rust worker failed
                logger.debug("Rust worker failed, falling back to Python implementation")
                
            except Exception as e:
                logger.warning(f"Error using Rust worker: {e}")
                # Fall through to Python implementation
        
        # Fallback to Python implementation if Rust worker is not available or failed
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
    
    def _get_active_window_info(self) -> Dict[str, str]:
        """Get information about the currently active window.
        
        Returns:
            Dictionary with window title and application name
        """
        try:
            if not HAS_GUI_DEPS:
                return {}
                
            active_window = gw.getActiveWindow()
            if not active_window:
                return {}
                
            return {
                'window_title': getattr(active_window, 'title', ''),
                'app_name': os.path.basename(active_window.process.name()) if hasattr(active_window, 'process') else ''
            }
        except Exception as e:
            logger.warning(f"Could not get active window info: {e}")
            return {}

    def _handle_note_result(self, note: str, filename: str, extra_metadata: Dict[str, Any]):
        """Handle the result of a note prompt.
        
        Args:
            note: The note text (empty string if skipped)
            filename: Path to the screenshot file
            extra_metadata: Additional metadata to include
        """
        try:
            if note is not None:  # None means the prompt was cancelled
                # Save metadata with the note
                if self.has_metadata and self.config.get('enable_notes', False):
                    try:
                        from metadata_utils import save_metadata
                        save_metadata(
                            image_path=filename,
                            note=note,
                            auto_summary=self.config.get('auto_summary_ocr', False),
                            extra=extra_metadata,
                            config=self.config
                        )
                        logger.debug(f"Saved metadata for {filename}")
                    except Exception as e:
                        logger.error(f"Failed to save metadata: {e}", exc_info=True)
            
            # Clean up
            if filename in self.pending_metadata:
                del self.pending_metadata[filename]
                
        except Exception as e:
            logger.error(f"Error handling note result: {e}", exc_info=True)

    def capture_screenshot(self, note: Optional[str] = None) -> Tuple[bool, str]:
        """Capture a single screenshot based on current settings.
        
        Args:
            note: Optional note to attach to the screenshot
            
        Returns:
            Tuple of (success, filename or error message)
        """
        try:
            # Skip if not within work hours (if work hours are enabled)
            if self.config["work_hours"]["enabled"] and not self._is_within_work_hours():
                logger.debug("Skipping capture: outside of work hours")
                return False, "Skipped: outside of work hours"
            
            # Get active window info for metadata
            window_info = {}
            if self.config.get('enable_notes', False) and self.config.get('note_mode', 'prompt') == 'auto':
                window_info = self._get_active_window_info()
                
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
                        # Update window info if we're capturing a specific window
                        if not window_info:
                            window_info = {
                                'window_title': window.title,
                                'app_name': os.path.basename(window.process.name()) if hasattr(window, 'process') else ''
                            }
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
            
            # Save the original screenshot first
            temp_filename = None
            if self.config["enable_face_blur"] and (HAS_OPENCV or HAS_RUST_WORKER):
                # Save original to a temp file if using Rust worker
                if self.config.get("enable_rust_worker", False) and HAS_RUST_WORKER:
                    temp_filename = f"{filename}.tmp.{self.image_format}"
                    save_kwargs = {}
                    if self.image_format == "jpg":
                        save_kwargs["quality"] = self.jpg_quality
                        save_kwargs["optimize"] = True
                    screenshot.save(temp_filename, format=self.image_format.upper(), **save_kwargs)
            
            # Apply face blur if enabled
            if self.config["enable_face_blur"] and (HAS_OPENCV or HAS_RUST_WORKER):
                try:
                    screenshot = self._blur_faces(screenshot, temp_filename or filename)
                    logger.debug("Applied face blur to screenshot")
                except Exception as e:
                    logger.error(f"Error applying face blur: {e}")
                    # Continue with unblurred screenshot
            
            # Clean up temp file if we created one
            if temp_filename and os.path.exists(temp_filename):
                try:
                    os.unlink(temp_filename)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file: {e}")
            
            # Save the final screenshot
            save_kwargs = {}
            if self.image_format == "jpg":
                save_kwargs["quality"] = self.jpg_quality
                save_kwargs["optimize"] = True
                
            screenshot.save(filename, format=self.image_format.upper(), **save_kwargs)
            logger.info(f"Screenshot saved: {filename}")
            
            # Handle notes and metadata
            if self.config.get('enable_notes', False):
                note_mode = self.config.get('note_mode', 'prompt')
                
                # Prepare metadata
                metadata = {
                    'window_title': window_info.get('window_title', ''),
                    'app_name': window_info.get('app_name', ''),
                    'capture_mode': self.mode,
                    'image_format': self.image_format,
                    **(window_info or {})
                }
                
                # Handle different note modes
                if note_mode == 'auto' or note:
                    # Save metadata immediately for auto mode or if note is provided directly
                    if self.has_metadata:
                        try:
                            from metadata_utils import save_metadata
                            save_metadata(
                                image_path=filename,
                                note=note or '',
                                auto_summary=self.config.get('auto_summary_ocr', False),
                                extra=metadata,
                                config=self.config
                            )
                            logger.debug("Saved auto metadata")
                        except Exception as e:
                            logger.error(f"Failed to save auto metadata: {e}", exc_info=True)
                
                elif note_mode == 'prompt' and self.has_note_prompt and not self.nogui:
                    # Show note prompt in non-blocking way
                    try:
                        # Store metadata for when we get the note
                        self.pending_metadata[filename] = metadata
                        
                        # Create and show the note prompt
                        from note_prompt import NotePrompt
                        NotePrompt(
                            image_path=filename,
                            callback=lambda n, f=filename, m=metadata: self._handle_note_result(n, f, m),
                            timeout=self.config.get('note_timeout_seconds', 8),
                            title="Add Note to Screenshot"
                        )
                    except Exception as e:
                        logger.error(f"Failed to show note prompt: {e}", exc_info=True)
            
            # Show notification if enabled
            if self.config["enable_notifications"] and HAS_GUI_DEPS and HAS_PLYER:
                try:
                    from plyer import notification
                    notification.notify(
                        title="Screenshot Captured",
                        message=f"Saved to {os.path.basename(filename)}",
                        timeout=3
                    )
                except Exception as e:
                    logger.warning(f"Failed to show notification: {e}")
            
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
    
    def _cleanup_old_screenshots(self):
        """Delete screenshots older than the configured retention period"""
        try:
            max_days = self.config.get("max_retention_days", 0)
            if max_days <= 0:
                return
                
            logger.info(f"Starting cleanup of screenshots older than {max_days} days")
            now = datetime.now()
            cutoff_time = now - timedelta(days=max_days)
            deleted_count = 0
            
            # Get all screenshot files in the directory
            for filename in os.listdir(self.screenshots_dir):
                if not (filename.startswith("screenshot_") and 
                       (filename.endswith(".png") or filename.endswith(".jpg") or filename.endswith(".jpeg"))):
                    continue
                    
                filepath = os.path.join(self.screenshots_dir, filename)
                try:
                    # Get file modification time
                    mtime = os.path.getmtime(filepath)
                    file_time = datetime.fromtimestamp(mtime)
                    
                    # Delete if older than retention period
                    if file_time < cutoff_time:
                        try:
                            os.remove(filepath)
                            deleted_count += 1
                            logger.debug(f"Deleted old screenshot: {filename}")
                            
                            # Also delete associated metadata file if it exists
                            metadata_file = f"{filepath}.meta"
                            if os.path.exists(metadata_file):
                                os.remove(metadata_file)
                                logger.debug(f"Deleted metadata file: {metadata_file}")
                                
                        except Exception as e:
                            logger.error(f"Error deleting {filename}: {e}")
                            
                except Exception as e:
                    logger.error(f"Error checking file {filename}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old screenshot(s)")
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def capture_screenshot(self, note: Optional[str] = None) -> Tuple[bool, str]:
        """Capture a screenshot based on current settings.
        
        Args:
            note: Optional note to attach to the screenshot
            
        Returns:
            Tuple of (success, filename or error message)
        """
        try:
            # Skip if not within work hours (if work hours are enabled)
            work_hours = self.config.get("work_hours", {})
            if work_hours.get("enabled", False) and not self._is_within_work_hours():
                logger.debug("Skipping capture: outside of work hours")
                return False, "Skipped: outside of work hours"
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.{self.image_format}"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Take screenshot based on mode
            if self.mode == "fullscreen":
                screenshot = pyautogui.screenshot()
            elif self.mode == "window" and self.target_window:
                try:
                    window = gw.getWindowsWithTitle(self.target_window)
                    if window:
                        win = window[0]
                        screenshot = pyautogui.screenshot(region=(
                            win.left, win.top, win.width, win.height
                        ))
                    else:
                        logger.warning(f"Window '{self.target_window}' not found, falling back to fullscreen")
                        screenshot = pyautogui.screenshot()
                except Exception as e:
                    logger.warning(f"Error capturing window: {e}, falling back to fullscreen")
                    screenshot = pyautogui.screenshot()
            elif self.mode == "region" and hasattr(self, 'custom_region') and self.custom_region:
                x, y, width, height = self.custom_region
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
            else:
                screenshot = pyautogui.screenshot()
            
            # Save the image
            save_kwargs = {}
            if self.image_format in ["jpg", "jpeg"]:
                save_kwargs["quality"] = self.jpg_quality
                
            screenshot.save(filepath, **save_kwargs)
            logger.info(f"Screenshot saved: {filepath}")
            
            # Save metadata if enabled
            if hasattr(self, 'has_metadata') and self.has_metadata and note:
                try:
                    from metadata_utils import save_metadata
                    save_metadata(
                        filepath,
                        note=note,
                        auto_summary=self.config.get("auto_summary", False),
                        extra={
                            "mode": self.mode,
                            "interval": self.interval,
                            "window_title": self.target_window if self.mode == "window" else None,
                            "region": self.custom_region if self.mode == "region" else None
                        },
                        config=self.config
                    )
                except Exception as e:
                    logger.error(f"Error saving metadata: {e}", exc_info=True)
            
            return True, filepath
                
        except Exception as e:
            error_msg = f"Error in capture_screenshot: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    def _capture_loop(self):
        """Main loop for capturing screenshots at regular intervals"""
        logger.info("Starting capture loop")
        
        while getattr(self, 'running', False):
            try:
                start_time = time.time()
                
                # Take a screenshot
                success, result = self.capture_screenshot()
                if success:
                    logger.debug(f"Successfully captured screenshot: {result}")
                else:
                    logger.warning(f"Failed to capture screenshot: {result}")
                
                # Calculate sleep time to maintain the desired interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.interval - elapsed)
                
                # Sleep in small increments to allow for quick shutdown
                while sleep_time > 0 and getattr(self, 'running', False):
                    time.sleep(min(0.5, sleep_time))
                    sleep_time -= 0.5
                    
            except Exception as e:
                logger.error(f"Error in capture loop: {e}", exc_info=True)
                time.sleep(5)  # Prevent tight loop on error
    
    def _setup_tray_icon(self):
        """Set up the system tray icon with menu options"""
        try:
            if not HAS_GUI_DEPS or self.nogui or not hasattr(self, 'root'):
                logger.debug("Skipping tray icon setup (GUI disabled or root not available)")
                return
                
            import pystray
            from PIL import Image, ImageDraw
            
            # Create a blank image for the icon
            width = 64
            height = 64
            color1 = '#1E88E5'  # Blue
            color2 = '#0D47A1'  # Darker blue
            
            # Create a new image with a blue gradient background
            image = Image.new('RGB', (width, height), color1)
            dc = ImageDraw.Draw(image)
            dc.rectangle([0, 0, width, height//2], fill=color1)
            dc.rectangle([0, height//2, width, height], fill=color2)
            
            # Add a camera icon
            camera_size = 32
            x = (width - camera_size) // 2
            y = (height - camera_size) // 2
            dc.ellipse([x, y, x + camera_size, y + camera_size], outline='white', width=2)
            dc.ellipse([x + 8, y + 8, x + camera_size - 8, y + camera_size - 8], outline='white', width=1)
            
            # Create menu items
            def on_quit(icon, item):
                icon.stop()
                if hasattr(self, 'root'):
                    self.root.quit()
                self.running = False
                sys.exit(0)
                
            def on_toggle_capture(icon, item):
                if self.running:
                    self.stop_capture()
                    icon.notify("Screenshot capture stopped", "Auto Screenshot")
                else:
                    self.start_capture()
                    icon.notify("Screenshot capture started", "Auto Screenshot")
                    
            def on_take_screenshot(icon, item):
                self.test_screenshot("Manual capture from tray")
                
            # Create menu
            menu = (
                pystray.MenuItem(
                    'Take Screenshot', 
                    on_take_screenshot,
                    default=True
                ),
                pystray.MenuItem(
                    'Start/Stop Capture', 
                    on_toggle_capture
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    'Quit', 
                    on_quit
                )
            )
            
            # Create the icon
            self.tray_icon = pystray.Icon(
                "auto_screenshot",
                image,
                "Auto Screenshot",
                menu=menu
            )
            
            # Run the icon in a separate thread
            import threading
            def run_icon():
                self.tray_icon.run()
                
            icon_thread = threading.Thread(target=run_icon, daemon=True)
            icon_thread.start()
            
            logger.info("Tray icon started")
            
        except Exception as e:
            logger.warning(f"Failed to start tray icon: {e}")
            
    def _show_notification(self, title: str, message: str, timeout: int = 5) -> None:
        """Show a desktop notification
        
        Args:
            title: Notification title
            message: Notification message
            timeout: Time in seconds to show the notification
        """
        try:
            if not self.config.get("enable_notifications", True):
                return
                
            if HAS_PLYER and HAS_GUI_DEPS:
                from plyer import notification
                notification.notify(
                    title=title,
                    message=message,
                    timeout=timeout,
                    app_name="Auto Screenshot"
                )
            elif HAS_GUI_DEPS and not self.nogui:
                # Fallback to tkinter messagebox if plyer is not available
                import tkinter as tk
                from tkinter import messagebox
                
                root = tk.Tk()
                root.withdraw()  # Hide the root window
                messagebox.showinfo(title, message)
                root.destroy()
            else:
                logger.info(f"{title}: {message}")
                
        except Exception as e:
            logger.error(f"Failed to show notification: {e}", exc_info=True)
    
    def _is_within_work_hours(self) -> bool:
        """Check if current time is within configured work hours"""
        work_hours = self.config.get("work_hours", {})
        if not work_hours.get("enabled", False):
            return True
            
        try:
            now = datetime.now().time()
            start = datetime.strptime(work_hours.get("start", "09:00"), "%H:%M").time()
            end = datetime.strptime(work_hours.get("end", "17:00"), "%H:%M").time()
            
            # Handle overnight work hours
            if start < end:
                return start <= now <= end
            else:
                return now >= start or now <= end
        except Exception as e:
            logger.error(f"Error checking work hours: {e}")
            return True  # Default to allowing captures if there's an error
            


    def capture_screenshot(self, note: Optional[str] = None) -> Tuple[bool, Union[str, Exception]]:
        """Capture a screenshot based on current settings
        
        Args:
            note: Optional note to attach to the screenshot
            
        Returns:
            tuple: (success, result) where success is a boolean and result is either the filename or an error message
        """
        if not self.running and not note:
            return False, "Capture is not running"
            
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.{self.image_format}"
        filepath = os.path.join(self.screenshots_dir, filename)
        
        try:
            # Take screenshot based on mode
            if self.mode == "fullscreen":
                screenshot = pyautogui.screenshot()
            elif self.mode == "window" and self.target_window:
                try:
                    window = gw.getWindowsWithTitle(self.target_window)
                    if window:
                        win = window[0]
                        screenshot = pyautogui.screenshot(region=(
                            win.left, win.top, win.width, win.height
                        ))
                    else:
                        logger.warning(f"Window '{self.target_window}' not found, falling back to fullscreen")
                        screenshot = pyautogui.screenshot()
                except Exception as e:
                    logger.warning(f"Error capturing window: {e}, falling back to fullscreen")
                    screenshot = pyautogui.screenshot()
            elif self.mode == "region" and self.custom_region:
                x, y, width, height = self.custom_region
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
            else:
                screenshot = pyautogui.screenshot()
            
            # Save the image
            save_kwargs = {}
            if self.image_format in ["jpg", "jpeg"]:
                save_kwargs["quality"] = self.jpg_quality
                
            screenshot.save(filepath, **save_kwargs)
            logger.debug(f"Screenshot saved to {filepath}")
            
            # Save metadata if enabled
            if self.has_metadata and note:
                try:
                    from metadata_utils import save_metadata
                    save_metadata(
                        filepath,
                        note=note,
                        auto_summary=self.config.get("auto_summary", False),
                        extra={
                            "mode": self.mode,
                            "interval": self.interval,
                            "window_title": self.target_window if self.mode == "window" else None,
                            "region": self.custom_region if self.mode == "region" else None
                        },
                        config=self.config
                    )
                except Exception as e:
                    logger.error(f"Error saving metadata: {e}", exc_info=True)
            
            return True, filepath
            
        except Exception as e:
            error_msg = f"Error capturing screenshot: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
            
    def test_screenshot(self, note: Optional[str] = None) -> bool:
        """Take a single test screenshot immediately
        
        Args:
            note: Optional note to attach to the test screenshot
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Taking test screenshot...")
        success, result = self.capture_screenshot(note=note)
        
        if success:
            logger.info(f"Test screenshot successful: {result}")
            
            # Show notification if enabled
            if self.config.get("enable_notifications", True):
                try:
                    from plyer import notification
                    notification.notify(
                        title="Test Screenshot",
                        message=f"Saved to {os.path.basename(result)}",
                        timeout=5
                    )
                except Exception as e:
                    logger.warning(f"Failed to show test notification: {e}")
        else:
            logger.error(f"Test screenshot failed: {result}")
            
        return success
        
    def _capture_loop(self):
        """Main capture loop that runs in a background thread"""
        logger.info("Starting capture loop")
        
        try:
            while self.running:
                start_time = time.time()
                
                try:
                    # Take a screenshot
                    success, result = self.capture_screenshot()
                    
                    if success:
                        logger.debug(f"Screenshot captured: {result}")
                    else:
                        logger.error(f"Failed to capture screenshot: {result}")
                except Exception as e:
                    logger.error(f"Error in capture loop: {e}", exc_info=True)
                
                # Calculate sleep time to maintain the interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.interval - elapsed)
                
                # Sleep in small chunks to allow for quick shutdown
                while sleep_time > 0 and self.running:
                    time.sleep(min(0.1, sleep_time))
                    sleep_time -= 0.1
                    
        except Exception as e:
            logger.error(f"Fatal error in capture loop: {e}", exc_info=True)
            self.running = False
            
            # Try to show error in GUI if available
            if hasattr(self, 'root'):
                self.root.after(100, lambda: messagebox.showerror(
                    "Capture Error", 
                    f"An error occurred in the capture loop: {e}"
                ))
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