# splitjoin

Split a file into checksummed chunks and rejoin them with verification. Every
chunk carries a SHA-256 in a JSON manifest, and rejoining verifies each chunk
*and* the reassembled whole-file digest — so a corrupted or tampered chunk is
caught instead of silently producing a bad file.

## Why

`split`/`cat` round-trips are fine until a chunk goes bad in transit or at rest.
`splitjoin` writes a `manifest.json` with each chunk's size, offset and SHA-256
plus the whole-file digest, and `join` refuses to produce output that doesn't
match — turning silent corruption into a loud, early failure.

## Install

```
pip install -e .
```

## Usage

```
# Split into 1 MiB chunks
splitjoin split big.iso parts/ --chunk-size 1048576

# Rejoin, verifying every checksum
splitjoin join parts/ restored.iso
```

`join` exits `2` with an `INTEGRITY FAILURE` message on any mismatch. Pass
`--no-verify` to skip the whole-file digest check (chunk checksums still apply).

## Python API

```python
from splitjoin import split_file, join_file, IntegrityError

split_file("big.iso", "parts", chunk_size=1048576)
try:
    join_file("parts", "restored.iso")
except IntegrityError as e:
    print("corrupted:", e)
```

## License

MIT
