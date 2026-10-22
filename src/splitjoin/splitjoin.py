"""Chunked file splitting and rejoining with SHA-256 verification.

Splits a file into fixed-size chunks and writes a JSON manifest recording each
chunk's filename, size, offset and SHA-256, plus the digest of the whole file.
Rejoining reads the manifest, verifies every chunk's checksum before use, and
confirms the reassembled file matches the recorded whole-file digest — so a
corrupted or tampered chunk is detected instead of silently producing a bad file.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

MANIFEST_VERSION = 1


class IntegrityError(Exception):
    """Raised when a chunk or the reassembled file fails checksum verification."""


@dataclass
class Chunk:
    name: str
    size: int
    offset: int
    sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, bufsize: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(bufsize), b""):
            h.update(block)
    return h.hexdigest()


def split_file(
    src: str | Path,
    out_dir: str | Path,
    chunk_size: int,
    prefix: str | None = None,
) -> dict:
    """Split ``src`` into ``chunk_size``-byte chunks under ``out_dir``.

    Writes a ``manifest.json`` describing the chunks and the whole-file SHA-256.
    Returns the manifest dict. ``chunk_size`` must be positive.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    src = Path(src)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prefix = prefix or src.name

    chunks: list[Chunk] = []
    whole = hashlib.sha256()
    offset = 0
    index = 0
    with open(src, "rb") as fh:
        while True:
            data = fh.read(chunk_size)
            if not data:
                break
            whole.update(data)
            name = f"{prefix}.part{index:04d}"
            (out / name).write_bytes(data)
            chunks.append(Chunk(name, len(data), offset, sha256_bytes(data)))
            offset += len(data)
            index += 1

    manifest = {
        "version": MANIFEST_VERSION,
        "original_name": src.name,
        "chunk_size": chunk_size,
        "total_size": offset,
        "whole_sha256": whole.hexdigest(),
        "chunks": [c.__dict__ for c in chunks],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def _load_manifest(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def join_file(
    chunk_dir: str | Path,
    out_path: str | Path,
    verify: bool = True,
) -> dict:
    """Reassemble the chunks described by ``chunk_dir/manifest.json``.

    Each chunk's SHA-256 is checked before concatenation; if ``verify`` is True
    the final file's digest is compared against the manifest. Raises
    ``IntegrityError`` on any mismatch. Returns a small summary dict.
    """
    chunk_dir = Path(chunk_dir)
    manifest = _load_manifest(chunk_dir / "manifest.json")
    out_path = Path(out_path)

    written = 0
    with open(out_path, "wb") as out:
        for entry in manifest["chunks"]:
            data = (chunk_dir / entry["name"]).read_bytes()
            if verify and sha256_bytes(data) != entry["sha256"]:
                raise IntegrityError(
                    f"checksum mismatch for chunk {entry['name']}"
                )
            if len(data) != entry["size"]:
                raise IntegrityError(
                    f"size mismatch for chunk {entry['name']}: "
                    f"expected {entry['size']}, got {len(data)}"
                )
            out.write(data)
            written += len(data)

    if written != manifest["total_size"]:
        raise IntegrityError(
            f"total size mismatch: expected {manifest['total_size']}, got {written}"
        )

    if verify:
        actual = sha256_file(out_path)
        if actual != manifest["whole_sha256"]:
            raise IntegrityError("reassembled file does not match whole-file digest")

    return {
        "bytes_written": written,
        "chunks": len(manifest["chunks"]),
        "verified": bool(verify),
    }
