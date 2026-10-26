"""Prepare the hero's piece photographs (26 Oct 2026). Requires Pillow.

The hero shows three real pieces melting into the Laguna field. Instead of erasing information
with heavy masks, the photographs are prepared so that the page needs only a short fade:

* the Cruze cluster takes the hero's teal in its neutral, unlit areas (car interior, black hood),
  while the lit dials, needles, warning lights, the LCD and the white figures keep their colour;
* the MediaNav screen is cut out of the MENIGAR banner it was photographed against, so the whole
  unit and its menu stay visible, like the ABS module that was already cut out.

Run: python3 scripts/prepare_hero_pieces.py
"""
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'assets/home'
CLUSTER = HOME / 'cuadro-cruze-1280.webp'
SCREEN = ROOT / 'assets/media/94/94920644a5ee21d5-multimedia-3.webp'
# The unit's outline on the screen photo, measured with its slight perspective.
SCREEN_OUTLINE = [(220.5, 333.5), (859.5, 324.5), (873.5, 645.5), (222.5, 664.5)]


def tinted_cluster(strength=0.8):
    image = Image.open(CLUSTER).convert('RGB')
    _, _, value = image.convert('HSV').split()
    # Saturation and brightness of a softened copy: compression noise in the dark plastic would
    # otherwise flip single pixels between tinted and untinted.
    _, soft_saturation, soft_value = image.filter(ImageFilter.GaussianBlur(2.5)).convert('HSV').split()
    teal = ImageOps.colorize(value, black='#00212a', mid='#0a4f5c', white='#9fd6dd', midpoint=140)
    neutral = soft_saturation.point(lambda x: int(255 * strength * max(0.0, 1 - x / 165) ** 0.7))
    unlit = soft_value.point(lambda x: 255 if x < 170 else max(0, int(255 * (228 - x) / 58)))
    weight = ImageChops.multiply(neutral, unlit).filter(ImageFilter.GaussianBlur(5))
    return Image.composite(teal, image, weight)


def screen_cutout():
    image = Image.open(SCREEN).convert('RGB')
    width, height = image.size
    _, saturation, value = image.convert('HSV').split()
    # Black glossy bezel: dark and nearly neutral (the navy banner is dark but saturated).
    bezel = ImageChops.multiply(value.point(lambda x: 255 if x < 78 else 0),
                                saturation.point(lambda x: 255 if x < 120 else 0))
    bezel = bezel.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    ImageDraw.floodfill(bezel, (240, 500), 128, thresh=0)
    bezel = bezel.point(lambda x: 255 if x == 128 else 0)
    # Everything the bezel encloses (the glass and its icons) belongs to the unit.
    outside = bezel.point(lambda x: 0 if x else 255)
    ImageDraw.floodfill(outside, (0, 0), 100, thresh=0)
    unit = outside.point(lambda x: 0 if x == 100 else 255)
    unit = unit.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    outline = Image.new('L', (width * 4, height * 4), 0)
    ImageDraw.Draw(outline).polygon([(x * 4, y * 4) for x, y in SCREEN_OUTLINE], fill=255)
    alpha = ImageChops.darker(unit.filter(ImageFilter.GaussianBlur(0.8)), outline.resize((width, height), Image.LANCZOS))
    cutout = image.convert('RGBA')
    cutout.putalpha(alpha)
    return cutout.crop(alpha.point(lambda x: 255 if x > 8 else 0).getbbox())


def save(image, name, widths, **options):
    for width in widths:
        size = (width, round(image.height * width / image.width))
        target = HOME / f'{name}-{width}.webp'
        (image if size == image.size else image.resize(size, Image.LANCZOS)).save(target, 'WEBP', method=6, **options)
        print(target.relative_to(ROOT), size, target.stat().st_size, 'bytes')


if __name__ == '__main__':
    save(tinted_cluster(), 'cuadro-cruze-laguna', [800, 1280], quality=82)
    screen = screen_cutout()
    save(screen, 'pantalla-medianav-recorte', [340, screen.width], quality=84, alpha_quality=90)
