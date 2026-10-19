# -*- coding: utf-8 -*-
"""Render MANY seekable scenes in one job. Scenes are shared between the servers (shards), balanced by duration;
each server renders its own scenes one after the other, with WORKERS browsers on every scene (seek_render.py).

    python3 $FARM/runner/seek_multi.py scenes.json [--fps 12]

scenes.json = [{"name": "s01", "path": "film/scenes/s01.html", "dur": 76.5}, ...]   (path relative to the work dir)
Result per scene (in out/): <name>.mp4 = VIDEO ONLY (parts joined without re-encoding), <name>.json = {dur, fps, frames_expected,
frames, sfx, errors}. The sound (music + effects) is mixed by the client, because the music is not ours to publish.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time

argv = sys.argv[1:]
manifest = json.load(open(argv[0], encoding='utf-8'))
fps = int(argv[argv.index('--fps') + 1]) if '--fps' in argv else 30
SH, NS = int(os.environ.get('SHARD', 0)), int(os.environ.get('SHARDS', 1))
FARM = os.environ['FARM']
root = os.getcwd()
os.makedirs('out', exist_ok=True)

# longest scene first, always onto the least loaded server (same answer on every server)
load, mine = [0.0] * NS, []
for i in sorted(range(len(manifest)), key=lambda i: (-manifest[i]['dur'], i)):
    s = min(range(NS), key=lambda k: (load[k], k))
    load[s] += manifest[i]['dur']
    if s == SH:
        mine.append(i)
mine.sort()
print('shard %d/%d: %d scenes, %.0fs of film' % (SH, NS, len(mine), load[SH]), flush=True)

failed = []
for i in mine:
    sc = manifest[i]
    name = sc['name']
    wd = os.path.join(root, 'scene_work', name)
    os.makedirs(wd, exist_ok=True)
    t0 = time.time()
    env = dict(os.environ, SHARD='0', SHARDS='1')
    r = subprocess.run([sys.executable, FARM + '/runner/seek_render.py', os.path.join(root, sc['path']), '--fps', str(fps)], cwd=wd, env=env)
    parts = sorted(glob.glob(wd + '/out/p_*.mp4'))
    errors = []
    for f in sorted(glob.glob(wd + '/out/err_*.json')):
        errors += json.load(open(f))
    errors = list(dict.fromkeys(errors))
    if r.returncode or not parts or not os.path.exists(wd + '/out/meta.json'):
        failed.append(name)
        print('  %s FAILED (exit %d)' % (name, r.returncode), flush=True)
        shutil.rmtree(wd, ignore_errors=True)
        continue
    meta = json.load(open(wd + '/out/meta.json'))
    open(wd + '/parts.txt', 'w').write(''.join("file '%s'\n" % p for p in parts))
    video = os.path.join(root, 'out', name + '.mp4')
    code = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', wd + '/parts.txt',
                           '-c', 'copy', '-movflags', '+faststart', video]).returncode
    frames = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets',
                             '-of', 'csv=p=0', video], capture_output=True, text=True).stdout.strip()
    json.dump({'dur': meta['dur'], 'fps': meta['fps'], 'frames_expected': meta['frames'], 'frames': int(frames or 0), 'sfx': meta['sfx'],
               'errors': errors[:20]}, open(os.path.join(root, 'out', name + '.json'), 'w'), ensure_ascii=False)
    print('  %s ok: %d/%d frames, %.0fs' % (name, int(frames or 0), meta['frames'], time.time() - t0), flush=True)
    if code:
        failed.append(name)
    shutil.rmtree(wd, ignore_errors=True)
if failed:
    sys.exit('failed scenes: ' + ', '.join(failed))
