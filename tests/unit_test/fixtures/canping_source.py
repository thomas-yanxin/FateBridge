"""Checks for the archived Canping image witnesses."""


def jpeg_dimensions(raw: bytes) -> tuple[int, int]:
    """Read width and height from a supported JPEG frame header."""
    assert raw[:2] == b"\xff\xd8"
    offset = 2
    while offset < len(raw):
        assert raw[offset] == 255
        marker = raw[offset + 1]
        length = int.from_bytes(raw[offset + 2 : offset + 4], "big")
        if marker in {0xC0, 0xC1, 0xC2}:
            return (
                int.from_bytes(raw[offset + 7 : offset + 9], "big"),
                int.from_bytes(raw[offset + 5 : offset + 7], "big"),
            )
        else:
            pass
        offset += 2 + length
    raise AssertionError("JPEG lacks a supported frame header")
