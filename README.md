# Auto Screenshot Tool

A Python-based automatic screenshot capture tool with multiple capture modes and scheduling options, featuring an optional high-performance Rust worker for image processing.

## Features

- Multiple capture modes: fullscreen, window, or custom region
- Configurable capture intervals
- Work hours scheduling
- Automatic cleanup of old screenshots
- Face blurring for privacy (with optional Rust acceleration)
- System tray icon and notifications
- Command-line and GUI interfaces
- High-performance Rust backend for image processing (optional)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/secbyteX03/auto-screencap.git
   cd auto-screencap
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   Optional Python dependencies for additional features:
   - `opencv-python`: For face blurring (Python fallback)
   - `pystray`: For system tray icon
   - `plyer`: For desktop notifications

### Rust Worker (Optional, but recommended for better performance)

For faster image processing, you can build the Rust worker:

1. Install Rust from [rustup.rs](https://rustup.rs/) if you haven't already
2. Build the Rust worker:
   ```bash
   cd rust-worker
   cargo build --release
   ```

The binary will be available at `rust-worker/target/release/rust_worker` (or `.exe` on Windows).

Enable the Rust worker in `config.json` by setting `"enable_rust_worker": true`.

## Usage

### GUI Mode
```bash
python main.py
```

### Command-line Mode
```bash
python main.py --nogui
```

### Configuration
Edit `config.json` to customize settings. Here are the available options:

```json
{
  "interval": 300,               // Capture interval in seconds (default: 300)
  "mode": "fullscreen",          // fullscreen, window, or region
  "target_window": "",          // Window title to capture (for window mode)
  "custom_region": null,        // [x, y, width, height] for region mode
  "save_path": "screenshots",   // Directory to save screenshots
  "image_format": "png",        // png or jpg
  "jpg_quality": 85,            // 1-100, only for jpg
  "max_retention_days": 30,     // 0 to disable
  "work_hours": {
    "enabled": false,           // Enable work hours scheduling
    "start": "09:00",          // Start time (24h format)
    "end": "17:00"             // End time (24h format)
  },
  "enable_tray": true,          // Show system tray icon
  "enable_notifications": true, // Show desktop notifications
  "enable_face_blur": false,    // Enable face blurring
  "enable_rust_worker": false,  // Use Rust worker for better performance
  "blur_sigma": 5.0,            // Blur strength (higher = more blur)
  "log_level": "INFO"           // DEBUG, INFO, WARNING, ERROR, CRITICAL
}
```

## Performance Notes

- The Rust worker provides significant performance improvements for face blurring and image processing.
- When enabled, the Rust worker is used automatically when `enable_face_blur` is true.
- The application falls back to Python/OpenCV if the Rust worker is not available.
- For best performance, build the Rust worker in release mode.

## Development

### Running Tests

```bash
# Run Python tests
pytest tests/

# Test Rust worker (requires Rust toolchain)
cd rust-worker
cargo test
```

### Building the Rust Worker

```bash
cd rust-worker
cargo build --release
```

The binary will be built to `rust-worker/target/release/rust_worker` (or `.exe` on Windows).

## License

MIT
