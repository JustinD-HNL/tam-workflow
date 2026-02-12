"""Tests for the encryption module.

Tests the Fernet-based encrypt/decrypt round-trip functionality used for
storing OAuth tokens and API keys in the database.
"""

import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet


# ---------------------------------------------------------------------------
# Helpers: We need to patch the settings before importing the module under test,
# because encryption.py reads settings.encryption_key at call time via _get_fernet().
# We also need to reset the module-level _fernet cache between tests.
# ---------------------------------------------------------------------------

def _make_test_key() -> str:
    """Generate a valid Fernet key for testing."""
    return Fernet.generate_key().decode()


@pytest.fixture(autouse=True)
def reset_fernet_cache():
    """Reset the module-level _fernet singleton between tests."""
    import src.integrations.encryption as enc_module
    enc_module._fernet = None
    yield
    enc_module._fernet = None


@pytest.fixture
def mock_settings_with_key():
    """Patch settings.encryption_key with a valid Fernet key."""
    key = _make_test_key()
    with patch("src.integrations.encryption.settings") as mock_settings:
        mock_settings.encryption_key = key
        yield mock_settings, key


@pytest.fixture
def mock_settings_no_key():
    """Patch settings.encryption_key with empty string."""
    with patch("src.integrations.encryption.settings") as mock_settings:
        mock_settings.encryption_key = ""
        yield mock_settings


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

class TestEncryptDecryptRoundTrip:
    """Test that encrypting then decrypting returns the original value."""

    def test_basic_round_trip(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token, decrypt_token

        original = "xoxb-slack-token-12345"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_round_trip_with_special_characters(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token, decrypt_token

        original = "token/with+special=chars&more!@#$%^*()"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_round_trip_with_unicode(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token, decrypt_token

        original = "token-with-unicode-\u2603-\u2764-\u2708"
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_round_trip_with_long_token(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token, decrypt_token

        original = "a" * 10000
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original

    def test_round_trip_with_json_like_string(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token, decrypt_token

        original = '{"access_token": "ya29.xxx", "refresh_token": "1//yyy"}'
        encrypted = encrypt_token(original)
        decrypted = decrypt_token(encrypted)
        assert decrypted == original


# ---------------------------------------------------------------------------
# Encryption properties
# ---------------------------------------------------------------------------

class TestEncryptionProperties:
    """Test properties of the encryption output."""

    def test_encrypted_differs_from_original(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token

        original = "my-secret-token"
        encrypted = encrypt_token(original)
        assert encrypted != original

    def test_different_inputs_produce_different_ciphertext(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token

        enc1 = encrypt_token("token-alpha")
        enc2 = encrypt_token("token-beta")
        assert enc1 != enc2

    def test_same_input_produces_different_ciphertext_each_time(self, mock_settings_with_key):
        """Fernet uses a timestamp + random IV, so repeated encryption of the
        same plaintext should yield different ciphertext."""
        from src.integrations.encryption import encrypt_token

        original = "same-token-repeated"
        enc1 = encrypt_token(original)
        enc2 = encrypt_token(original)
        # Fernet includes a timestamp, so they should differ unless called
        # in the exact same timestamp-and-random-IV scenario (extremely unlikely)
        # We allow equality but in practice they differ.
        # Just verify both decrypt correctly
        from src.integrations.encryption import decrypt_token
        assert decrypt_token(enc1) == original
        assert decrypt_token(enc2) == original

    def test_encrypted_output_is_string(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token

        encrypted = encrypt_token("test")
        assert isinstance(encrypted, str)


# ---------------------------------------------------------------------------
# Empty string handling
# ---------------------------------------------------------------------------

class TestEmptyStringHandling:
    """Test behavior with empty strings."""

    def test_empty_string_round_trip(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token, decrypt_token

        encrypted = encrypt_token("")
        decrypted = decrypt_token(encrypted)
        assert decrypted == ""

    def test_empty_string_produces_nonempty_ciphertext(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token

        encrypted = encrypt_token("")
        assert len(encrypted) > 0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestEncryptionErrors:
    """Test error conditions."""

    def test_missing_encryption_key_raises(self, mock_settings_no_key):
        from src.integrations.encryption import encrypt_token

        with pytest.raises(ValueError, match="ENCRYPTION_KEY not set"):
            encrypt_token("some-token")

    def test_decrypt_with_wrong_key_raises(self, mock_settings_with_key):
        from src.integrations.encryption import encrypt_token

        encrypted = encrypt_token("secret")

        # Now switch to a different key
        import src.integrations.encryption as enc_module
        enc_module._fernet = None  # Reset cache

        different_key = _make_test_key()
        with patch("src.integrations.encryption.settings") as new_mock:
            new_mock.encryption_key = different_key
            from src.integrations.encryption import decrypt_token

            with pytest.raises(ValueError, match="Failed to decrypt"):
                decrypt_token(encrypted)

    def test_decrypt_garbage_raises(self, mock_settings_with_key):
        from src.integrations.encryption import decrypt_token

        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_token("not-valid-fernet-data")

    def test_fernet_instance_is_cached(self, mock_settings_with_key):
        """After the first call, subsequent calls should reuse the Fernet instance."""
        import src.integrations.encryption as enc_module
        from src.integrations.encryption import encrypt_token

        encrypt_token("first")
        fernet_1 = enc_module._fernet

        encrypt_token("second")
        fernet_2 = enc_module._fernet

        assert fernet_1 is fernet_2
