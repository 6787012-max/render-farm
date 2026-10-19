# -*- coding: utf-8 -*-
"""Join the slices the servers shot (out/p_<shard>_<k>.mp4, same encoder settings) into out/<name> without re-encoding,
and check the frame count.

    python3 $FARM/runner/concat_parts.py <name.mp4> [expected_frames]
"""
import glob
import json
import os
import subprocess
import sys

name = sys.argv[1]
expected = int(sys.argv[2]) if len(sys.argv) > 2 else None
parts = sorted(glob.glob('out/p_*.mp4'))
open('parts.txt', 'w').write(''.join("file '%s'\n" % os.path.abspath(p) for p in parts))
out = 'out/' + name
code = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', 'parts.txt', '-c', 'copy', out]).returncode
frames = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', out],
                        capture_output=True, text=True).stdout.strip()
for p in parts:
    os.remove(p)
rep = {'parts': len(parts), 'frames': int(frames or 0), 'frames_expected': expected, 'concat_exit': code}
json.dump(rep, open('out/report.json', 'w'))
print(json.dumps(rep))
sys.exit(0 if code == 0 and (expected is None or rep['frames'] == expected) else 1)
