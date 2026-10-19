# -*- coding: utf-8 -*-
"""Render a seekable HTML scene frame by frame - the contract of stefansky-clips/kit/render.py:
window.__ready, window.__seek(t), window.__dur, window.__sfx=[{t,name,vol}], window.__missing.

Shard SHARD of SHARDS of the frames, split again between WORKERS browsers running side by side.
Each browser writes out/p_<shard>_<worker>.mp4 (video only) and out/err_<shard>_<worker>.json;
shard 0 / worker 0 also writes out/meta.json (dur, sfx). seek_merge.py joins the parts and adds the sound.

    python3 $FARM/runner/seek_render.py <scene.html> [--fps 30]
"""
import json
import os
import subprocess
import sys
import time

argv = sys.argv[1:]
scene = os.path.abspath(argv[0])
fps = int(argv[argv.index('--fps') + 1]) if '--fps' in argv else 30
SH, NS, W = int(os.environ.get('SHARD', 0)), int(os.environ.get('SHARDS', 1)), int(os.environ.get('WORKERS', 3))
os.makedirs('out', exist_ok=True)

if '--k' not in argv:                                   # parent: start the browsers and wait for all of them
    t0 = time.time()
    procs = [subprocess.Popen([sys.executable, __file__] + argv + ['--k', str(k)]) for k in range(W)]
    codes = [p.wait() for p in procs]
    print('shard %d/%d: %d browsers, exit %s, %.0fs' % (SH, NS, W, codes, time.time() - t0), flush=True)
    sys.exit(1 if any(codes) else 0)

k = int(argv[argv.index('--k') + 1])
from playwright.sync_api import sync_playwright
BROWSER_ARGS = ['--hide-scrollbars', '--allow-file-access-from-files'] + (
    ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] if os.environ.get('KIT_GL') == '1' else ['--disable-gpu'])
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=BROWSER_ARGS)
    try:
        pg = browser.new_page(viewport={'width': 1920, 'height': 1080})
        pg.on('pageerror', lambda e: errors.append(str(e)[:400]))
        pg.on('console', lambda m: errors.append(m.text[:400]) if m.type == 'error' else None)
        pg.goto('file://' + scene, wait_until='load')
        pg.wait_for_function('window.__ready === true', timeout=90000)
        dur = float(pg.evaluate('window.__dur'))
        missing = pg.evaluate('window.__missing || []')
        if missing:
            errors.append('MISSING IMAGES: ' + ', '.join(m.rsplit('/', 1)[-1] for m in missing))
        n = int(round(dur * fps))
        sa, sb = n * SH // NS, n * (SH + 1) // NS                 # this shard
        a, b = sa + (sb - sa) * k // W, sa + (sb - sa) * (k + 1) // W   # this browser
        if SH == 0 and k == 0:
            json.dump({'dur': dur, 'frames': n, 'fps': fps, 'sfx': pg.evaluate('window.__sfx || []')}, open('out/meta.json', 'w'))
        part = 'out/p_%03d_%02d.mp4' % (SH, k)
        if a < b:
            ff = subprocess.Popen(['ffmpeg', '-hide_banner', '-nostats', '-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', str(fps),
                                   '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-profile:v', 'high', '-level', '4.1', '-pix_fmt', 'yuv420p',
                                   '-crf', '21', '-preset', 'medium', '-threads', '2', part], stdin=subprocess.PIPE)
            t0 = time.time()
            for i in range(a, b):
                pg.evaluate('window.__seek(%f)' % (i / fps))
                ff.stdin.write(pg.screenshot(type='jpeg', quality=92, timeout=240000))
            ff.stdin.close()
            if ff.wait():
                errors.append('ffmpeg failed on %s' % part)
            print('  shard %d browser %d: frames %d-%d  %.1f fps' % (SH, k, a, b, (b - a) / max(.1, time.time() - t0)), flush=True)
    finally:
        browser.close()
json.dump(errors, open('out/err_%03d_%02d.json' % (SH, k), 'w'))
sys.exit(0 if not any(e.startswith('ffmpeg failed') for e in errors) else 1)
