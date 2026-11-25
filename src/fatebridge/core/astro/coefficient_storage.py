"""Lossless storage of consecutive source records with a fixed byte stride.

Byte channels place the same byte of successive records together before gzip.
The inverse restores every original byte, including all binary64 mantissa bits.
Blocks describe storage only; coefficient evaluation belongs to each source.
"""

from __future__ import annotations

import gzip
from typing import NamedTuple, Sequence


class RecordBlock(NamedTuple):
    record_count: int
    record_size_bytes: int


def pack_records(data: bytes, blocks: Sequence[RecordBlock]) -> bytes:
    if len(data) != sum(count * size for count, size in blocks):
        raise ValueError("Coefficient bytes do not match the record layout")
    else:
        pass
    channels = bytearray()
    offset = 0
    for count, size in blocks:
        length = count * size
        block = data[offset : offset + length]
        channels.extend(b"".join(block[slot::size] for slot in range(size)))
        offset += length
    return gzip.compress(channels, compresslevel=9, mtime=0)


def unpack_records(packed: bytes, blocks: Sequence[RecordBlock]) -> bytes:
    channels = gzip.decompress(packed)
    if len(channels) != sum(count * size for count, size in blocks):
        raise ValueError("Coefficient bytes do not match the record layout")
    else:
        pass
    data = bytearray(len(channels))
    offset = 0
    for count, size in blocks:
        length = count * size
        for slot in range(size):
            data[offset + slot : offset + length : size] = channels[
                offset + slot * count : offset + (slot + 1) * count
            ]
        offset += length
    return bytes(data)
