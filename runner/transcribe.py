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
import zlib  # noqa: E402
raw = '/tmp/part.wav'   # a WAV at the phone's own rate (8kHz), zlib-compressed before encryption
data = f.decrypt(open(src, 'rb').read())
try:
    data = zlib.decompress(data)
except zlib.error:
    pass
with open(raw, 'wb') as fo:
    fo.write(data)

t0 = time.time()
from faster_whisper import WhisperModel  # noqa: E402  (after decrypt, so a bad key fails fast)
m = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 4)
t1 = time.time()
# The client always sends 16kHz mono PCM, so read it directly. faster-whisper's own decoder (PyAV)
# broke on 23/10/2026: the newest av dropped the metadata_errors argument that faster-whisper passes.
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402
audio, rate = sf.read(raw, dtype='float32', always_2d=True)
audio = audio.mean(axis=1)
if rate != 16000:
    import soxr  # noqa: E402
    audio = soxr.resample(audio, rate, 16000).astype(np.float32)
segs, info = m.transcribe(audio, language='he', beam_size=beam, vad_filter=True, condition_on_previous_text=False)
text = ' '.join(s.text.strip() for s in segs).strip()
t2 = time.time()
res = {'text': text, 'audio_sec': round(info.duration, 1), 'load_sec': round(t1 - t0, 1), 'asr_sec': round(t2 - t1, 1)}
with open(dst, 'wb') as fo:
    fo.write(f.encrypt(json.dumps(res, ensure_ascii=False).encode('utf-8')))
print('audio %.0fs, model load %.1fs, asr %.1fs, chars %d' % (info.duration, t1 - t0, t2 - t1, len(text)))
