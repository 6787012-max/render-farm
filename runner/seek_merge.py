# -*- coding: utf-8 -*-
"""Join the parts seek_render.py made (out/p_*.mp4) and add the scene's sound effects - the same mix as
stefansky-clips/kit/render.py (sfx at 0.55 x vol, optional quiet music, limiter, AAC 160k).
Leaves only out/<name> and out/report.json.

    python3 $FARM/runner/seek_merge.py <name.mp4> --sfx-dir kit/sfx [--music f.mp3 --music-vol 0.16 --music-start 0]
"""
import glob
import json
import os
import subprocess
import sys

argv = sys.argv[1:]
name = argv[0]
opt = lambda k, d=None: argv[argv.index(k) + 1] if k in argv else d
sfx_dir, music = opt('--sfx-dir', 'kit/sfx'), opt('--music')
music_vol, music_start = float(opt('--music-vol', 0.16)), float(opt('--music-start', 0))
O = 'out/'
parts = sorted(glob.glob(O + 'p_*.mp4'))
meta = json.load(open(O + 'meta.json'))
errors = []
for f in sorted(glob.glob(O + 'err_*.json')):
    errors += json.load(open(f))
errors = list(dict.fromkeys(errors))
open('parts.txt', 'w').write(''.join("file '%s'\n" % os.path.abspath(p) for p in parts))
tmp = 'video.mp4'
code = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-c', 'copy',
                       '-movflags', '+faststart', tmp]).returncode
if code:
    sys.exit('concat failed')
length = meta['dur']
inputs, filters, mix = ['-i', tmp], [], []
idx = 1
if music:
    inputs += ['-stream_loop', '-1', '-ss', str(music_start), '-i', music]
    filters.append('[%d:a]atrim=0:%.3f,volume=%.3f,afade=t=in:d=0.8,afade=t=out:st=%.3f:d=1.2[m]' % (idx, length, music_vol, max(0, length - 1.2)))
    mix.append('[m]'); idx += 1
for k, s in enumerate(meta['sfx']):
    f = os.path.join(sfx_dir, s['name'] + '.wav')
    t = s['t']
    if not os.path.exists(f) or t < 0 or t > length:
        continue
    inputs += ['-i', f]
    filters.append('[%d:a]volume=%.3f,adelay=%d:all=1[s%d]' % (idx, 0.55 * s.get('vol', 1), int(t * 1000), k))
    mix.append('[s%d]' % k); idx += 1
out = O + name
if mix:
    filters.append('%samix=inputs=%d:normalize=0:duration=longest,atrim=0:%.3f,alimiter=limit=0.9[a]' % (''.join(mix), len(mix), length))
    open('filter.txt', 'w').write(';\n'.join(filters))
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y'] + inputs + ['-filter_complex_script', 'filter.txt', '-map', '0:v', '-map', '[a]',
                                                                         '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-ar', '44100', '-ac', '2', '-movflags', '+faststart', out]
else:
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', tmp, '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-shortest',
           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '64k', '-movflags', '+faststart', out]
code = subprocess.run(cmd).returncode
vdur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout or 0)
frames = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', tmp],
                        capture_output=True, text=True).stdout.strip()
for f in parts + glob.glob(O + 'err_*.json') + [O + 'meta.json']:
    os.remove(f)
rep = {'dur': length, 'video_dur': round(vdur, 2), 'frames_expected': meta['frames'], 'frames': int(frames or 0), 'parts': len(parts),
       'sfx': len(mix) - (1 if music else 0), 'sfx_list': meta['sfx'], 'audio_mix_exit': code, 'size_kb': os.path.getsize(out) // 1024 if os.path.exists(out) else 0, 'errors': errors[:20]}
json.dump(rep, open(O + 'report.json', 'w'), ensure_ascii=False)
print(json.dumps(rep, ensure_ascii=False))
sys.exit(0 if code == 0 else 1)          # a frame-count mismatch is in the report; the client flags it
