"""
Metadata handling for auto-screencap.

This module provides functions for saving and managing screenshot metadata.
Supports multiple storage backends (JSON, CSV, SQLite) with optional encryption.
"""

import os
import json
import csv
import sqlite3
import logging
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any, Union, Tuple, List

# Set up logger
logger = logging.getLogger("auto-screencap.metadata")

# Try to import optional dependencies
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    logger.warning("pytesseract or PIL not found. OCR summaries will be disabled.")

# Try to import crypto_utils for encryption
try:
    from .crypto_utils import (
        encrypt_data as crypto_encrypt,
        decrypt_data as crypto_decrypt,
        is_encrypted as is_data_encrypted,
        ensure_encryption_key,
        EncryptionError as CryptoError
    )
    HAS_CRYPTO = True
except ImportError as e:
    HAS_CRYPTO = False
    logger.warning(f"crypto_utils not available. Metadata encryption will be disabled: {e}")

class MetadataEncryptionError(Exception):
    """Exception raised for errors in metadata encryption/decryption."""
    pass

class MetadataStorageError(Exception):
    """Exception raised for errors in metadata storage operations."""
    pass

def _prepare_encryption_key(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Prepare the encryption key from config.
    
    Args:
        config: Application configuration
        
    Returns:
        Encryption key as string or None if encryption is disabled
        
    Raises:
        MetadataEncryptionError: If encryption is enabled but no key is available
    """
    if not HAS_CRYPTO:
        if config and config.get('enable_metadata_encryption', False):
            raise MetadataEncryptionError(
                "Encryption is enabled but crypto_utils is not available. "
                "Install with: pip install cryptography"
            )
        return None
    
    if not config or not config.get('enable_metadata_encryption', False):
        return None
    
    try:
        return ensure_encryption_key(config)
    except CryptoError as e:
        raise MetadataEncryptionError(f"Failed to prepare encryption key: {e}")

def encrypt_metadata(metadata: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Encrypt sensitive metadata values.
    
    Args:
        metadata: Dictionary of metadata
        key: Encryption key
        
    Returns:
        New dictionary with sensitive values encrypted
    """
    if not key or not HAS_CRYPTO:
        return metadata
    
    # Create a copy to avoid modifying the original
    result = metadata.copy()
    
    # Fields to encrypt
    sensitive_fields = ['note', 'window_title', 'app_name', 'ocr_text']
    
    for field in sensitive_fields:
        if field in result and result[field]:
            try:
                # Convert to string if needed
                value = str(result[field])
                # Encrypt and store as base64 string
                result[f'encrypted_{field}'] = crypto_encrypt(value, key)
                # Remove the original field
                del result[field]
            except Exception as e:
                logger.error(f"Failed to encrypt field '{field}': {e}")
    
    # Mark that this metadata contains encrypted fields
    if any(k.startswith('encrypted_') for k in result):
        result['_encrypted'] = True
    
    return result

def decrypt_metadata(metadata: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Decrypt encrypted metadata values.
    
    Args:
        metadata: Dictionary of metadata with encrypted fields
        key: Encryption key
        
    Returns:
        New dictionary with encrypted values decrypted
    """
    if not key or not HAS_CRYPTO or not metadata.get('_encrypted'):
        return metadata
    
    # Create a copy to avoid modifying the original
    result = metadata.copy()
    
    # Find all encrypted fields
    encrypted_fields = [k for k in result if k.startswith('encrypted_')]
    
    for enc_field in encrypted_fields:
        # Extract the original field name
        field = enc_field[9:]  # Remove 'encrypted_' prefix
        
        try:
            # Decrypt the value
            decrypted = crypto_decrypt(result[enc_field], key)
            # Store the decrypted value
            result[field] = decrypted.decode('utf-8')
            # Remove the encrypted field
            del result[enc_field]
        except Exception as e:
            logger.error(f"Failed to decrypt field '{field}': {e}")
    
    # Remove the encryption marker
    if '_encrypted' in result:
        del result['_encrypted']
    
    return result

def generate_ocr_summary(image_path: str) -> Optional[str]:
    """Generate a text summary of an image using OCR.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text or None if OCR fails or is not available
    """
    if not HAS_OCR:
        logger.warning("OCR dependencies not available. Install pytesseract and PIL for OCR support.")
        return None
    
    try:
        # Open the image
        with Image.open(image_path) as img:
            # Convert to grayscale for better OCR
            if img.mode != 'L':
                img = img.convert('L')
            
            # Use pytesseract to extract text
            text = pytesseract.image_to_string(img)
            
            # Clean up the text
            text = ' '.join(text.split())
            return text if text.strip() else None
    
    except Exception as e:
        logger.error(f"OCR processing failed: {e}")
        return None

def save_metadata_json(
    image_path: str,
    metadata: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Save metadata as a JSON sidecar file.
    
    Args:
        image_path: Path to the image file
        metadata: Dictionary of metadata to save
        config: Application configuration (for encryption settings)
        
    Raises:
        MetadataStorageError: If saving fails
        MetadataEncryptionError: If encryption is enabled but fails
    """
    if config is None:
        config = {}
        
    json_path = f"{image_path}.json"
    
    try:
        # Prepare encryption key if needed
        enc_key = None
        if config.get('enable_metadata_encryption', False):
            enc_key = _prepare_encryption_key(config)
            if enc_key:
                metadata = encrypt_metadata(metadata, enc_key)
        
        # Convert to JSON
        json_data = json.dumps(metadata, indent=2, ensure_ascii=False, default=str)
        
        # Write to file
        with open(json_path, 'w', encoding='utf-8') as f:
            f.write(json_data)
            
        logger.debug(f"Saved metadata to {json_path}")
        
    except Exception as e:
        if isinstance(e, MetadataEncryptionError):
            raise
        raise MetadataStorageError(f"Failed to save JSON metadata: {e}")

def save_metadata_csv(
    image_path: str,
    metadata: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Append metadata to a CSV file in the same directory as the image.
    
    Args:
        image_path: Path to the image file
        metadata: Dictionary of metadata to save
        config: Application configuration (for encryption settings)
        
    Raises:
        MetadataStorageError: If saving fails
        MetadataEncryptionError: If encryption is enabled but fails
    """
    if config is None:
        config = {}
        
    csv_path = os.path.join(os.path.dirname(image_path), "screenshots_metadata.csv")
    
    try:
        # Prepare encryption key if needed
        enc_key = None
        if config.get('enable_metadata_encryption', False):
            enc_key = _prepare_encryption_key(config)
            if enc_key:
                metadata = encrypt_metadata(metadata, enc_key)
        
        # Prepare the data for CSV
        row_data = metadata.copy()
        row_data['image_path'] = os.path.basename(image_path)
        row_data['timestamp'] = datetime.now().isoformat()
        
        # Check if file exists to determine if we need to write headers
        file_exists = os.path.isfile(csv_path)
        
        # Open the CSV file in append mode
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            # Get fieldnames from data, ensuring consistent order
            fieldnames = list(row_data.keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            # Write header if file is new
            if not file_exists:
                writer.writeheader()
                
            # Write the row
            writer.writerow(row_data)
            
        logger.debug(f"Appended metadata to {csv_path}")
        
        # Handle encryption if needed
        if config and config.get('encrypt_metadata'):
            # Generate a unique salt for this chunk
            salt = os.urandom(16)
            encryption_key = _prepare_encryption_key(config)
            if encryption_key:
                file_key, _ = generate_encryption_key(encryption_key.hex(), salt)
                
                # Encrypt the row data
                json_data = json.dumps(row_data, ensure_ascii=False)
                encrypted = encrypt_data(json_data.encode('utf-8'), file_key)
                
                # Save salt + encrypted data
                chunk_path = f"{csv_path}.enc"
                with open(chunk_path, 'wb') as f:
                    f.write(salt + encrypted)
        else:
            # Append to plain CSV
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
    
    except Exception as e:
        raise MetadataStorageError(f"Failed to save CSV metadata: {e}")

def save_metadata_sqlite(
    image_path: str,
    metadata: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Save metadata to an SQLite database.
    
    Args:
        image_path: Path to the image file
        metadata: Dictionary of metadata to save
        config: Application configuration (for encryption settings)
        
    Raises:
        MetadataStorageError: If saving fails
        MetadataEncryptionError: If encryption is enabled but fails
    """
    if config is None:
        config = {}
        
    db_path = os.path.join(os.path.dirname(image_path), 'screenshots_metadata.db')
    
    try:
        # Prepare encryption key if needed
        enc_key = None
        if config.get('enable_metadata_encryption', False):
            enc_key = _prepare_encryption_key(config)
            if enc_key:
                metadata = encrypt_metadata(metadata, enc_key)
        
        # Ensure timestamp exists
        if 'timestamp' not in metadata:
            metadata['timestamp'] = datetime.now().isoformat()
        
        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            image_path TEXT NOT NULL,
            note TEXT,
            window_title TEXT,
            app_name TEXT,
            ocr_summary TEXT,
            extra_data TEXT,
            is_encrypted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Prepare the data for insertion
        row_data = {
            'timestamp': metadata.get('timestamp'),
            'image_path': os.path.basename(image_path),
            'note': metadata.get('note'),
            'window_title': metadata.get('window_title'),
            'app_name': metadata.get('app_name'),
            'ocr_summary': metadata.get('ocr_summary'),
            'extra_data': json.dumps(metadata.get('extra', {})),
            'is_encrypted': 1 if enc_key and metadata.get('_encrypted') else 0
        }
        
        # Prepare the metadata blob if encryption is enabled
        metadata_blob = None
        if enc_key and metadata.get('_encrypted'):
            # Generate a unique salt for this record
            salt = os.urandom(16)
            file_key, _ = generate_encryption_key(enc_key.hex(), salt)
            
            # Encrypt the metadata
            json_data = json.dumps(metadata, ensure_ascii=False)
            encrypted = encrypt_data(json_data.encode('utf-8'), file_key)
            metadata_blob = salt + encrypted
        
        # Insert or replace the record
        cursor.execute('''
        INSERT OR REPLACE INTO screenshots 
        (timestamp, image_path, note, window_title, app_name, ocr_summary, metadata_blob, is_encrypted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp, 
            image_name, 
            note, 
            window_title, 
            app_name, 
            ocr_summary, 
            metadata_blob,
            1 if metadata_blob else 0
        ))
        
        conn.commit()
        
    except Exception as e:
        raise MetadataStorageError(f"Failed to save SQLite metadata: {e}")
    
    finally:
        if 'conn' in locals():
            conn.close()

def save_metadata(
    image_path: str,
    note: Optional[str] = None,
    auto_summary: bool = False,
    extra: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> None:
    """Save metadata for a screenshot.
    
    Args:
        image_path: Path to the screenshot image
        note: Optional note to include with the screenshot
        auto_summary: Whether to generate an OCR summary
        extra: Additional metadata to include
        config: Application configuration (defaults to empty dict)
    """
    if config is None:
        config = {}
    
    if not config.get('enable_notes', False):
        return
    
    try:
        # Prepare metadata dictionary
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'note': note or '',
            'window_title': extra.get('window_title', '') if extra else '',
            'app_name': extra.get('app_name', '') if extra else '',
            **(extra or {})
        }
        
        # Generate OCR summary if requested
        if auto_summary and config.get('auto_summary_ocr', False):
            ocr_text = generate_ocr_summary(image_path)
            if ocr_text:
                metadata['ocr_summary'] = ocr_text
        
        # Get encryption key if enabled
        encryption_key = None
        if config.get('enable_metadata_encryption', False):
            passphrase = config.get('metadata_encryption_key', '')
            if not passphrase:
                logger.warning("Encryption enabled but no passphrase provided in config")
            else:
                # Derive a consistent key from the passphrase
                encryption_key = generate_encryption_key(passphrase)[0]
        
        # Save using the configured storage backend
        storage_backend = config.get('metadata_store', 'json').lower()
        
        if storage_backend == 'csv':
            save_metadata_csv(image_path, metadata, encryption_key)
        elif storage_backend == 'sqlite':
            save_metadata_sqlite(image_path, metadata, encryption_key)
        else:  # Default to JSON
            save_metadata_json(image_path, metadata, encryption_key)
    
    except Exception as e:
        logger.error(f"Failed to save metadata: {e}", exc_info=True)
