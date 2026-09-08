from __future__ import annotations

from pathlib import Path
import re

ROOT = Path("The-12-Day-Dancer-Offline")
ALBUMS = [
    "dies-iovis", "dies-solis", "dies-martis", "dies-albini",
    "dies-tigris", "dies-delfini", "dies-canis", "dies-felis",
    "dies-tauri", "dies-ursi", "dies-apri", "dies-akita",
]
EXPECTED = {
    "dies-iovis": 25, "dies-solis": 24, "dies-martis": 20,
    "dies-albini": 24, "dies-tigris": 24, "dies-delfini": 24,
    "dies-canis": 24, "dies-felis": 24, "dies-tauri": 8,
    "dies-ursi": 24, "dies-apri": 8, "dies-akita": 9,
}

root_html = ROOT / "index.html"
text = root_html.read_text(encoding="utf-8")
for album in ALBUMS:
    text = text.replace(f'href="{album}/"', f'href="{album}/index.html"')
root_html.write_text(text, encoding="utf-8", newline="\n")

hook = "<script>window.__OFFLINE_MEDIA_FILES=(typeof tracks!=='undefined'?tracks:(typeof films!=='undefined'?films:[])).map(x=>x.file);</script>"
for album in ALBUMS:
    page = ROOT / album / "index.html"
    text = page.read_text(encoding="utf-8")
    text, count = re.subn(
        r"const\s+RELEASE_BASE\s*=\s*(?:`[^`]*`|'[^']*'|\"[^\"]*\")\s*;",
        "const RELEASE_BASE='media';",
        text,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Could not rewrite RELEASE_BASE exactly once in {page}")
    text = text.replace('href="../"', 'href="../index.html"')
    if hook not in text:
        text = text.replace("</body>", hook + "\n</body>")
    page.write_text(text, encoding="utf-8", newline="\n")

server = r'''from __future__ import annotations
import os, re, shutil, threading, webbrowser
from email.utils import formatdate
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parent
HOST="127.0.0.1"; PORT=8765

class RangeHandler(SimpleHTTPRequestHandler):
    protocol_version="HTTP/1.1"
    def send_head(self):
        path=self.translate_path(self.path)
        if os.path.isdir(path):
            clean=self.path.split("?",1)[0].split("#",1)[0]
            if not clean.endswith("/"):
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                self.send_header("Location",clean+"/")
                self.send_header("Content-Length","0")
                self.end_headers(); return None
            for name in ("index.html","index.htm"):
                candidate=os.path.join(path,name)
                if os.path.isfile(candidate): path=candidate; break
            else: return self.list_directory(path)
        try: f=open(path,"rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND,"File not found"); return None
        fs=os.fstat(f.fileno()); size=fs.st_size; start=0; end=size-1; status=HTTPStatus.OK
        header=self.headers.get("Range")
        if header:
            m=re.fullmatch(r"bytes=(\d*)-(\d*)",header.strip())
            if not m:
                f.close(); self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE); return None
            a,b=m.groups()
            if not a and not b:
                f.close(); self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE); return None
            if not a: start=max(0,size-int(b))
            else: start=int(a)
            if b: end=min(size-1,int(b))
            if start>=size or start>end:
                f.close(); self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range",f"bytes */{size}")
                self.send_header("Content-Length","0"); self.end_headers(); return None
            status=HTTPStatus.PARTIAL_CONTENT
        self.send_response(status)
        self.send_header("Content-type",self.guess_type(path))
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(end-start+1))
        self.send_header("Last-Modified",formatdate(fs.st_mtime,usegmt=True))
        if status==HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
        self.end_headers(); self._range=(start,end); f.seek(start); return f
    def copyfile(self,source,outputfile):
        start,end=getattr(self,"_range",(0,None))
        if end is None: return shutil.copyfileobj(source,outputfile)
        remaining=end-start+1
        while remaining:
            chunk=source.read(min(1024*1024,remaining))
            if not chunk: break
            outputfile.write(chunk); remaining-=len(chunk)
    def log_message(self,fmt,*args): print("[offline]",fmt%args)

def open_browser(): webbrowser.open(f"http://{HOST}:{PORT}/index.html")
if __name__=="__main__":
    os.chdir(ROOT); httpd=ThreadingHTTPServer((HOST,PORT),RangeHandler)
    if not os.environ.get("THE12_NO_BROWSER"): threading.Timer(.8,open_browser).start()
    print(f"The 12 Day Dancer is running at http://{HOST}:{PORT}/index.html")
    print("Press Ctrl+C to stop.")
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: httpd.server_close()
'''
(ROOT / "server.py").write_text(server, encoding="utf-8", newline="\n")

launcher = r'''@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 server.py
  goto :eof
)
where python >nul 2>&1
if %errorlevel%==0 (
  python server.py
  goto :eof
)
echo.
echo Python 3 was not found.
echo Install Python 3, then run this file again.
echo.
pause
'''
(ROOT / "START-THE-12-DAY-DANCER.cmd").write_text(launcher, encoding="utf-8", newline="\r\n")

readme = '''THE 12 DAY DANCER - COMPLETE OFFLINE TAKEOUT

Windows start:
  Double-click START-THE-12-DAY-DANCER.cmd

The browser opens at http://127.0.0.1:8765/index.html.
The package is designed to work without GitHub, Suno, or an internet connection.

Offline rules:
- All 12 Bulgarian-panel buttons point explicitly to <album>/index.html.
- Every player uses local files in <album>/media/.
- Only browser-ready *.web.m4a audio is included. Original M4A masters are intentionally excluded.
- Dies Akita includes all nine MP4 films used by the Brumbrum video player.
- server.py supports HTTP byte ranges, so audio/video seeking works locally.

If the takeout is supplied as several Part-XXX.zip files:
  Extract EVERY part into the same destination folder and allow folders to merge.
  The parts are independent ZIPs and contain disjoint files.

Verification:
  SOURCE-COMMIT.txt
  MANIFEST-SHA256.txt
  OFFLINE-TEST-REPORT.txt
'''
(ROOT / "TAKEOUT-README.txt").write_text(readme, encoding="utf-8", newline="\n")

report = []
root_text = root_html.read_text(encoding="utf-8")
for album in ALBUMS:
    expected = f'href="{album}/index.html"'
    if expected not in root_text:
        raise SystemExit(f"Missing explicit offline panel link: {expected}")
report.append("Bulgarian panel: 12/12 explicit index.html links OK")

total = 0
for album in ALBUMS:
    html = (ROOT / album / "index.html").read_text(encoding="utf-8")
    if "github.com/bryanzzai/bryanmackayne/releases/download" in html:
        raise SystemExit(f"Online Release URL remains in {album}/index.html")
    if "const RELEASE_BASE='media';" not in html or "window.__OFFLINE_MEDIA_FILES" not in html:
        raise SystemExit(f"Offline rewrite incomplete in {album}/index.html")
    media = sorted(p.name for p in (ROOT / album / "media").iterdir() if p.is_file())
    if len(media) != EXPECTED[album]:
        raise SystemExit(f"{album}: {len(media)} local media; expected {EXPECTED[album]}")
    total += len(media)
    report.append(f"{album}: {len(media)} local browser media files staged")

originals = [p for p in ROOT.rglob("*.m4a") if not p.name.endswith(".web.m4a")]
if originals:
    raise SystemExit("Original/non-web M4A found: " + ", ".join(map(str, originals[:20])))
web_audio = list(ROOT.rglob("*.web.m4a")); videos = list(ROOT.rglob("*.mp4"))
if len(web_audio) != 229 or len(videos) != 9 or total != 238:
    raise SystemExit(f"Media totals wrong: web={len(web_audio)}, mp4={len(videos)}, total={total}")
if any("dies-akita/media" not in p.as_posix() for p in videos):
    raise SystemExit("MP4 found outside dies-akita/media")
report += [
    "Original M4A masters: 0 included (intentional)",
    "Browser-ready audio: 229 *.web.m4a",
    "Brumbrum video: 9 *.mp4",
    "Total local browser media: 238",
]
external = []
for hp in ROOT.rglob("*.html"):
    if re.search(r"https?://", hp.read_text(encoding="utf-8"), re.I):
        external.append(str(hp.relative_to(ROOT)))
if external:
    raise SystemExit("External HTTP(S) references remain: " + ", ".join(external))
report.append("Offline HTML external HTTP(S) dependencies: 0")
(ROOT / "OFFLINE-TEST-REPORT.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
print("\n".join(report))
