"""Pure unit tests -- no DB needed. AES-256-GCM envelope encryption
(docs/ARCHITECTURE.md section 8.3, approved Phase 9 decision)."""

from __future__ import annotations

import pytest

from apps.payments import encryption


def test_roundtrip():
    envelope = encryption.encrypt_secret("sk_test_super_secret_12345")
    assert encryption.decrypt_secret(envelope) == "sk_test_super_secret_12345"


def test_envelope_is_versioned_and_never_contains_the_plaintext():
    envelope = encryption.encrypt_secret("sk_test_super_secret_12345")
    assert envelope.startswith("v1:")
    assert "sk_test_super_secret_12345" not in envelope


def test_two_encryptions_of_the_same_plaintext_use_different_nonces():
    """Random nonce per call (approved Phase 9 requirement) -- the two ciphertexts
    must differ even for identical plaintext, proving the nonce isn't reused."""
    first = encryption.encrypt_secret("same-secret")
    second = encryption.encrypt_secret("same-secret")
    assert first != second


def test_tampered_ciphertext_fails_to_decrypt():
    envelope = encryption.encrypt_secret("sk_test_super_secret_12345")
    version, nonce_b64, ciphertext_b64 = envelope.split(":")
    tampered_ciphertext = ciphertext_b64[:-4] + (
        "A" * 4 if ciphertext_b64[-4:] != "AAAA" else "BBBB"
    )
    tampered = f"{version}:{nonce_b64}:{tampered_ciphertext}"
    with pytest.raises(encryption.DecryptionError):
        encryption.decrypt_secret(tampered)


def test_malformed_envelope_fails_cleanly():
    with pytest.raises(encryption.DecryptionError):
        encryption.decrypt_secret("not-a-valid-envelope")


def test_wrong_key_version_is_rejected():
    envelope = encryption.encrypt_secret("sk_test_super_secret_12345")
    wrong_version_envelope = "v99:" + envelope.split(":", 1)[1]
    with pytest.raises(encryption.DecryptionError):
        encryption.decrypt_secret(wrong_version_envelope)


def test_decryption_error_message_never_contains_plaintext_or_key(settings):
    envelope = encryption.encrypt_secret("sk_test_super_secret_12345")
    tampered = envelope[:-1] + ("A" if envelope[-1] != "A" else "B")
    try:
        encryption.decrypt_secret(tampered)
    except encryption.DecryptionError as exc:
        assert "sk_test_super_secret_12345" not in str(exc)
        assert settings.PAYMENT_ENCRYPTION_KEY not in str(exc)
    else:
        pytest.fail("expected DecryptionError")


def test_mask_secret_shows_only_a_short_suffix():
    assert encryption.mask_secret("sk_test_51H8xyzABCDEF9f2c") == "****9f2c"


def test_mask_secret_on_a_short_string_masks_everything():
    assert encryption.mask_secret("ab") == "**"


def test_invalid_base64_master_key_raises_encryption_error(settings):
    settings.PAYMENT_ENCRYPTION_KEY = "not valid base64!!"
    with pytest.raises(encryption.EncryptionError):
        encryption.encrypt_secret("anything")


def test_wrong_length_master_key_raises_encryption_error(settings):
    import base64

    settings.PAYMENT_ENCRYPTION_KEY = base64.b64encode(b"too-short").decode()
    with pytest.raises(encryption.EncryptionError):
        encryption.encrypt_secret("anything")
