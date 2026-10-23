# -*- coding: utf-8 -*-
"""One part of a phone-line transcription: decrypt -> faster-whisper (Hebrew) -> encrypt.

    python runner/transcribe.py <in.enc> <out.enc> <model> <beam>

The repo is public, so only timings and sizes are printed. Never the text.
The encrypted result is JSON: {"text": ..., "audio_sec": ..., "load_sec": ..., "asr_sec": ...}.
"""
import json
import os
import sys
import time

from cryptography.fernet import Fernet

src, dst, model_name, beam = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
f = Fernet(os.environ['TX_KEY'].encode())
wav = '/tmp/part.wav'
with open(src, 'rb') as fi, open(wav, 'wb') as fo:
    fo.write(f.decrypt(fi.read()))

t0 = time.time()
from faster_whisper import WhisperModel  # noqa: E402  (after decrypt, so a bad key fails fast)
m = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 4)
t1 = time.time()
segs, info = m.transcribe(wav, language='he', beam_size=beam, vad_filter=True, condition_on_previous_text=False)
text = ' '.join(s.text.strip() for s in segs).strip()
t2 = time.time()
res = {'text': text, 'audio_sec': round(info.duration, 1), 'load_sec': round(t1 - t0, 1), 'asr_sec': round(t2 - t1, 1)}
with open(dst, 'wb') as fo:
    fo.write(f.encrypt(json.dumps(res, ensure_ascii=False).encode('utf-8')))
print('audio %.0fs, model load %.1fs, asr %.1fs, chars %d' % (info.duration, t1 - t0, t2 - t1, len(text)))
