"""
Test script for Rust worker integration.

This script tests the Rust worker integration by:
1. Creating a test image
2. Processing it with the Rust worker
3. Verifying the output
"""

import os
import sys
import json
import tempfile
import subprocess
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

# Add parent directory to path to import rust_integration
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import the Rust integration
try:
    from rust_integration import process_image_with_rust, RustWorkerError
    HAS_RUST_WORKER = True
except ImportError:
    HAS_RUST_WORKER = False

# Skip all tests if Rust worker is not available
pytestmark = pytest.mark.skipif(
    not HAS_RUST_WORKER,
    reason="Rust worker integration not available"
)

def create_test_image(path, size=(100, 100), color="red"):
    """Create a test image with the specified size and color."""
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    # Draw a simple shape to make the image non-uniform
    draw.rectangle([10, 10, 90, 90], fill="blue")
    img.save(path)
    return path

def test_rust_worker_basic():
    """Test basic Rust worker functionality with a test image."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test image
        input_path = Path(temp_dir) / "test.png"
        create_test_image(input_path, (200, 200))
        
        # Process with Rust worker
        output_path = Path(temp_dir) / "output.png"
        result = process_image_with_rust(
            image_path=input_path,
            blur_sigma=5.0,
            resize=(100, 100),
            out_path=output_path
        )
        
        # Verify results
        assert result is not None
        assert result.exists()
        assert result.stat().st_size > 0
        
        # Verify image dimensions if resized
        with Image.open(result) as img:
            assert img.size == (100, 100)

def test_rust_worker_face_blur():
    """Test face blur functionality with a test image."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a test image
        input_path = Path(temp_dir) / "test_face.png"
        create_test_image(input_path, (200, 200))
        
        # Process with face blur
        output_path = Path(temp_dir) / "blurred.png"
        result = process_image_with_rust(
            image_path=input_path,
            blur_sigma=10.0,  # Strong blur for testing
            out_path=output_path
        )
        
        # Verify results
        assert result is not None
        assert result.exists()
        
        # Simple check that the file was modified (not a perfect test)
        assert result.stat().st_size > 0
        assert result.stat().st_size != input_path.stat().st_size

def test_rust_worker_missing_binary():
    """Test behavior when Rust binary is missing."""
    # Test with a non-existent binary path
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = Path(temp_dir) / "test.png"
        create_test_image(input_path)
        
        with pytest.raises(RustWorkerError):
            process_image_with_rust(
                image_path=input_path,
                blur_sigma=5.0,
                binary_path="/path/to/nonexistent/binary"
            )

if __name__ == "__main__":
    # Simple test runner for manual testing
    print("Running Rust worker tests...")
    
    if not HAS_RUST_WORKER:
        print("Error: Rust worker integration not available")
        sys.exit(1)
    
    # Run tests
    test_rust_worker_basic()
    test_rust_worker_face_blur()
    test_rust_worker_missing_binary()
    
    print("All tests passed!")
