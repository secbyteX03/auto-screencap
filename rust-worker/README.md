# Rust Image Worker

This is an optional component for `auto-screencap` that provides fast image processing capabilities using Rust.

## Features

- **Face Blurring**: Apply gaussian blur to images
- **Image Resizing**: High-quality image resizing
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Fast**: Optimized for performance

## Building

1. Install Rust from [rustup.rs](https://rustup.rs/) if you haven't already
2. Build in release mode:
   ```bash
   cd rust-worker
   cargo build --release
   ```

The binary will be available at:
- Linux/macOS: `target/release/rust_worker`
- Windows: `target\release\rust_worker.exe`

## Usage

The worker is automatically used by `auto-screencap` when `enable_face_blur` is enabled in the config.

### Manual Testing

You can test the worker manually using JSON input:

```bash
# Windows
echo {"path":"test.png","blur_sigma":5.0} | target\release\rust_worker.exe

# Linux/macOS
echo '{"path":"test.png","blur_sigma":5.0}' | target/release/rust_worker
```

## Input/Output Format

### Input (JSON via stdin)
```json
{
  "path": "input.png",
  "blur_sigma": 5.0,
  "resize": [800, 600],
  "out_path": "output.png"
}
```

### Output (JSON via stdout)
```json
{
  "ok": true,
  "out_path": "output.png",
  "msg": "Image processed successfully"
}
```

## Error Handling

- All errors are returned as JSON with `ok: false`
- The `msg` field contains a human-readable error message
- The process will exit with non-zero status on errors
