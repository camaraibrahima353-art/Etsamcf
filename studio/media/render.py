"""Montage FFmpeg : plans animés, voix, nappe musicale procédurale, sous-titres incrustés, export vertical."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from .visuals import H, W, font_path, music_freqs

SCENE_PAD_S = 0.30          # respiration entre deux phrases
MUSIC_LICENSE = "Nappe musicale synthétisée par FFmpeg (aevalsrc), propriété du studio"


def _run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg a échoué ({p.returncode}) : {p.stderr[-1500:]}")
    return p


def _ass_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _chunks(text, max_chars):
    words, out, cur = text.split(), [], []
    for w in words:
        cand = " ".join(cur + [w])
        if cur and (len(cand) > max_chars or len(cur) >= 5):
            out.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
        if re.search(r"[.!?:;]$", w) and cur:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def build_ass(scenes, out: Path, max_chars=26, accent="#FFE29A"):
    """Sous-titres mot à mot (3-4 mots), centrés au-dessus de la zone d'interface des plateformes."""
    ac = accent.lstrip("#")
    ass_accent = f"&H00{ac[4:6]}{ac[2:4]}{ac[0:2]}"
    fam = "Inter" if "Inter" in font_path() else "DejaVu Sans"
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{fam},84,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,7,3,5,40,40,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    cues = []
    t0 = 0.0
    for sc in scenes:
        speech = sc["speech_s"]
        parts = _chunks(sc["voice"], max_chars)
        total_chars = sum(len(p) for p in parts) or 1
        t = t0 + 0.05
        for p in parts:
            dur = speech * len(p) / total_chars
            txt = re.sub(r"(\d[\d\s,.%]*)", lambda m: "{\\c" + ass_accent + "&}" + m.group(1) + "{\\c&H00FFFFFF&}", p)
            txt = txt.replace("\n", " ")
            cues.append((t, t + dur, p))
            lines.append(
                f"Dialogue: 0,{_ass_time(t)},{_ass_time(t + dur)},Cap,,0,0,0,,"
                "{\\pos(500,1330)\\fscx86\\fscy86\\t(0,90,\\fscx100\\fscy100)}" + txt
            )
            t += dur
        t0 += sc["duration_s"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return cues


def render_video(project: dict, workdir: Path, out_mp4: Path, fps=30, max_caption_chars=26, accent="#FFE29A", target_lufs=-14.0):
    scenes = project["scenes"]
    workdir.mkdir(parents=True, exist_ok=True)
    total = sum(s["duration_s"] for s in scenes)

    # 1) piste voix : phrases + silences
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in scenes:
        cmd += ["-i", s["wav"]]
    filt = "".join(f"[{i}:a]apad=whole_dur={s['duration_s']:.3f}[a{i}];" for i, s in enumerate(scenes))
    filt += "".join(f"[a{i}]" for i in range(len(scenes))) + f"concat=n={len(scenes)}:v=0:a=1[out]"
    voice = workdir / "voice.wav"
    _run(cmd + ["-filter_complex", filt, "-map", "[out]", "-ar", "44100", "-ac", "1", str(voice)])

    # 2) un plan animé par scène (panoramique lent, sens alterné)
    clips = []
    for i, s in enumerate(scenes):
        d = s["duration_s"]
        x = f"(iw-{W})*(t/{d:.3f})" if i % 2 == 0 else f"(iw-{W})*(1-t/{d:.3f})"
        y = f"(ih-{H})*(0.5+0.5*sin(t/{d:.3f}*3.14159/2))" if i % 3 == 2 else f"(ih-{H})/2"
        clip = workdir / f"clip_{i:02d}.mp4"
        if s.get("bg_video"):
            # vraie vidéo en fond (bouclée si trop courte) + calque texte transparent centré
            _run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", s["bg_video"],
                  "-loop", "1", "-framerate", str(fps), "-i", s["image"],
                  "-filter_complex", f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={fps}[b];"
                                     f"[1:v]crop={W}:{H}:(iw-{W})/2:(ih-{H})/2[o];"
                                     f"[b][o]overlay=0:0,fade=t=in:st=0:d=0.18,format=yuv420p[v]",
                  "-map", "[v]", "-t", f"{d:.3f}", "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an",
                  str(clip)])
        else:
            _run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-framerate", str(fps), "-t", f"{d:.3f}", "-i", s["image"],
                  "-vf", f"crop={W}:{H}:x='{x}':y='{y}',fade=t=in:st=0:d=0.18,format=yuv420p",
                  "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an", str(clip)])
        clips.append(clip)
    lst = workdir / "clips.txt"
    lst.write_text("".join(f"file '{c.name}'\n" for c in clips))
    raw = workdir / "video_raw.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(raw)])

    # 3) sous-titres
    ass = workdir / "captions.ass"
    cues = build_ass(scenes, ass, max_caption_chars, accent)

    # 4) assemblage final : sous-titres, barre de progression, musique atténuée sous la voix, normalisation -14 LUFS
    f1, f2, f3, f4 = music_freqs(project["niche"])
    music = (f"aevalsrc='0.05*sin(2*PI*{f1}*t)*(0.6+0.4*sin(2*PI*0.20*t))+0.035*sin(2*PI*{f2}*t)*(0.6+0.4*sin(2*PI*0.13*t))"
             f"+0.03*sin(2*PI*{f3}*t)+0.04*sin(2*PI*{f4}*t)':s=44100:d={total:.3f}")
    fontsdir = str(Path(font_path()).parent) if font_path() else "/usr/share/fonts"
    filt = (
        f"[0:v]ass={ass}:fontsdir={fontsdir}[vs];"
        f"color=c=white@0.9:s={W}x12:r={fps}:d={total:.3f}[bar];"
        f"[vs][bar]overlay=x='-W+W*t/{total:.3f}':y=0:shortest=1,format=yuv420p[v];"
        f"[2:a]lowpass=f=1800,afade=t=in:d=1.5,afade=t=out:st={max(total - 1.5, 0):.3f}:d=1.5,volume=0.55[m];"
        f"[1:a]asplit=2[vo][sc];"
        f"[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md];"
        f"[vo][md]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=44100[a]"
    )
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    final, out_mp4 = out_mp4, workdir / "master.mp4"  # rendu hors de data/final puis déplacement atomique
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-i", str(voice), "-f", "lavfi", "-i", music,
          "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
          "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
          "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", "-t", f"{total:.3f}", str(out_mp4)])

    # 5) correction fine du volume (la normalisation en un passage reste souvent 1 à 2 LU sous la cible)
    p = subprocess.run(["ffmpeg", "-nostats", "-i", str(out_mp4), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    if m and abs(target_lufs - float(m[-1])) > 0.5:
        tmp = out_mp4.with_suffix(".tmp.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out_mp4), "-c:v", "copy",
              "-af", f"volume={target_lufs - float(m[-1]):.2f}dB,alimiter=limit=0.84:level=disabled",
              "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-movflags", "+faststart", str(tmp)])
        tmp.replace(out_mp4)
    out_mp4.replace(final)

    (workdir / "project.json").write_text(json.dumps({**project, "total_s": total, "captions": cues}, ensure_ascii=False, indent=2))
    return total
