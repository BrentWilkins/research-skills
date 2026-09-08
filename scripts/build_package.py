#!/usr/bin/env python3
"""Build a verified source archive from the explicit PACKAGE_FILES.txt inventory."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def inventory(root):
    names = (root / "PACKAGE_FILES.txt").read_text(encoding="utf-8").splitlines()
    if not names or len(names) != len(set(names)):
        raise ValueError("Empty or duplicate publication inventory")
    result = {}
    for name in names:
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or "\\" in name or ":" in name
                or any(part in {"", ".", ".."} for part in name.split("/"))):
            raise ValueError(f"Invalid publication path: {name!r}")
        path = root
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise ValueError(f"Symlink excluded from publication: {name}")
        if not path.is_file():
            raise ValueError(f"Missing publication file: {name}")
        result[name] = path.read_bytes()
    return result


def build(output, root=ROOT):
    files = inventory(root)
    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    files["SHA256SUMS"] = sums.encode("utf-8")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, data in sorted(files.items()):
                    info = tarfile.TarInfo("research-skills/" + name)
                    info.size = len(data)
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(data))
    with tarfile.open(output, "r:gz") as archive:
        if len(archive.getmembers()) != len(files):
            raise ValueError("Publication archive inventory mismatch")
        for name, data in files.items():
            member = archive.extractfile("research-skills/" + name)
            if member is None or member.read() != data:
                raise ValueError(f"Publication verification failed: {name}")
    return len(files), output.stat().st_size, hashlib.sha256(output.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        count, size, checksum = build(args.output)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"ERROR: {exc}\n")
    print(f"Verified {count} files, {size} bytes: {args.output}\nSHA-256: {checksum}")


if __name__ == "__main__":
    main()
