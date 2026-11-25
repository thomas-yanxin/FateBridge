"""Storage identity shared by the DE441 producer and its single live reader.

This declares selected-word storage, not a new physical ephemeris model.
"""

MODEL_ID = "lossless_de441_planetary_source_v4"
BASENAME = "de441-planetary-0001-9999-v4"
BINARY_ORDER = "little_endian_float64"
STORAGE = "source_time_chunks_original_binary64_record_byte_channels_gzip_v1"
