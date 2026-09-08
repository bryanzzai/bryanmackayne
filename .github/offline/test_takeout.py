from __future__ import annotations

from pathlib import Path
from urllib.parse import quote
import os
import subprocess
import sys
import time
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

ROOT = Path("The-12-Day-Dancer-Offline")
ALBUMS = [
    "dies-iovis", "dies-solis", "dies-martis", "dies-albini",
    "dies-tigris", "dies-delfini", "dies-canis", "dies-felis",
    "dies-tauri", "dies-ursi", "dies-apri", "dies-akita",
]
BASE = "http://127.0.0.1:8765/"
REPORT = ROOT / "OFFLINE-TEST-REPORT.txt"

media = sorted([*ROOT.rglob("*.web.m4a"), *ROOT.rglob("*.mp4")])
if len(media) != 238:
    raise SystemExit(f"Expected 238 media files before testing, found {len(media)}")

# Container-level validation: every browser file must be readable media with a positive duration.
for i, path in enumerate(media, 1):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    duration = float(result.stdout.strip())
    if duration <= 0:
        raise SystemExit(f"Invalid duration for {path}: {duration}")
    if i % 50 == 0 or i == len(media):
        print(f"ffprobe {i}/{len(media)}")
with REPORT.open("a", encoding="utf-8") as f:
    f.write(f"ffprobe: {len(media)}/{len(media)} media files valid with positive duration\n")

# Run the exact local server shipped in the archive.
env = os.environ.copy(); env["THE12_NO_BROWSER"] = "1"
server = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
try:
    for _ in range(60):
        try:
            with urllib.request.urlopen(BASE + "index.html", timeout=2) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.5)
    else:
        out = server.stdout.read() if server.stdout else ""
        raise RuntimeError("Local server did not start.\n" + out)

    # Every media file must support byte ranges; this is what makes local seeking reliable.
    for i, path in enumerate(media, 1):
        rel = path.relative_to(ROOT).as_posix()
        req = urllib.request.Request(BASE + quote(rel), headers={"Range": "bytes=0-31"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            if r.status != 206 or len(data) != 32:
                raise RuntimeError(f"Range test failed for {rel}: status={r.status}, bytes={len(data)}")
        if i % 50 == 0 or i == len(media):
            print(f"HTTP range {i}/{len(media)}")
    with REPORT.open("a", encoding="utf-8") as f:
        f.write(f"HTTP byte-range: {len(media)}/{len(media)} media files returned 206\n")

    # Chrome is deliberately prevented from resolving anything except localhost.
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--mute-audio")
    opts.add_argument("--autoplay-policy=no-user-gesture-required")
    opts.add_argument("--host-resolver-rules=MAP * 0.0.0.0, EXCLUDE localhost, EXCLUDE 127.0.0.1")
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(60)
    driver.set_script_timeout(30)

    metadata_script = r"""
      const selector=arguments[0], filename=arguments[1], done=arguments[2];
      const el=document.querySelector(selector);
      if(!el){done({ok:false,error:'media element missing'});return;}
      let finished=false;
      const finish=x=>{if(finished)return;finished=true;clearTimeout(timer);done(x)};
      const timer=setTimeout(()=>finish({ok:false,error:'metadata timeout',ready:el.readyState}),12000);
      el.pause(); el.src='media/'+encodeURIComponent(filename); el.muted=true;
      el.onloadedmetadata=()=>finish({ok:Number.isFinite(el.duration)&&el.duration>0,duration:el.duration,ready:el.readyState});
      el.onerror=()=>finish({ok:false,error:el.error&&el.error.code,ready:el.readyState});
      el.load();
    """
    playback_script = r"""
      const selector=arguments[0], filename=arguments[1], done=arguments[2];
      const el=document.querySelector(selector);
      if(!el){done({ok:false,error:'media element missing'});return;}
      let ticks=0, finished=false, sought=false;
      const finish=x=>{if(finished)return;finished=true;clearInterval(timer);done(x)};
      el.pause(); el.src='media/'+encodeURIComponent(filename); el.muted=true; el.load();
      const timer=setInterval(()=>{
        ticks++;
        if(el.error){finish({ok:false,error:el.error.code,current:el.currentTime,ready:el.readyState});return;}
        if(el.readyState>=2 && el.paused && !sought) el.play().catch(()=>{});
        if(!sought && el.currentTime>0.20 && el.readyState>=2){
          sought=true;
          const d=Number.isFinite(el.duration)?el.duration:2;
          const target=Math.min(Math.max(0.8,d*0.55),Math.max(0.8,d-0.5));
          try{el.currentTime=target}catch(e){finish({ok:false,error:String(e),current:el.currentTime,ready:el.readyState});return;}
          setTimeout(()=>finish({ok:!el.error&&el.currentTime>0.3,error:el.error&&el.error.code,current:el.currentTime,ready:el.readyState,duration:el.duration}),900);
        }
        if(ticks>100) finish({ok:false,error:'playback timeout',current:el.currentTime,ready:el.readyState,duration:el.duration});
      },250);
    """

    try:
        driver.get(BASE + "index.html")
        links = driver.execute_script("return [...document.querySelectorAll('a.album.live')].map(a=>a.getAttribute('href'))")
        expected_links = [f"{album}/index.html" for album in ALBUMS]
        if links != expected_links:
            raise RuntimeError(f"Bulgarian panel paths/order mismatch: {links}")

        tested = []
        metadata_total = 0
        for album in ALBUMS:
            driver.get(BASE + album + "/index.html")
            refs = driver.execute_script("return window.__OFFLINE_MEDIA_FILES || []")
            local = sorted(p.name for p in (ROOT / album / "media").iterdir() if p.is_file())
            if len(refs) != len(set(refs)):
                raise RuntimeError(f"{album}: duplicate player media references")
            if sorted(refs) != local:
                missing = sorted(set(refs) - set(local)); extra = sorted(set(local) - set(refs))
                raise RuntimeError(f"{album}: player/media mismatch; missing={missing}; extra={extra}")
            if not refs:
                raise RuntimeError(f"{album}: runtime media manifest is empty")

            selector = "#player" if album == "dies-akita" else "#audio"
            for name in refs:
                result = driver.execute_async_script(metadata_script, selector, name)
                if not result.get("ok"):
                    raise RuntimeError(f"{album}: browser metadata failed for {name}: {result}")
                metadata_total += 1
            for idx in ({0, len(refs)-1} if len(refs) > 1 else {0}):
                result = driver.execute_async_script(playback_script, selector, refs[idx])
                if not result.get("ok"):
                    raise RuntimeError(f"{album}: playback/seek failed for {refs[idx]}: {result}")
            line = f"{album}: runtime mapping {len(refs)}/{len(local)} exact; all metadata OK; first+last playback/seek OK"
            tested.append(line); print(line)

        if metadata_total != 238:
            raise RuntimeError(f"Browser metadata total {metadata_total}; expected 238")
        with REPORT.open("a", encoding="utf-8") as f:
            f.write("Browser panel: 12/12 explicit buttons in canonical order and reachable\n")
            f.write(f"Browser metadata: {metadata_total}/{metadata_total} media files load locally\n")
            f.write("\n".join(tested) + "\n")
            f.write("Chrome external DNS: blocked during browser test; localhost only\n")
    finally:
        driver.quit()
finally:
    server.terminate()
    try: server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill(); server.wait()

print("OFFLINE TEST SUITE PASSED")
