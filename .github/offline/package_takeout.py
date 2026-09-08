from __future__ import annotations

from pathlib import Path
import hashlib
import zipfile

ROOT = Path("The-12-Day-Dancer-Offline")
OUT = Path("takeout-parts")
OUT.mkdir(exist_ok=True)

# Final manifest is made only after every test has updated the report.
manifest = ROOT / "MANIFEST-SHA256.txt"
lines = []
for p in sorted(x for x in ROOT.rglob("*") if x.is_file() and x != manifest):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    lines.append(f"{h.hexdigest()}  {p.relative_to(ROOT).as_posix()}")
manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"SHA256 manifest: {len(lines)} files")

# Independent ZIPs under 450 MiB. Extract every part into the same destination.
max_bytes = 450 * 1024 * 1024
files = sorted(p for p in ROOT.rglob("*") if p.is_file())
groups: list[list[Path]] = []
current: list[Path] = []
current_size = 0
for p in files:
    size = p.stat().st_size
    if size > max_bytes:
        raise SystemExit(f"Single file exceeds part limit: {p} ({size} bytes)")
    if current and current_size + size > max_bytes:
        groups.append(current); current = []; current_size = 0
    current.append(p); current_size += size
if current:
    groups.append(current)

summary = []
for i, group in enumerate(groups, 1):
    zpath = OUT / f"The-12-Day-Dancer-Offline-Part-{i:03d}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in group:
            arc = Path(ROOT.name) / p.relative_to(ROOT)
            z.write(p, arc.as_posix())
    summary.append(f"{zpath.name}\t{zpath.stat().st_size}\t{len(group)} files")

(OUT / "PARTS.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
print("\n".join(summary))
print(f"Parts: {len(groups)}; files packaged: {sum(len(g) for g in groups)}")
