"""
Integration with Rust image processing worker.

This module provides a Python interface to the optional Rust image processing worker.
The worker provides faster image processing (blur, resize) compared to pure Python.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Set up logger
logger = logging.getLogger("auto-screencap.rust")

# Binary name with platform-specific extension
BINARY_NAME = "rust_worker" + ('.exe' if platform.system() == 'Windows' else '')

# Default search paths for the binary
DEFAULT_SEARCH_PATHS = [
    # Development location
    Path(__file__).parent / "rust-worker" / "target" / "release" / BINARY_NAME,
    # Installed location (if installed in PATH)
    Path(BINARY_NAME),
]

class RustWorkerError(Exception):
    """Exception raised for errors in the Rust worker integration."""
    pass

def find_rust_binary(search_paths: Optional[List[Union[str, Path]]] = None) -> Optional[Path]:
    """
    Locate the Rust worker binary.
    
    Args:
        search_paths: Optional list of paths to search for the binary.
                     If None, uses DEFAULT_SEARCH_PATHS.
    
    Returns:
        Path to the binary if found, None otherwise.
    """
    if search_paths is None:
        search_paths = DEFAULT_SEARCH_PATHS
    
    for path in search_paths:
        path = Path(path)
        if path.is_file():
            # Make sure it's executable on Unix-like systems
            if platform.system() != 'Windows' and not os.access(path, os.X_OK):
                try:
                    path.chmod(0o755)  # Make it executable
                except Exception as e:
                    logger.warning(f"Found binary at {path} but couldn't make it executable: {e}")
                    continue
            return path.resolve()
    
    return None

def call_rust_worker(
    image_path: Union[str, Path],
    blur_sigma: Optional[float] = None,
    resize: Optional[Tuple[int, int]] = None,
    out_path: Optional[Union[str, Path]] = None,
    binary_path: Optional[Union[str, Path]] = None,
) -> Dict:
    """
    Call the Rust worker to process an image.
    
    Args:
        image_path: Path to the input image.
        blur_sigma: Sigma value for gaussian blur (None to disable).
        resize: Optional (width, height) to resize the image.
        out_path: Optional output path. If None, appends "_processed" to the input filename.
        binary_path: Optional path to the Rust binary. If None, will search for it.
    
    Returns:
        Dictionary with the response from the Rust worker.
        
    Raises:
        RustWorkerError: If the binary is not found or the worker fails.
    """
    # Convert paths to strings for JSON serialization
    image_path = str(Path(image_path).resolve())
    out_path = str(Path(out_path).resolve()) if out_path else None
    
    # Prepare the request
    request = {
        "path": image_path,
        "blur_sigma": blur_sigma,
        "out_path": out_path,
    }
    
    if resize:
        request["resize"] = list(resize)
    
    # Find the binary if not provided
    if binary_path is None:
        binary_path = find_rust_binary()
        if binary_path is None:
            raise RustWorkerError(
                "Rust worker binary not found. "
                "Please build it with 'cargo build --release' in the rust-worker directory."
            )
    
    binary_path = str(binary_path)
    
    try:
        # Run the binary with JSON input
        result = subprocess.run(
            [binary_path],
            input=json.dumps(request).encode('utf-8'),
            capture_output=True,
            check=True
        )
        
        # Parse the response
        response = json.loads(result.stdout.decode('utf-8'))
        
        if not response.get('ok', False):
            raise RustWorkerError(f"Rust worker failed: {response.get('msg', 'Unknown error')}")
            
        return response
        
    except subprocess.CalledProcessError as e:
        try:
            error_msg = json.loads(e.stderr.decode('utf-8')).get('msg', e.stderr.decode('utf-8'))
        except:
            error_msg = e.stderr.decode('utf-8', errors='replace')
            
        raise RustWorkerError(f"Rust worker process failed: {error_msg}") from e
        
    except json.JSONDecodeError as e:
        raise RustWorkerError(f"Invalid JSON response from Rust worker: {e}") from e
        
    except Exception as e:
        raise RustWorkerError(f"Error calling Rust worker: {e}") from e

def process_image_with_rust(
    image_path: Union[str, Path],
    blur_sigma: Optional[float] = None,
    resize: Optional[Tuple[int, int]] = None,
    out_path: Optional[Union[str, Path]] = None,
    binary_path: Optional[Union[str, Path]] = None,
) -> Optional[Path]:
    """
    Process an image using the Rust worker with graceful fallback.
    
    Args:
        image_path: Path to the input image.
        blur_sigma: Sigma value for gaussian blur (None to disable).
        resize: Optional (width, height) to resize the image.
        out_path: Optional output path. If None, appends "_processed" to the input filename.
        binary_path: Optional path to the Rust binary. If None, will search for it.
    
    Returns:
        Path to the processed image if successful, None if the worker is not available.
    """
    try:
        response = call_rust_worker(
            image_path=image_path,
            blur_sigma=blur_sigma,
            resize=resize,
            out_path=out_path,
            binary_path=binary_path,
        )
        return Path(response['out_path'])
    except RustWorkerError as e:
        logger.warning(f"Rust worker not available: {e}")
        return None

# Example usage
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <image_path> [blur_sigma]")
        sys.exit(1)
    
    image_path = sys.argv[1]
    blur_sigma = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    
    try:
        result = process_image_with_rust(
            image_path=image_path,
            blur_sigma=blur_sigma,
            resize=(800, 600)  # Optional: resize to 800x600
        )
        
        if result:
            print(f"Processed image saved to: {result}")
        else:
            print("Rust worker not available")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
