#!/usr/bin/env python3
"""Short narrated lecture video: HTML slides + Kokoro voice + captions from the real timings.

Each slide in <name>.json has lines; line k is spoken while the slide shows step k
(elements with data-step <= k in <name>.html). The voice is synthetic (Kokoro, Apache 2.0, runs
locally) and the title slide says so.

Usage:  ~/.cache/ai410-kokoro-venv/bin/python build.py m1-part1   (from this folder)
Writes: out/<name>.mp4 (with a soft caption track), out/<name>.vtt, out/<name>-poster.jpg
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = sys.argv[1]
cfg = json.loads((HERE / f'{NAME}.json').read_text(encoding='utf-8'))
OUT = HERE / 'out'; OUT.mkdir(exist_ok=True)
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PRE = 0.35   # silence before the first line of each slide

def spoken(text):
    # Pronunciation fixes; captions keep the real text. [word](/.../) pins phonemes.
    text = (text.replace('AI 420', 'AI four twenty').replace('1962', 'nineteen sixty-two').replace('2007', 'two thousand seven')
                .replace('AIC 3', '[AIC](/ˌAˌIsˈi/) three').replace('AIC 4', '[AIC](/ˌAˌIsˈi/) four')
                .replace('adk web', 'ADK web').replace('ADK', '[ADK](/ˌAdˌikˈA/)')
                .replace('Codespaces', 'Code spaces').replace('403', 'four oh three'))
    return re.sub(r"(?<!\[)\bAI\b", '[AI](/ˈAˌI/)', text)

def duration(path):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                          '-of', 'default=nw=1:nk=1', str(path)], text=True))

def stamp(t):
    return f'{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{t % 60:06.3f}'

import numpy as np, soundfile as sf
from kokoro import KPipeline
pipe = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')

tmp = Path(tempfile.mkdtemp())
html = (HERE / f'{NAME}.html').as_uri()
SR = 24000
audio, cues, segs, t = [], [], [], 0.0
for slide in cfg['slides']:
    sid, lines = slide['id'], slide['lines']
    for k, line in enumerate(lines, 1):
        png = tmp / f'{sid}-{k}.png'
        subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--window-size=1920,1080',
                        '--force-device-scale-factor=1', '--virtual-time-budget=4000', f'--screenshot={png}',
                        f'{html}#{sid}-{k}'], check=True, capture_output=True)
        wav = np.concatenate([np.asarray(c) for _, _, c in pipe(spoken(line), voice=cfg['voice'], speed=cfg['speed'])])
        pre = PRE if k == 1 else 0.0
        post = cfg['gap'] + (cfg['slide_tail'] if k == len(lines) else 0.0)
        d_line = len(wav) / SR
        audio += [np.zeros(int(pre * SR)), wav, np.zeros(int(post * SR))]
        cues.append((t + pre, t + pre + d_line, line))
        seg_len = pre + d_line + post
        segs.append((png, seg_len))
        t += seg_len
    print(f'{sid}: done, t={t:.1f}s')

sf.write(tmp / 'voice.wav', np.concatenate(audio).astype(np.float32), SR)
lst = tmp / 'list.txt'
lst.write_text(''.join(f"file '{p}'\nduration {d:.3f}\n" for p, d in segs) + f"file '{segs[-1][0]}'\nduration 1.0\n")
vtt = ['WEBVTT', '']
for i, (a, b, line) in enumerate(cues, 1):
    vtt += [str(i), f'{stamp(a)} --> {stamp(b)}', line, '']
(OUT / f'{NAME}.vtt').write_text('\n'.join(vtt), encoding='utf-8')

mp4 = OUT / f'{NAME}.mp4'
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(lst),
                '-i', str(tmp / 'voice.wav'), '-i', str(OUT / f'{NAME}.vtt'),
                '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'slow', '-crf', '20', '-tune', 'stillimage',
                '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000', '-c:a', 'aac', '-b:a', '160k',
                '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng',
                '-map', '0:v', '-map', '1:a', '-map', '2:s', '-t', f'{t:.3f}', '-movflags', '+faststart', str(mp4)], check=True)
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(segs[0][0]), '-vf', 'scale=1280:720', '-q:v', '3',
                str(OUT / f'{NAME}-poster.jpg')], check=True)
words = sum(len(l.split()) for s in cfg['slides'] for l in s['lines'])
print(f'{mp4.name}: {duration(mp4):.1f}s, {mp4.stat().st_size / 1e6:.1f} MB, {len(cues)} lines, {words} words')
