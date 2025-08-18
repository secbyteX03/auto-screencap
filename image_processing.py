"""
Image processing functionality for auto-screencap.
Includes face detection and blurring features.
"""
import logging
from typing import Optional, Tuple

logger = logging.getLogger("auto-screencap.image_processing")

# Try to import optional dependencies
try:
    import cv2
    import numpy as np
    from PIL import Image
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    logger.warning("OpenCV not available. Face blurring will be disabled.")

class ImageProcessor:
    """Handles image processing tasks like face blurring."""
    
    def __init__(self, blur_strength: int = 30, min_face_size: Tuple[int, int] = (30, 30)):
        """Initialize the image processor.
        
        Args:
            blur_strength: Strength of the Gaussian blur (higher = more blur)
            min_face_size: Minimum face size to detect (width, height)
        """
        self.blur_strength = blur_strength
        self.min_face_size = min_face_size
        self._face_cascade = None
        
    def blur_faces(self, image):
        """Detect and blur faces in the given image.
        
        Args:
            image: PIL Image to process
            
        Returns:
            PIL.Image: Processed image with faces blurred
        """
        if not HAS_OPENCV:
            logger.warning("OpenCV not available. Cannot blur faces.")
            return image
            
        try:
            # Convert PIL Image to OpenCV format (BGR)
            img_array = np.array(image)
            
            # Convert RGB to BGR if needed
            if len(img_array.shape) == 3 and img_array.shape[2] == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
            
            # Load the pre-trained face detector if not already loaded
            if self._face_cascade is None:
                self._load_face_cascade()
                if self._face_cascade is None:
                    return image
            
            # Detect faces in the image
            faces = self._face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=self.min_face_size,
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # Blur each detected face
            for (x, y, w, h) in faces:
                # Extract the region of interest (face)
                face_roi = img_array[y:y+h, x:x+w]
                
                # Apply Gaussian blur to the face region
                # Use odd kernel size for Gaussian blur
                ksize = (99, 99)  # Must be odd
                face_roi = cv2.GaussianBlur(face_roi, ksize, self.blur_strength)
                
                # Put the blurred face back into the image
                img_array[y:y+h, x:x+w] = face_roi
            
            # Convert back to RGB for PIL
            if len(img_array.shape) == 3:
                img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                
            return Image.fromarray(img_array)
            
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return image  # Return original image on error
    
    def _load_face_cascade(self):
        """Load the pre-trained face cascade classifier."""
        try:
            # Try different possible paths for the cascade file
            cascade_paths = [
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml',
                'haarcascade_frontalface_default.xml',
                '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml'
            ]
            
            for path in cascade_paths:
                try:
                    self._face_cascade = cv2.CascadeClassifier(path)
                    if not self._face_cascade.empty():
                        logger.debug(f"Loaded face cascade from {path}")
                        return
                except Exception as e:
                    continue
            
            logger.error("Could not load face detection model. Face blurring disabled.")
            self._face_cascade = None
            
        except Exception as e:
            logger.error(f"Error loading face cascade: {e}")
            self._face_cascade = None
