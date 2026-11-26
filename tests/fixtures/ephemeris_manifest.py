"""Small explicit file-identity fixtures; never an astronomy reference."""


def manifest_for_payloads(payloads):
    return {
        "schema_version": 1,
        "id": "synthetic_file_identity_fixture",
        "base_url": "https://ephemeris-test.invalid",
        "files": {name: {"bytes": len(data)} for name, data in payloads.items()},
    }
