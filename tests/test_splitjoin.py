import json

import pytest

from splitjoin.splitjoin import (
    IntegrityError,
    join_file,
    sha256_file,
    split_file,
)


def test_roundtrip_exact_chunks(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes(b"abcdefghij")  # 10 bytes, chunk size 4 -> 3 chunks
    out_dir = tmp_path / "parts"
    m = split_file(src, out_dir, chunk_size=4)
    assert m["total_size"] == 10
    assert len(m["chunks"]) == 3
    assert m["chunks"][0]["size"] == 4
    assert m["chunks"][2]["size"] == 2

    out = tmp_path / "restored.bin"
    result = join_file(out_dir, out)
    assert out.read_bytes() == b"abcdefghij"
    assert result["verified"] is True


def test_roundtrip_identical_digest(tmp_path):
    src = tmp_path / "img.dat"
    src.write_bytes(bytes(range(256)) * 7)
    out_dir = tmp_path / "p"
    split_file(src, out_dir, chunk_size=64)
    out = tmp_path / "out.dat"
    join_file(out_dir, out)
    assert sha256_file(src) == sha256_file(out)


def test_chunk_size_must_be_positive(tmp_path):
    src = tmp_path / "a.bin"
    src.write_bytes(b"abc")
    with pytest.raises(ValueError):
        split_file(src, tmp_path / "p", chunk_size=0)


def test_detects_corrupted_chunk(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes(b"0123456789" * 5)
    out_dir = tmp_path / "p"
    split_file(src, out_dir, chunk_size=8)
    # Corrupt one chunk in place.
    victim = out_dir / "data.bin.part0001"
    victim.write_bytes(b"XXXXXXXX")
    out = tmp_path / "out.bin"
    with pytest.raises(IntegrityError):
        join_file(out_dir, out)


def test_detects_truncated_chunk(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes(b"0123456789" * 5)
    out_dir = tmp_path / "p"
    split_file(src, out_dir, chunk_size=8)
    victim = out_dir / "data.bin.part0000"
    victim.write_bytes(victim.read_bytes()[:3])  # shrink it
    out = tmp_path / "out.bin"
    with pytest.raises(IntegrityError):
        join_file(out_dir, out)


def test_no_verify_skips_digest_check(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes(b"hello world, this is a test payload")
    out_dir = tmp_path / "p"
    split_file(src, out_dir, chunk_size=10)
    # Tamper with the manifest's whole-file digest only; chunk checksums still
    # match, so verify=False must succeed even though the final digest is wrong.
    manifest_path = out_dir / "manifest.json"
    m = json.loads(manifest_path.read_text())
    m["whole_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(m))
    out = tmp_path / "out.bin"
    result = join_file(out_dir, out, verify=False)
    assert result["verified"] is False
    assert out.read_bytes() == src.read_bytes()


def test_empty_file(tmp_path):
    src = tmp_path / "empty.bin"
    src.write_bytes(b"")
    out_dir = tmp_path / "p"
    m = split_file(src, out_dir, chunk_size=16)
    assert m["total_size"] == 0 and m["chunks"] == []
    out = tmp_path / "out.bin"
    join_file(out_dir, out)
    assert out.read_bytes() == b""
