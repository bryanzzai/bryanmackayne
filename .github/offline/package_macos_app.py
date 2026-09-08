from __future__ import annotations

from pathlib import Path
import hashlib
import plistlib
import shutil
import zipfile

OFFLINE = Path("The-12-Day-Dancer-Offline")
APP = Path("The 12 Day Dancer.app")
CONTENTS = APP / "Contents"
MACOS = CONTENTS / "MacOS"
RESOURCES = CONTENTS / "Resources"
SITE = RESOURCES / "site"
OUT = Path("macos-app-parts")

if APP.exists():
    shutil.rmtree(APP)
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
MACOS.mkdir(parents=True)
RESOURCES.mkdir(parents=True, exist_ok=True)

if not OFFLINE.is_dir():
    raise SystemExit("Offline working tree is missing")

# Add a final manifest before the offline tree becomes an app resource.
manifest = OFFLINE / "MANIFEST-SHA256.txt"
lines = []
for p in sorted(x for x in OFFLINE.rglob("*") if x.is_file() and x != manifest):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    lines.append(f"{h.hexdigest()}  {p.relative_to(OFFLINE).as_posix()}")
manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")

shutil.move(str(OFFLINE), str(SITE))

info = {
    "CFBundleName": "The 12 Day Dancer",
    "CFBundleDisplayName": "The 12 Day Dancer",
    "CFBundleIdentifier": "dk.bryanmackayne.the12daydancer.offline",
    "CFBundleVersion": "1",
    "CFBundleShortVersionString": "1.0",
    "CFBundlePackageType": "APPL",
    "CFBundleExecutable": "The12DayDancer",
    "CFBundleIconFile": "The12DayDancer.icns",
    "LSMinimumSystemVersion": "13.0",
    "NSHighResolutionCapable": True,
}
with (CONTENTS / "Info.plist").open("wb") as f:
    plistlib.dump(info, f, sort_keys=False)
(CONTENTS / "PkgInfo").write_text("APPL????", encoding="ascii")

# The compiled launcher and .icns are added by the workflow after this script.
print(f"Prepared app resource tree: {SITE}")
print(f"Manifest entries: {len(lines)}")

# A second invocation after compilation/signing performs packaging.
marker = Path(".macos-app-ready")
if not marker.exists():
    raise SystemExit(0)

launcher = MACOS / "The12DayDancer"
icon = RESOURCES / "The12DayDancer.icns"
if not launcher.is_file() or not icon.is_file():
    raise SystemExit("Compiled launcher or app icon missing")

# Independent ZIPs small enough to be downloaded separately through the connector.
max_bytes = 350 * 1024 * 1024
files = sorted(p for p in APP.rglob("*") if p.is_file())
groups: list[list[Path]] = []
current: list[Path] = []
current_size = 0
for p in files:
    size = p.stat().st_size
    if size > max_bytes:
        raise SystemExit(f"Single file exceeds part limit: {p} ({size} bytes)")
    if current and current_size + size > max_bytes:
        groups.append(current)
        current = []
        current_size = 0
    current.append(p)
    current_size += size
if current:
    groups.append(current)

summary = []
for i, group in enumerate(groups, 1):
    zpath = OUT / f"The-12-Day-Dancer-macOS-App-Part-{i:03d}.zip"
    with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for p in group:
            z.write(p, p.as_posix())
    summary.append(f"{zpath.name}\t{zpath.stat().st_size}\t{len(group)} files")

(OUT / "PARTS.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
print("\n".join(summary))
print(f"Parts: {len(groups)}; app files packaged: {sum(len(g) for g in groups)}")
if len(groups) > 10:
    raise SystemExit("More than ten parts produced; workflow upload steps must be extended")
