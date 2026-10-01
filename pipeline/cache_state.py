"""Encrypt/decrypt Actions recovery state; plaintext never leaves the runner."""
from __future__ import annotations

import argparse
import io
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT = b"HighlanderHub-pipeline-cache-v1\0"


def cache_key() -> bytes:
    value = os.environ.get("PIPELINE_CACHE_KEY", "")
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("PIPELINE_CACHE_KEY must be 32 random bytes encoded as lowercase hex")
    return bytes.fromhex(value)


def encrypt(directory: Path, destination: Path, key: bytes) -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError("Recovery state must not contain symlinks")
            if path.is_file():
                tar.add(path, arcname=path.relative_to(directory).as_posix(), recursive=False)
    nonce = os.urandom(12)
    payload = FORMAT + nonce + AESGCM(key).encrypt(nonce, archive.getvalue(), FORMAT)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(payload)
    temporary.chmod(0o600)
    temporary.replace(destination)


def decrypt(source: Path, directory: Path, key: bytes) -> None:
    payload = source.read_bytes()
    if not payload.startswith(FORMAT):
        raise ValueError("Unrecognized recovery state format")
    nonce = payload[len(FORMAT):len(FORMAT) + 12]
    plaintext = AESGCM(key).decrypt(nonce, payload[len(FORMAT) + 12:], FORMAT)
    # Authenticate and validate the entire archive before touching saved state.
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary)
        with tarfile.open(fileobj=io.BytesIO(plaintext), mode="r:gz") as tar:
            for member in tar.getmembers():
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts or not member.isfile():
                    raise ValueError("Unsafe recovery state archive entry")
                target = staging / path
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as content:
                    target.write_bytes(content.read())
        # Do not follow a preexisting destination symlink either.
        for path in staging.rglob("*"):
            relative = path.relative_to(staging)
            if any(directory.joinpath(*relative.parts[:i]).is_symlink()
                   for i in range(len(relative.parts) + 1)):
                raise ValueError("Recovery destination must not contain symlinks")
        directory.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, directory, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["encrypt", "decrypt"])
    parser.add_argument("archive", type=Path)
    parser.add_argument("--directory", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()
    key = cache_key()
    if args.mode == "encrypt":
        encrypt(args.directory, args.archive, key)
    else:
        decrypt(args.archive, args.directory, key)


if __name__ == "__main__":
    main()
