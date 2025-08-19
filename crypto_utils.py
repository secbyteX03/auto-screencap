"""
Cryptographic utilities for secure metadata storage.

This module provides functions for encrypting and decrypting metadata
using AES-256-CBC with PBKDF2 key derivation and PKCS7 padding.
"""

import os
import base64
import hashlib
import logging
from typing import Tuple, Optional, Union, Dict, Any

# Third-party imports
try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

logger = logging.getLogger("auto-screencap.crypto")

class EncryptionError(Exception):
    """Exception raised for errors in the encryption/decryption process."""
    pass

def derive_key(passphrase: Union[str, bytes], salt: bytes) -> bytes:
    """Derive a secure encryption key from a passphrase and salt.
    
    Args:
        passphrase: The passphrase to derive the key from
        salt: Random salt value
        
    Returns:
        bytes: Derived key (32 bytes for AES-256)
    """
    if not HAS_CRYPTOGRAPHY:
        raise EncryptionError("cryptography module not available")
    
    if isinstance(passphrase, str):
        passphrase = passphrase.encode('utf-8')
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256 bits for AES-256
        salt=salt,
        iterations=100000,  # High iteration count for security
        backend=default_backend()
    )
    
    return kdf.derive(passphrase)

def encrypt_data(data: Union[str, bytes], passphrase: str) -> str:
    """Encrypt data using AES-256-CBC with PBKDF2 key derivation.
    
    Args:
        data: The data to encrypt (string or bytes)
        passphrase: The passphrase to use for encryption
        
    Returns:
        str: Base64-encoded encrypted data with salt and IV prepended
        
    Raises:
        EncryptionError: If encryption fails or cryptography is not available
    """
    if not HAS_CRYPTOGRAPHY:
        raise EncryptionError("cryptography module not available")
    
    try:
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        # Generate random salt and IV
        salt = os.urandom(16)  # 128-bit salt
        iv = os.urandom(16)    # 128-bit IV for AES-CBC
        
        # Derive key from passphrase and salt
        key = derive_key(passphrase, salt)
        
        # Pad the data to be a multiple of the block size
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(data) + padder.finalize()
        
        # Encrypt the data
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine salt + iv + encrypted_data and base64 encode
        combined = salt + iv + encrypted_data
        return base64.b64encode(combined).decode('ascii')
        
    except Exception as e:
        logger.error(f"Encryption failed: {e}", exc_info=True)
        raise EncryptionError(f"Failed to encrypt data: {e}")

def decrypt_data(encrypted_data: str, passphrase: str) -> bytes:
    """Decrypt data that was encrypted with encrypt_data().
    
    Args:
        encrypted_data: Base64-encoded encrypted data with salt and IV
        passphrase: The passphrase used for encryption
        
    Returns:
        bytes: Decrypted data
        
    Raises:
        EncryptionError: If decryption fails, data is corrupted, or cryptography is not available
    """
    if not HAS_CRYPTOGRAPHY:
        raise EncryptionError("cryptography module not available")
    
    try:
        # Decode base64
        combined = base64.b64decode(encrypted_data)
        
        # Extract salt (16 bytes), IV (16 bytes), and encrypted data
        if len(combined) < 32:  # salt + IV = 32 bytes
            raise ValueError("Invalid encrypted data format")
            
        salt = combined[:16]
        iv = combined[16:32]
        encrypted_data = combined[32:]
        
        # Derive the same key
        key = derive_key(passphrase, salt)
        
        # Decrypt the data
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
        
        # Unpad the data
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded_data) + unpadder.finalize()
        
    except Exception as e:
        logger.error(f"Decryption failed: {e}", exc_info=True)
        raise EncryptionError(f"Failed to decrypt data: {e}")

def is_encrypted(data: str) -> bool:
    """Check if a string appears to be encrypted data.
    
    Args:
        data: The data to check
        
    Returns:
        bool: True if the data appears to be encrypted, False otherwise
    """
    try:
        # Check if it's base64 encoded
        decoded = base64.b64decode(data)
        # Should have at least salt (16) + IV (16) + some data
        return len(decoded) >= 32
    except Exception:
        return False

def ensure_encryption_key(config: Dict[str, Any]) -> str:
    """Ensure an encryption key is available in the config.
    
    If no key is set and encryption is enabled, this will generate a new key
    and update the config.
    
    Args:
        config: The application configuration
        
    Returns:
        str: The encryption key
        
    Raises:
        EncryptionError: If encryption is enabled but no key is provided or generated
    """
    if not config.get('enable_metadata_encryption', False):
        return ''
    
    # If a key is already set, use it
    key = config.get('metadata_encryption_key')
    if key:
        return key
    
    # Try to get key from environment
    key = os.environ.get('AUTO_SCREENCAP_ENCRYPTION_KEY')
    if key:
        config['metadata_encryption_key'] = key
        return key
    
    # Generate a new key if none exists
    try:
        key = base64.b64encode(os.urandom(32)).decode('ascii')
        config['metadata_encryption_key'] = key
        logger.warning("Generated new encryption key. Make sure to save your config!")
        return key
    except Exception as e:
        raise EncryptionError(f"Failed to generate encryption key: {e}")
