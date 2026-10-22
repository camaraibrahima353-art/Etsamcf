"""Visuels procéduraux (Pillow) : aucune image tierce, donc aucun risque de droits.

Chaque scène produit une image légèrement plus grande que 1080x1920 pour permettre un
mouvement de caméra lent (effet Ken Burns) au montage. Les zones masquées par l'interface
des plateformes (haut ~150 px, bas ~450 px, colonne droite ~140 px) restent sans texte.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
OVER = 1.12  # marge pour le mouvement de caméra
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
FONT_REGULAR = [
    "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
LICENSE = "Visuel procédural généré par le studio (Pillow) ; police Inter (SIL OFL 1.1) ou DejaVu (licence libre)"


def _font(size, bold=True):
    for p in FONT_CANDIDATES if bold else FONT_REGULAR:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def font_path() -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return ""


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(draw, text, max_w, max_h, start=150, min_size=56):
    size = start
    while size >= min_size:
        f = _font(size)
        lines = _wrap(draw, text, f, max_w)
        lh = int(size * 1.12)
        if len(lines) * lh <= max_h and all(draw.textlength(l, font=f) <= max_w for l in lines):
            return f, lines, lh
        size -= 6
    f = _font(min_size)
    return f, _wrap(draw, text, f, max_w), int(min_size * 1.12)


def _background(palette, seed):
    rnd = random.Random(seed)
    w, h = int(W * OVER), int(H * OVER)
    top, mid, light = (_hex(c) for c in palette)
    k = np.linspace(0, 1, h)[:, None]  # dégradé vertical
    rows = np.array(top) * (1 - k) + np.array(mid) * 0.35 * k + np.array(top) * 0.4 * k
    img = Image.fromarray(np.repeat(rows[:, None, :], w, axis=1).clip(0, 255).astype("uint8"), "RGB")
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(7):  # formes géométriques floues
        r = rnd.randint(120, 420)
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        col = mid if rnd.random() < 0.6 else light
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*col, rnd.randint(40, 90)))
    for i in range(14):  # grille de points discrète
        for j in range(24):
            d.ellipse([60 + i * 90, 60 + j * 90, 64 + i * 90, 64 + j * 90], fill=(*light, 28))
    layer = layer.filter(ImageFilter.GaussianBlur(28))
    return Image.alpha_composite(img.convert("RGBA"), layer), (top, mid, light)


def _shadow_text(img, xy, text, font, fill, anchor="mm"):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((xy[0] + 6, xy[1] + 8), text, font=font, fill=(0, 0, 0, 170), anchor=anchor)
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(img).text(xy, text, font=font, fill=fill, anchor=anchor)


def render_scene(out: Path, onscreen: str, visual: dict, palette: list, niche_label: str, index: int, total: int, seed: str):
    img, (top, mid, light) = _background(palette, f"{seed}-{index}")
    w, h = img.size
    ox, oy = (w - W) // 2, (h - H) // 2  # origine de la zone visible centrale
    d = ImageDraw.Draw(img)
    vtype = visual.get("type", "text")
    accent = visual.get("accent", "")
    white = (255, 255, 255, 255)
    lightc = (*light, 255)

    # pastille de niche (zone haute sûre, sous l'interface)
    pill_font = _font(40, bold=True)
    label = niche_label.upper()
    while d.textlength(label, font=pill_font) > W - 420 and len(label) > 4:
        label = label[:-2].rstrip() + "…"
    tw = d.textlength(label, font=pill_font)
    px0, py0 = ox + 80, oy + 190
    d.rounded_rectangle([px0, py0, px0 + tw + 60, py0 + 74], radius=37, fill=(*mid, 235))
    d.text((px0 + 30, py0 + 37), label, font=pill_font, fill=white, anchor="lm")
    # compteur de scène (incite à rester jusqu'au bout)
    d.text((ox + W - 170, py0 + 37), f"{index + 1}/{total}", font=_font(40), fill=(*light, 220), anchor="rm")

    cx = ox + (W - 140) // 2 + 30  # centre horizontal hors colonne d'icônes
    area_top, area_h = oy + 330, 760
    max_w = W - 260

    if vtype == "bignumber" and accent:
        nf = _font(300 if len(accent) <= 4 else 200)
        _shadow_text(img, (cx, area_top + 190), accent, nf, lightc)
        f, lines, lh = _fit(d, onscreen, max_w, 360, start=96)
        y = area_top + 420
    elif vtype == "question":
        _shadow_text(img, (cx, area_top + 150), "?", _font(300), lightc)
        f, lines, lh = _fit(d, onscreen, max_w, area_h - 360, start=120)
        y = area_top + 340
    elif vtype == "list" and accent:
        r = 95
        d.ellipse([cx - r, area_top + 40, cx + r, area_top + 40 + 2 * r], fill=(*light, 255))
        d.text((cx, area_top + 40 + r), accent, font=_font(120), fill=(*top, 255), anchor="mm")
        f, lines, lh = _fit(d, onscreen, max_w, 480, start=110)
        y = area_top + 290
    elif vtype == "reveal":
        d.rounded_rectangle([ox + 90, area_top, ox + W - 170, area_top + area_h], radius=48, outline=(*light, 255), width=10)
        f, lines, lh = _fit(d, onscreen, max_w - 80, area_h - 120, start=120)
        y = area_top + (area_h - len(lines) * lh) // 2
    else:  # title / text
        f, lines, lh = _fit(d, onscreen, max_w, area_h, start=140 if vtype == "title" else 116)
        y = area_top + (area_h - len(lines) * lh) // 2
        if vtype == "title":
            ub = y + len(lines) * lh + 30
            d.rounded_rectangle([cx - 170, ub, cx + 170, ub + 18], radius=9, fill=(*light, 255))

    for i, line in enumerate(lines):
        _shadow_text(img, (cx, y + i * lh + lh // 2), line, f, white)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, quality=92)
    return out


def render_thumbnail(out: Path, title: str, palette: list, niche_label: str, seed: str):
    """Miniature 1080x1920 (couverture) à partir du titre."""
    tmp = out.with_suffix(".big.png")
    title = "".join(ch for ch in title if ord(ch) < 0x2190).strip()  # la police n'a pas d'émojis
    render_scene(tmp, title,{"type": "title"}, palette, niche_label, 0, 1, seed + "-thumb")
    img = Image.open(tmp)
    w, h = img.size
    img.crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H)).save(out, quality=90)
    tmp.unlink(missing_ok=True)
    return out


def music_freqs(niche_id: str):
    """Accord de base par niche pour la nappe musicale procédurale."""
    roots = {"science": 220.0, "histoire": 196.0, "espace": 174.6, "finance": 233.1, "tech_ia": 246.9,
             "psycho": 207.7, "langues": 261.6, "quiz": 293.7, "afrique": 185.0, "maths": 277.2}
    r = roots.get(niche_id, 220.0)
    return [r, r * math.pow(2, 4 / 12), r * math.pow(2, 7 / 12), r / 2]
