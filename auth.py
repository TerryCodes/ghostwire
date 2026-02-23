import secrets
from nanoid import generate

# Custom alphabet for nanoid (default URL-safe base64)
DEFAULT_ALPHABET = "_~0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def generate_token():
    """Generate a 43-character nanoid token that decodes to 32 bytes for AES-256"""
    # 43 chars * 6 bits = 258 bits = 32.25 bytes (we use first 32 bytes)
    return generate(size=43)

def nanoid_to_bytes(token):
    """Convert nanoid string to bytes (32 bytes for 43-char token)"""
    # Map each character to its 6-bit value
    result = bytearray()
    buffer = 0
    bits_in_buffer = 0

    for char in token:
        value = DEFAULT_ALPHABET.index(char)
        buffer = (buffer << 6) | value
        bits_in_buffer += 6

        if bits_in_buffer >= 8:
            byte = (buffer >> (bits_in_buffer - 8)) & 0xFF
            result.append(byte)
            bits_in_buffer -= 8

    # Ensure we have exactly 32 bytes
    while len(result) < 32:
        result.append(0)

    return bytes(result[:32])

def validate_token(token,expected_token):
    if len(token)!=len(expected_token):
        return False
    return secrets.compare_digest(token,expected_token)
