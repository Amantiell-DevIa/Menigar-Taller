"""The photo library (4 Nov 2026): originals instead of Live Composer's small copies, and photos the right way up.

The old pages showed copies such as name-400x300.jpg, which WordPress does not list as sizes of the image, so
they came into the library as they were. A copy now gives way to its original when the original is clearly
larger and the same picture.
"""
import json
from pathlib import Path
import random
import re
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_local_media import COPY_SUFFIX, replaces_copy


def photo(seed, size=(640, 480), mode='RGB'):
    """A reproducible picture: coloured blocks on a background that depends on the seed."""
    rng = random.Random(seed)
    image = Image.new('RGB', size, tuple(rng.randrange(256) for _ in range(3)))
    draw = ImageDraw.Draw(image)
    for _ in range(30):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        draw.rectangle((x, y, x + size[0] // 4, y + size[1] // 4), fill=tuple(rng.randrange(256) for _ in range(3)))
    return image.convert(mode)


class ReplacesCopyTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.dir = Path(self.folder.name)

    def saved(self, image, name):
        path = self.dir / name
        image.save(path)
        return path

    def test_the_same_picture_clearly_larger_replaces_the_copy(self):
        original = photo(1)
        self.assertTrue(replaces_copy(self.saved(original.resize((400, 300)), 'a-400x300.png'), self.saved(original, 'a.png')))

    def test_a_different_picture_never_replaces_the_copy(self):
        # Control: same name and proportions, a different photo.
        self.assertFalse(replaces_copy(self.saved(photo(1, (400, 300)), 'a-400x300.png'), self.saved(photo(2), 'a.png')))

    def test_an_original_that_is_not_clearly_larger_keeps_the_copy(self):
        original = photo(3, (440, 330))
        self.assertFalse(replaces_copy(self.saved(original.resize((400, 300)), 'a-400x300.png'), self.saved(original, 'a.png')))

    def test_a_copy_cut_from_the_middle_of_the_original_still_counts(self):
        original = photo(4)
        square = original.crop((80, 0, 560, 480)).resize((300, 300))
        self.assertTrue(replaces_copy(self.saved(square, 'a-300x300.png'), self.saved(original, 'a.png')))

    def test_transparency_is_compared_over_white(self):
        # The invisible band is black in the copy and white in the original, as in mante_freno.png.
        picture = photo(5, mode='RGBA')
        visible = Image.new('L', picture.size, 255)
        ImageDraw.Draw(visible).rectangle((0, 0, 640, 120), fill=0)
        original = Image.composite(picture, Image.new('RGBA', picture.size, (255, 255, 255, 0)), visible)
        copy = Image.composite(picture, Image.new('RGBA', picture.size, (0, 0, 0, 0)), visible).resize((400, 300), Image.Resampling.NEAREST)
        self.assertTrue(replaces_copy(self.saved(copy, 'a-400x300.png'), self.saved(original, 'a.png')))

    def test_an_animated_original_keeps_the_still_copy(self):
        frames = [photo(6), photo(7)]
        animated = self.dir / 'a.gif'
        frames[0].save(animated, save_all=True, append_images=frames[1:])
        self.assertFalse(replaces_copy(self.saved(frames[0].resize((400, 300)), 'a-400x300.png'), animated))

    def test_only_the_size_at_the_end_of_the_name_marks_a_copy(self):
        self.assertEqual(COPY_SUFFIX.sub('', '/uploads/2021/10/bmw_serie-3_e30-400x300.jpg'), '/uploads/2021/10/bmw_serie-3_e30.jpg')
        self.assertEqual(COPY_SUFFIX.sub('', '/uploads/640x480-cuadro.jpg'), '/uploads/640x480-cuadro.jpg')


class LibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'data/media-local-manifest.json').read_text())

    def test_the_folder_holds_exactly_the_library(self):
        listed = {entry['localPath'] for entry in self.manifest['files']}
        on_disk = {'/' + path.relative_to(ROOT).as_posix() for path in (ROOT / 'assets/media').rglob('*') if path.is_file() and path.name != '.DS_Store'}
        self.assertEqual(on_disk - listed, set(), 'Archivos que ya no usa nadie.')
        self.assertEqual(listed - on_disk, set(), 'Archivos que faltan.')

    def test_only_a_few_small_copies_remain(self):
        copies = [entry for entry in self.manifest['files'] if re.search(r'-\d+x\d+\.\w+$', entry['backupPath'])]
        self.assertLess(len(copies), 60, 'Las copias de Live Composer dan paso a sus originales.')

    def test_photos_with_a_stale_rotation_tag_stay_upright(self):
        # These displays read upright as stored: their tag says to turn them.
        for name in ['display_fiat_ducato_999999', 'fallo_display_vw_golf_3', 'display_nissan_micra']:
            entries = [entry for entry in self.manifest['files'] if name in entry['backupPath']]
            self.assertTrue(entries)
            for entry in entries:
                with self.subTest(file=entry['localPath']):
                    self.assertGreater(entry['width'], entry['height'])
                    with Image.open(ROOT / entry['localPath'].lstrip('/')) as image:
                        self.assertNotIn(image.getexif().get(274), (3, 6, 8), 'Sin etiqueta de giro en el archivo publicado.')


if __name__ == '__main__':
    unittest.main()
