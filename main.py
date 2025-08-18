#!/usr/bin/env python3
"""
Automatic Screenshot Tool
Captures screenshots at regular intervals with various options:
- Full screen capture
- Specific application window
- Custom region selection
"""

import os
import time
import threading
from datetime import datetime
from typing import Optional, Tuple
import tkinter as tk
from tkinter import messagebox, simpledialog

try:
    import pyautogui
    import pygetwindow as gw
    from PIL import Image, ImageTk
except ImportError as e:
    print(f"Required library not installed: {e}")
    print("Please install required packages:")
    print("pip install pyautogui pygetwindow pillow")
    exit(1)

class ScreenshotTool:
    def __init__(self):
        self.running = False
        self.screenshot_thread = None
        self.interval = 5  # Default 5 seconds
        self.mode = "fullscreen"  # fullscreen, window, region
        self.target_window = None
        self.custom_region = None
        self.screenshots_dir = "screenshots"
        
        # Create screenshots directory
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Disable pyautogui failsafe for smoother operation
        pyautogui.FAILSAFE = False
        
        self.setup_gui()
    
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
        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        # Create fullscreen transparent window
        overlay = tk.Toplevel()
        overlay.attributes('-fullscreen', True)
        overlay.attributes('-alpha', 0.3)
        overlay.configure(bg='black')
        overlay.attributes('-topmost', True)
        
        canvas = tk.Canvas(overlay, highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables for selection
        start_x = start_y = end_x = end_y = 0
        selection_rect = None
        
        def on_mouse_down(event):
            nonlocal start_x, start_y, selection_rect
            start_x, start_y = event.x, event.y
            if selection_rect:
                canvas.delete(selection_rect)
        
        def on_mouse_drag(event):
            nonlocal selection_rect, end_x, end_y
            end_x, end_y = event.x, event.y
            if selection_rect:
                canvas.delete(selection_rect)
            selection_rect = canvas.create_rectangle(
                start_x, start_y, end_x, end_y, 
                outline='red', width=2
            )
        
        def on_mouse_up(event):
            nonlocal end_x, end_y
            end_x, end_y = event.x, event.y
            
            # Calculate region coordinates
            x1, y1 = min(start_x, end_x), min(start_y, end_y)
            x2, y2 = max(start_x, end_x), max(start_y, end_y)
            
            if abs(x2 - x1) > 10 and abs(y2 - y1) > 10:  # Minimum size check
                self.custom_region = (x1, y1, x2 - x1, y2 - y1)  # (x, y, width, height)
                self.region_label.config(
                    text=f"Region: {x1},{y1} - {x2}x{y2} ({x2-x1}x{y2-y1})"
                )
            
            overlay.destroy()
            self.root.deiconify()  # Show main window again
        
        # Bind mouse events
        canvas.bind('<Button-1>', on_mouse_down)
        canvas.bind('<B1-Motion>', on_mouse_drag)
        canvas.bind('<ButtonRelease-1>', on_mouse_up)
        
        # Add instruction text
        canvas.create_text(screen_width//2, 50, 
                          text="Click and drag to select region. Release to confirm.", 
                          fill='white', font=('Arial', 16))
        canvas.create_text(screen_width//2, 80, 
                          text="Press ESC to cancel", 
                          fill='white', font=('Arial', 12))
        
        # ESC to cancel
        def on_escape(event):
            overlay.destroy()
            self.root.deiconify()
        
        overlay.bind('<Escape>', on_escape)
        overlay.focus_set()
    
    def take_screenshot(self) -> Optional[str]:
        """Take a screenshot based on current mode and save it"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            mode = self.mode_var.get()
            
            if mode == "fullscreen":
                screenshot = pyautogui.screenshot()
            
            elif mode == "window" and self.target_window:
                # Find the window
                windows = [w for w in gw.getAllWindows() if w.title == self.target_window]
                if not windows:
                    self.status_label.config(text="Target window not found!", fg="red")
                    return None
                
                window = windows[0]
                # Bring window to front
                try:
                    window.activate()
                    time.sleep(0.1)  # Small delay to ensure window is active
                except:
                    pass  # Some windows can't be activated
                
                # Capture window region
                screenshot = pyautogui.screenshot(region=(
                    window.left, window.top, window.width, window.height
                ))
            
            elif mode == "region" and self.custom_region:
                x, y, width, height = self.custom_region
                screenshot = pyautogui.screenshot(region=(x, y, width, height))
            
            else:
                self.status_label.config(text="Invalid configuration!", fg="red")
                return None
            
            # Save screenshot
            screenshot.save(filepath)
            self.screenshot_count += 1
            self.counter_label.config(text=f"Screenshots taken: {self.screenshot_count}")
            
            return filepath
        
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}", fg="red")
            return None
    
    def screenshot_loop(self):
        """Main screenshot capture loop"""
        while self.running:
            filepath = self.take_screenshot()
            if filepath:
                self.status_label.config(
                    text=f"Captured: {os.path.basename(filepath)}", 
                    fg="green"
                )
            
            # Wait for the specified interval
            for _ in range(int(self.interval * 10)):  # Check every 0.1 seconds
                if not self.running:
                    break
                time.sleep(0.1)
    
    def start_capture(self):
        """Start the automatic screenshot capture"""
        try:
            self.interval = float(self.interval_var.get())
            if self.interval < 0.5:
                messagebox.showwarning("Invalid Interval", 
                                     "Interval must be at least 0.5 seconds")
                return
        except ValueError:
            messagebox.showerror("Invalid Interval", 
                               "Please enter a valid number for interval")
            return
        
        mode = self.mode_var.get()
        
        # Validate configuration
        if mode == "window" and not self.target_window:
            messagebox.showwarning("No Window Selected", 
                                 "Please select a target window first")
            return
        
        if mode == "region" and not self.custom_region:
            messagebox.showwarning("No Region Selected", 
                                 "Please select a custom region first")
            return
        
        self.mode = mode
        self.running = True
        
        # Start screenshot thread
        self.screenshot_thread = threading.Thread(target=self.screenshot_loop)
        self.screenshot_thread.daemon = True
        self.screenshot_thread.start()
        
        # Update UI
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Capturing screenshots...", fg="blue")
    
    def stop_capture(self):
        """Stop the automatic screenshot capture"""
        self.running = False
        
        if self.screenshot_thread:
            self.screenshot_thread.join(timeout=1)
        
        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Stopped", fg="orange")
    
    def test_screenshot(self):
        """Take a single test screenshot"""
        mode = self.mode_var.get()
        
        if mode == "window" and not self.target_window:
            messagebox.showwarning("No Window Selected", 
                                 "Please select a target window first")
            return
        
        if mode == "region" and not self.custom_region:
            messagebox.showwarning("No Region Selected", 
                                 "Please select a custom region first")
            return
        
        self.mode = mode
        filepath = self.take_screenshot()
        
        if filepath:
            messagebox.showinfo("Test Screenshot", 
                              f"Test screenshot saved as:\n{filepath}")
    
    def run(self):
        """Start the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window closing"""
        if self.running:
            self.stop_capture()
        self.root.destroy()

class CommandLineInterface:
    """Command line interface for the screenshot tool"""
    
    @staticmethod
    def show_windows():
        """Display all available windows"""
        windows = gw.getAllWindows()
        print("\nAvailable windows:")
        for i, window in enumerate(windows):
            if window.title.strip():
                print(f"{i+1}. {window.title}")
    
    @staticmethod
    def run_cli():
        """Run command line version"""
        print("=== Automatic Screenshot Tool (CLI) ===")
        print("1. Full screen")
        print("2. Specific window")
        print("3. Custom region")
        
        try:
            choice = input("\nSelect mode (1-3): ").strip()
            interval = float(input("Enter interval in seconds: "))
            
            if interval < 0.5:
                print("Interval must be at least 0.5 seconds")
                return
            
            screenshots_dir = "screenshots"
            os.makedirs(screenshots_dir, exist_ok=True)
            
            if choice == "1":
                mode = "fullscreen"
                print(f"Starting fullscreen capture every {interval} seconds...")
                print("Press Ctrl+C to stop")
                
            elif choice == "2":
                CommandLineInterface.show_windows()
                window_num = int(input("\nEnter window number: ")) - 1
                windows = [w for w in gw.getAllWindows() if w.title.strip()]
                
                if 0 <= window_num < len(windows):
                    target_window = windows[window_num]
                    print(f"Capturing window: {target_window.title}")
                    print("Press Ctrl+C to stop")
                else:
                    print("Invalid window number")
                    return
                    
            elif choice == "3":
                print("Region selection not available in CLI mode.")
                print("Please use GUI mode for region selection.")
                return
            
            else:
                print("Invalid choice")
                return
            
            # Start capture loop
            count = 0
            try:
                while True:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_{timestamp}.png"
                    filepath = os.path.join(screenshots_dir, filename)
                    
                    if choice == "1":
                        screenshot = pyautogui.screenshot()
                    elif choice == "2":
                        try:
                            target_window.activate()
                            time.sleep(0.1)
                        except:
                            pass
                        screenshot = pyautogui.screenshot(region=(
                            target_window.left, target_window.top, 
                            target_window.width, target_window.height
                        ))
                    
                    screenshot.save(filepath)
                    count += 1
                    print(f"Screenshot {count} saved: {filename}")
                    
                    time.sleep(interval)
                    
            except KeyboardInterrupt:
                print(f"\nStopped. Total screenshots taken: {count}")
        
        except (ValueError, IndexError) as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

def main():
    """Main function to choose between GUI and CLI"""
    print("Automatic Screenshot Tool")
    print("1. Launch GUI (recommended)")
    print("2. Use command line interface")
    
    try:
        choice = input("Select interface (1-2, or press Enter for GUI): ").strip()
        
        if choice == "2":
            CommandLineInterface.run_cli()
        else:
            # Default to GUI
            app = ScreenshotTool()
            app.run()
    
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error starting application: {e}")

if __name__ == "__main__":
    main()