# -*- coding: utf-8 -*-
"""Send the result back: every file under <out dir> XOR 0xA7 (files over 90MB split into .bin.000, .bin.001 ...),
committed alone (orphan) and pushed to branch out/<job>.

    python runner/push_result.py /tmp/w/out <job>
"""
import os
import subprocess
import sys
from pathlib import Path

T = bytes(i ^ 0xA7 for i in range(256))
CHUNK = 90 * 1024 * 1024
src, job = Path(sys.argv[1]), sys.argv[2]
res = Path('/tmp/result')
res.mkdir()
n = 0
for f in sorted(src.rglob('*')):
    if f.is_file():
        rel = f.relative_to(src).as_posix()
        data = f.read_bytes().translate(T)
        dst = res / (rel + '.bin')
        dst.parent.mkdir(parents=True, exist_ok=True)
        if len(data) <= CHUNK:
            dst.write_bytes(data)
        else:
            for i in range(0, len(data), CHUNK):
                Path('%s.%03d' % (dst, i // CHUNK)).write_bytes(data[i:i + CHUNK])
        n += 1
        print('%8.1f MB  %s' % (len(data) / 1e6, rel), flush=True)
if not n:
    sys.exit('no result files')
url = 'https://x-access-token:%s@github.com/%s.git' % (os.environ['GH_TOKEN'], os.environ['GITHUB_REPOSITORY'])
g = lambda *a: subprocess.run(['git', '-c', 'user.name=render-bot', '-c', 'user.email=render-bot@users.noreply.github.com'] + list(a), cwd=res, check=True)
g('init', '-q')
g('add', '-A')
g('commit', '-q', '-m', 'result ' + job)
g('push', '-q', url, 'HEAD:refs/heads/out/' + job)
print('pushed %d files to out/%s' % (n, job))
