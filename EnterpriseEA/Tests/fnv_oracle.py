"""FNV-1a 32-bit helper and fixed test vector for RuntimeEvidence fingerprint.

The MQL EEA_RuntimeFingerprint uses FNV-1a 32-bit (not fnv1a64).
This module provides the Python implementation and a fixed test vector
matching the expected MQL output.

Usage:
    python -m unittest fnv_oracle -v
"""

import unittest

# FNV-1a 32-bit constants matching MQL implementation
FNV1A32_PRIME = 0x01000193
FNV1A32_BASIS = 0x811C9DC5


def fnv1a32_hex(server: str, account_id: str) -> str:
    """FNV-1a 32-bit hash matching MQL EEA_RuntimeFingerprint byte-for-byte."""
    h = FNV1A32_BASIS
    raw = server + "|" + account_id
    for ch in raw:
        h ^= ord(ch)
        h = (h * FNV1A32_PRIME) & 0xFFFFFFFF
    return f"fnv1a32:{h:x}"


# Fixed test vector: server="VTMarkets-Demo", account_id="12345678"
# Pre-computed expected output from the MQL implementation
FNV1A32_TEST_VECTOR = {
    "server": "VTMarkets-Demo",
    "account_id": "12345678",
    "expected": "fnv1a32:a9a2fef8",
}

# Base snapshot fingerprint: server="VTMarkets-Demo", empty account_id
FNV1A32_BASE_FINGERPRINT = "fnv1a32:b96fe430"


class TestFNV1a32(unittest.TestCase):
    def test_fnv1a32_deterministic(self):
        """FNV-1a 32-bit hash is deterministic for same inputs."""
        result1 = fnv1a32_hex("test", "123")
        result2 = fnv1a32_hex("test", "123")
        self.assertEqual(result1, result2)

    def test_fnv1a32_different_inputs(self):
        """FNV-1a 32-bit hash differs for different inputs."""
        result1 = fnv1a32_hex("test", "123")
        result2 = fnv1a32_hex("test", "456")
        self.assertNotEqual(result1, result2)

    def test_fnv1a32_format(self):
        """FNV-1a 32-bit hash uses fnv1a32: prefix with lowercase hex."""
        result = fnv1a32_hex("server", "account")
        self.assertTrue(result.startswith("fnv1a32:"))
        hex_part = result.split(":")[1]
        self.assertEqual(hex_part, hex_part.lower())
        self.assertTrue(all(c in "0123456789abcdef" for c in hex_part))

    def test_fnv1a32_fixed_vector(self):
        """Fixed test vector matching MQL expected output."""
        result = fnv1a32_hex(
            FNV1A32_TEST_VECTOR["server"],
            FNV1A32_TEST_VECTOR["account_id"]
        )
        # The test vector is computed from the MQL implementation
        # and should match the expected output exactly
        self.assertEqual(result, FNV1A32_TEST_VECTOR["expected"])

    def test_fnv1a32_base_fingerprint(self):
        """Base snapshot fingerprint for empty account_id."""
        result = fnv1a32_hex("VTMarkets-Demo", "")
        self.assertEqual(result, FNV1A32_BASE_FINGERPRINT)


if __name__ == "__main__":
    unittest.main()