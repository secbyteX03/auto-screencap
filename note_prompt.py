"""
Note prompt window for adding notes to screenshots.

This module provides a non-blocking GUI prompt for adding notes to screenshots.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, Any
import threading
import time

class NotePrompt:
    """A non-blocking note prompt window with timeout."""
    
    def __init__(
        self,
        image_path: str,
        callback: Callable[[str], Any],
        timeout: int = 8,
        title: str = "Add Note",
        initial_note: str = ""
    ):
        """Initialize the note prompt.
        
        Args:
            image_path: Path to the screenshot image
            callback: Function to call with the note text when done
            timeout: Timeout in seconds (0 for no timeout)
            title: Window title
            initial_note: Initial note text
        """
        self.image_path = image_path
        self.callback = callback
        self.timeout = timeout
        self.title = title
        self.initial_note = initial_note
        self.window = None
        self.timer_id = None
        self.timer_running = False
        self.timer_thread = None
        self.result_sent = False
        
        # Start the UI in a separate thread
        self.thread = threading.Thread(target=self._create_ui, daemon=True)
        self.thread.start()
    
    def _create_ui(self):
        """Create the note prompt UI."""
        self.window = tk.Tk()
        self.window.title(self.title)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Make window stay on top
        self.window.attributes('-topmost', True)
        
        # Configure grid
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        
        # Header with image name
        img_name = self.image_path.split('/')[-1] if '/' in self.image_path else self.image_path
        header = ttk.Label(
            self.window,
            text=f"Add note for: {img_name}",
            font=('Arial', 10, 'bold'),
            padding=(10, 10, 10, 5)
        )
        header.grid(row=0, column=0, columnspan=2, sticky='ew')
        
        # Note text area
        self.text = tk.Text(
            self.window,
            wrap=tk.WORD,
            width=40,
            height=6,
            font=('Arial', 10),
            padx=5,
            pady=5
        )
        self.text.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')
        self.text.insert('1.0', self.initial_note)
        self.text.focus_set()
        
        # Timer label
        if self.timeout > 0:
            self.timer_var = tk.StringVar()
            self.timer_var.set(f"Auto-saving in {self.timeout}s...")
            timer_label = ttk.Label(
                self.window,
                textvariable=self.timer_var,
                font=('Arial', 8),
                foreground='#666666'
            )
            timer_label.grid(row=2, column=0, columnspan=2, pady=(0, 5))
        
        # Button frame
        button_frame = ttk.Frame(self.window)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(0, 10))
        
        # Skip button
        skip_btn = ttk.Button(
            button_frame,
            text="Skip",
            command=self._on_skip,
            width=10
        )
        skip_btn.pack(side=tk.RIGHT, padx=5)
        
        # Save button
        save_btn = ttk.Button(
            button_frame,
            text="Save",
            command=self._on_save,
            style='Accent.TButton',
            width=10
        )
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        # Style the save button differently
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Arial', 10, 'bold'))
        
        # Set focus to the text widget
        self.text.focus_set()
        
        # Start the timer if needed
        if self.timeout > 0:
            self._start_timer()
        
        # Center the window
        self._center_window()
        
        # Start the main loop
        self.window.mainloop()
    
    def _center_window(self):
        """Center the window on the screen."""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def _start_timer(self):
        """Start the countdown timer."""
        if self.timeout <= 0 or self.timer_running:
            return
        
        self.timer_running = True
        self.remaining_time = self.timeout
        self._update_timer()
    
    def _update_timer(self):
        """Update the timer display."""
        if not self.timer_running or not hasattr(self, 'timer_var'):
            return
        
        self.remaining_time -= 1
        
        if self.remaining_time <= 0:
            self.timer_var.set("Saving...")
            self._on_timeout()
        else:
            self.timer_var.set(f"Auto-saving in {self.remaining_time}s...")
            if self.window:
                self.timer_id = self.window.after(1000, self._update_timer)
    
    def _stop_timer(self):
        """Stop the countdown timer."""
        self.timer_running = False
        if hasattr(self, 'timer_id') and self.timer_id and self.window:
            self.window.after_cancel(self.timer_id)
    
    def _send_result(self, note: str):
        """Send the result to the callback and close the window."""
        if self.result_sent:
            return
            
        self.result_sent = True
        self._stop_timer()
        
        # Call the callback in the main thread
        if self.window:
            self.window.after(100, lambda: self._safe_callback(note))
            self.window.after(200, self._safe_destroy)
    
    def _safe_callback(self, note: str):
        """Safely call the callback, handling any exceptions."""
        try:
            self.callback(note)
        except Exception as e:
            print(f"Error in note callback: {e}")
    
    def _safe_destroy(self):
        """Safely destroy the window."""
        try:
            if self.window:
                self.window.destroy()
        except:
            pass
    
    def _on_save(self, event=None):
        """Handle save button click."""
        note = self.text.get('1.0', 'end-1c').strip()
        self._send_result(note)
    
    def _on_skip(self, event=None):
        """Handle skip button click."""
        self._send_result("")
    
    def _on_timeout(self):
        """Handle timeout."""
        note = self.text.get('1.0', 'end-1c').strip()
        self._send_result(note)
    
    def _on_close(self):
        """Handle window close."""
        self._on_skip()
    
    def close(self):
        """Close the note prompt."""
        if self.window:
            self.window.after(0, self._on_skip)
