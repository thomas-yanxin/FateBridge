"""Small explicit file-identity fixtures; never an astronomy reference."""

import hashlib


def manifest_for_payloads(payloads):
    return {
        "schema_version": 1,
        "id": "synthetic_file_identity_fixture",
        "base_url": "https://ephemeris-test.invalid",
        "files": {
            name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in payloads.items()
        },
    }
