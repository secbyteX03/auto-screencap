"""Tests for metadata functionality."""

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from metadata_utils import (
    save_metadata,
    MetadataStorageError,
    MetadataEncryptionError
)

class TestMetadata(unittest.TestCase):
    """Test metadata functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_image = os.path.join(self.test_dir, "test.png")
        
        # Create a dummy image file
        with open(self.test_image, 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\x0f\x10\x8f\x04\x83\x00\x00\x00\x00IEND\xaeB`\x82')
    
    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_save_metadata_json(self):
        """Test saving metadata as JSON."""
        config = {
            'enable_notes': True,
            'metadata_store': 'json'
        }
        
        save_metadata(
            self.test_image,
            note="Test note",
            extra={'window_title': 'Test Window', 'app_name': 'TestApp'},
            config=config
        )
        
        # Check that JSON file was created
        json_path = f"{self.test_image}.json"
        self.assertTrue(os.path.exists(json_path))
        
        # Check JSON content
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.assertEqual(data['note'], 'Test note')
        self.assertEqual(data['window_title'], 'Test Window')
        self.assertEqual(data['app_name'], 'TestApp')
    
    def test_save_metadata_csv(self):
        """Test saving metadata as CSV."""
        config = {
            'enable_notes': True,
            'metadata_store': 'csv'
        }
        
        save_metadata(
            self.test_image,
            note="CSV Test",
            extra={'window_title': 'CSV Window', 'app_name': 'CSVApp'},
            config=config
        )
        
        # Check that CSV file was created
        csv_path = os.path.join(self.test_dir, 'screenshots_log.csv')
        self.assertTrue(os.path.exists(csv_path))
        
        # Check CSV content
        import csv
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['note'], 'CSV Test')
        self.assertEqual(rows[0]['window_title'], 'CSV Window')
    
    @patch('metadata_utils.HAS_CRYPTO', True)
    @patch('metadata_utils.generate_encryption_key')
    @patch('metadata_utils.encrypt_data')
    def test_metadata_encryption(self, mock_encrypt, mock_gen_key):
        """Test metadata encryption."""
        # Setup mocks
        mock_key = b'0123456789abcdef0123456789abcdef'
        mock_gen_key.return_value = (mock_key, b'salt1234')
        mock_encrypt.return_value = b'encrypted_data'
        
        config = {
            'enable_notes': True,
            'enable_metadata_encryption': True,
            'metadata_encryption_key': 'testpass',
            'metadata_store': 'json'
        }
        
        save_metadata(
            self.test_image,
            note="Encrypted Note",
            config=config
        )
        
        # Check that encryption was attempted
        mock_gen_key.assert_called_once()
        mock_encrypt.assert_called_once()
        
        # Check that encrypted file was created
        json_path = f"{self.test_image}.json"
        self.assertTrue(os.path.exists(json_path))
        
        # Check that the file contains the expected encrypted data
        with open(json_path, 'rb') as f:
            content = f.read()
            self.assertEqual(content, b'salt1234encrypted_data')
    
    @patch('metadata_utils.HAS_OCR', True)
    @patch('pytesseract.image_to_string')
    def test_ocr_summary(self, mock_ocr):
        """Test OCR summary generation."""
        # Setup mock
        mock_ocr.return_value = "This is test OCR text"
        
        config = {
            'enable_notes': True,
            'auto_summary_ocr': True,
            'metadata_store': 'json'
        }
        
        save_metadata(
            self.test_image,
            auto_summary=True,
            config=config
        )
        
        # Check that OCR was called
        mock_ocr.assert_called_once()
        
        # Check that OCR text was saved
        json_path = f"{self.test_image}.json"
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.assertEqual(data['ocr_summary'], 'This is test OCR text')

if __name__ == '__main__':
    unittest.main()
