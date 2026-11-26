#!/usr/bin/env python3
"""Audio-only lecture overview: Kokoro voice + MP3 + transcript + captions from the real timings.

Usage:  ~/.cache/ai410-kokoro-venv/bin/python audio.py m1-overview   (from this folder)
Writes: out/<name>.mp3, out/<name>.vtt, out/<name>-transcript.txt
An audio-only file needs a text transcript (WCAG 1.2.1); publish the transcript next to it.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = sys.argv[1]
cfg = json.loads((HERE / f'{NAME}.json').read_text(encoding='utf-8'))
OUT = HERE / 'out'; OUT.mkdir(exist_ok=True)
SR = 24000

def spoken(text):
    text = (text.replace('AI 420', 'AI four twenty').replace('AIC 3', '[AIC](/ˌAˌIsˈi/) three').replace('AIC 4', '[AIC](/ˌAˌIsˈi/) four')
                .replace('ADK', '[ADK](/ˌAdˌikˈA/)').replace('1962', 'nineteen sixty-two').replace('2007', 'two thousand seven'))
    return re.sub(r"(?<!\[)\bAI\b", '[AI](/ˈAˌI/)', text)

def stamp(t):
    return f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}'

import numpy as np, soundfile as sf
from kokoro import KPipeline
pipe = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')

audio, cues, t = [np.zeros(int(0.4 * SR))], [], 0.4
for s_no, sec in enumerate(cfg['sections']):
    if s_no:
        audio.append(np.zeros(int(cfg['section_gap'] * SR))); t += cfg['section_gap']
    for line in sec['lines']:
        wav = np.concatenate([np.asarray(c) for _, _, c in pipe(spoken(line), voice=cfg['voice'], speed=cfg['speed'])])
        d = len(wav) / SR
        cues.append((t, t + d, line))
        audio += [wav, np.zeros(int(cfg['gap'] * SR))]
        t += d + cfg['gap']
    print(f"{sec['heading']}: t={t:.1f}s")

tmp = Path(tempfile.mkdtemp())
sf.write(tmp / 'voice.wav', np.concatenate(audio).astype(np.float32), SR)
mp3 = OUT / f'{NAME}.mp3'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(tmp / 'voice.wav'),
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100', '-ac', '1', '-c:a', 'libmp3lame', '-b:a', '96k',
                '-metadata', f"title={cfg['title']}", '-metadata', 'artist=City University of Seattle · AI 420',
                '-metadata', 'comment=Narrated with a synthetic voice (Kokoro). Transcript available.', str(mp3)], check=True)

vtt = ['WEBVTT', '']
for i, (a, b, line) in enumerate(cues, 1):
    vtt += [str(i), f'{stamp(a)} --> {stamp(b)}', line, '']
(OUT / f'{NAME}.vtt').write_text('\n'.join(vtt), encoding='utf-8')
txt = [cfg['title'], 'Narrated with a synthetic voice.', '']
for sec in cfg['sections']:
    txt += [sec['heading'], ' '.join(sec['lines']), '']
(OUT / f'{NAME}-transcript.txt').write_text('\n'.join(txt), encoding='utf-8')
words = sum(len(l.split()) for s in cfg['sections'] for l in s['lines'])
print(f'{mp3.name}: {t:.1f}s, {mp3.stat().st_size / 1e6:.1f} MB, {words} words')
