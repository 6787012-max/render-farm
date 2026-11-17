# -*- coding: utf-8 -*-
"""YouTube search and download on a farm server (the workflow yt-fetch.yml puts WARP in front of it).
Results are written to <work>/out, and the farm sends that folder back, like a render result.

    python3 $FARM/runner/yt_job.py search "<query>" [--per 15] [--client tv,web_safari]
    python3 $FARM/runner/yt_job.py get <video id> [--cuts "0:10-0:30,1:00-1:20"] [--client ...]

search: out/search.txt, one line per hit: id | m:ss | title
get with --cuts: out/<id>_cut<N>.mp4, 1280x720, H.264, no sound
get without --cuts: out/<id>.mp4, 720p with sound, at most 300 MB
--client: yt-dlp YouTube player clients (for example tv,web_safari,mweb), only when the default is blocked
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

MAX_FULL_BYTES = 300 * 1000 * 1000


def yt(args, timeout):
    return subprocess.run(['yt-dlp', '--no-warnings', '--no-playlist'] + args,
                          capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)


def ext_args(client):
    return ['--extractor-args', 'youtube:player_client=%s' % client] if client else []


def mmss(sec):
    try:
        s = int(float(sec))
        return '%d:%02d' % (s // 60, s % 60)
    except ValueError:
        return 'NA'


def parse_t(text):
    # "90", "1:30" or "1:02:03" -> seconds
    total = 0.0
    for part in text.strip().split(':'):
        total = total * 60 + float(part)
    return total


def do_search(query, per, client):
    r = yt(['--flat-playlist', '--print', '%(id)s\t%(duration)s\t%(title)s',
            'ytsearch%d:%s' % (per, query)] + ext_args(client), 600)
    rows = []
    for line in r.stdout.splitlines():
        parts = line.split('\t')
        if len(parts) < 3 or not re.fullmatch(r'[A-Za-z0-9_-]{11}', parts[0]):
            continue
        rows.append('%s | %s | %s' % (parts[0], mmss(parts[1]), '\t'.join(parts[2:]).strip()))
    os.makedirs('out', exist_ok=True)
    with open('out/search.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(rows) + '\n')
    print('search %r: %d results' % (query, len(rows)), flush=True)
    if not rows:
        sys.exit('search: no results. yt-dlp said: ' + r.stderr[-800:])


def ensure_ffmpeg():
    # render-warp.yml does not run runner/setup.sh, and the ubuntu image had no ffmpeg on 17/11
    if shutil.which('ffmpeg'):
        return
    subprocess.run('sudo apt-get update -q && sudo apt-get install -y -q --no-install-recommends ffmpeg',
                   shell=True, check=True)


def do_get(vid, cuts, client):
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
        sys.exit('bad video id: %r' % vid)
    ensure_ffmpeg()
    os.makedirs('out', exist_ok=True)
    os.makedirs('work', exist_ok=True)
    fmt = 'bv*[height<=720]/b[height<=720]' if cuts else 'bv*[height<=720]+ba/b[height<=720]/b'
    r = yt(['-f', fmt, '--merge-output-format', 'mp4', '-o', 'work/%(id)s.%(ext)s',
            'https://www.youtube.com/watch?v=' + vid] + ext_args(client), 1500)
    if r.returncode:
        sys.exit('download failed (exit %d): %s' % (r.returncode, r.stderr[-1500:]))
    cands = [p for p in glob.glob('work/%s.*' % vid) if not p.endswith(('.part', '.ytdl'))]
    if not cands:
        sys.exit('download: no file found')
    src = cands[0]
    size = os.path.getsize(src)
    print('downloaded %s %.1f MB' % (src, size / 1e6), flush=True)
    if not cuts:
        if size > MAX_FULL_BYTES:
            sys.exit('whole video is %.1f MB, over the 300 MB limit; use --cuts' % (size / 1e6))
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', src, '-c', 'copy',
                        '-movflags', '+faststart', 'out/%s.mp4' % vid], check=True)
        print('out/%s.mp4 ready' % vid, flush=True)
        return
    for i, span in enumerate(cuts.split(','), 1):
        if '-' not in span:
            sys.exit('bad cut %r, use start-end' % span)
        a, b = span.split('-', 1)
        ss, to = parse_t(a), parse_t(b)
        if to <= ss:
            sys.exit('bad cut %r: end is not after start' % span)
        dst = 'out/%s_cut%d.mp4' % (vid, i)
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', src,
                        '-ss', str(ss), '-to', str(to), '-an',
                        '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1',
                        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p',
                        '-movflags', '+faststart', dst], check=True)
        print('%s ready  %.1f s' % (dst, to - ss), flush=True)
    shutil.rmtree('work', ignore_errors=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='mode', required=True)
    s = sub.add_parser('search')
    s.add_argument('query')
    s.add_argument('--per', type=int, default=15)
    s.add_argument('--client', default='')
    g = sub.add_parser('get')
    g.add_argument('id')
    g.add_argument('--cuts', default='')
    g.add_argument('--client', default='')
    a = ap.parse_args()
    if a.mode == 'search':
        do_search(a.query, a.per, a.client)
    else:
        do_get(a.id, a.cuts, a.client)
