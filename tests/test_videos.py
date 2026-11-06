"""The videos of the fichas (4 Nov 2026): they play on the page, and nothing reaches YouTube before a click.

WordPress embedded the player on every visit. The new site showed a plain link instead, because it loads nothing
from third parties on its own. The fichas now use the player of Sobre nosotros: MENIGAR's own photo as the poster,
and YouTube only when the visitor asks for it.
"""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from public_copy import YOUTUBE_VIDEOS
from source_sections import render_sections, youtube_video

FRAME = re.compile(
    r'<div class="repair-video-frame" data-embed="youtube" data-embed-src="([^"]+)" data-embed-title="Vídeo de YouTube: ([^"]+)">'
    r'<img src="([^"]+)" width="640" height="480" alt="" loading="lazy" decoding="async">'
    r'<a class="repair-video-play" href="https://www\.youtube\.com/watch\?v=([^"]+)" target="_blank" rel="noopener noreferrer" '
    r'data-embed-load aria-label="Reproducir el vídeo: ([^"]+)">')


def published_fichas():
    catalogue = (ROOT / 'data' / 'catalogo-v2.js').read_text(encoding='utf-8')
    records = json.loads(catalogue.split('window.MENIGAR_CATALOG = ')[1].strip().rstrip(';'))
    return {r['localPath']: (ROOT / r['localPath'].lstrip('/') / 'index.html').read_text(encoding='utf-8') for r in records}


class PublishedVideos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = published_fichas()
        cls.frames = {path: FRAME.findall(html) for path, html in cls.pages.items()}
        cls.frames = {path: found for path, found in cls.frames.items() if found}

    def test_every_video_plays_on_its_ficha(self):
        self.assertEqual(sum(map(len, self.frames.values())), 44)
        self.assertEqual(len(self.frames), 37)
        self.assertEqual({frame[0] for found in self.frames.values() for frame in found}, set(YOUTUBE_VIDEOS))
        self.assertEqual(sum('data-embed=' in html for html in self.pages.values()), 37, 'Ningún reproductor con otro marcado.')
        self.assertEqual([path for path, html in self.pages.items() if 'Ver vídeo de este servicio' in html], [])

    def test_each_player_links_to_the_same_video_it_plays(self):
        for found in self.frames.values():
            for video, title, poster, linked, label in found:
                self.assertRegex(video, r'^[\w-]{11}$', 'app.js solo admite identificadores de 11 caracteres.')
                self.assertEqual((video, title, title), (linked, YOUTUBE_VIDEOS[video][0], label))
                self.assertEqual(poster, YOUTUBE_VIDEOS[video][1])

    def test_nothing_reaches_youtube_before_the_click(self):
        for path, html in self.pages.items():
            self.assertNotRegex(html, r'(?i)<iframe', path)
            self.assertNotIn('youtube.com/embed', html, path)
            self.assertNotIn('ytimg.com', html, path)

    def test_posters_are_menigar_photos_of_the_library(self):
        for title, poster in YOUTUBE_VIDEOS.values():
            self.assertRegex(poster, r'^/assets/media/[0-9a-f]{2}/[0-9a-f]{16}-[\w-]+\.webp$', title)
            self.assertTrue((ROOT / poster.lstrip('/')).is_file(), poster)

    def test_videos_of_one_page_are_told_apart_by_their_photo(self):
        for path, found in self.frames.items():
            self.assertEqual(len({frame[2] for frame in found}), len(found), path)

    def test_titles_read_as_the_rest_of_the_site(self):
        for title, _ in YOUTUBE_VIDEOS.values():
            self.assertNotRegex(title, r'(?i)test repair|taller')
            self.assertFalse(title.isupper(), title)


class ProcessVideos(unittest.TestCase):
    """The two videos the owner sent, made with AI, in Cómo funciona. They come from the site itself, not from YouTube."""

    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / 'envios/index.html').read_text(encoding='utf-8')
        cls.frames = re.findall(r'data-embed="video" data-embed-src="([^"]+)" data-embed-title="[^"]+"><img src="([^"]+)"[^>]*alt=""[^>]*>'
                                r'<a class="p-video-play" href="([^"]+)"', cls.html)

    def test_both_wait_for_the_click(self):
        self.assertEqual(len(self.frames), 2)
        self.assertNotRegex(self.html, r'(?i)<video|<iframe', 'Abrir la página no descarga ningún vídeo.')

    def test_the_player_accepts_them_and_they_are_light(self):
        app = (ROOT / 'app.js').read_text(encoding='utf-8')
        self.assertIn(r'/^\/assets\/video\/[\w-]+\.mp4$/', app)
        for video, poster, link in self.frames:
            self.assertEqual(video, link)
            self.assertRegex(video, r'^/assets/video/[\w-]+\.mp4$')
            self.assertLess((ROOT / video.lstrip('/')).stat().st_size, 10_000_000, video)
            self.assertLess((ROOT / poster.lstrip('/')).stat().st_size, 200_000, poster)

    def test_the_page_says_they_are_made_with_ai(self):
        self.assertIn('Vídeos realizados con inteligencia artificial.', self.html)

    def test_they_stay_apart_from_the_filmed_videos(self):
        about = (ROOT / 'sobre-nosotros/index.html').read_text(encoding='utf-8')
        self.assertIn('grabadas en el laboratorio', about)
        self.assertNotIn('/assets/video/', about)

    def test_every_way_of_serving_the_site_lets_them_through(self):
        for source in ('scripts/build_vercel_static.cjs', 'scripts/build_review_package.py', 'servidor.py',
                       'backend/review-router.php', 'backend/dev-router.php'):
            self.assertIn('mp4', (ROOT / source).read_text(encoding='utf-8'), source)


class Renderer(unittest.TestCase):
    known = 'https://www.youtube.com/embed/h7pEn5sztoU'

    def html(self, *blocks):
        ordered = [{'order': i, **block} for i, block in enumerate(blocks, 1)]
        return render_sections({'uid': 'x', 'brand': '', 'description': '', 'title': 'Prueba',
                                'sourceSections': [{'title': 'Apartado', 'anchor': 'a', 'blocks': ordered}]})

    def test_a_reviewed_video_is_recognised_whatever_its_parameters(self):
        for url in (self.known, self.known + '?si=abc', self.known + '?feature=oembed',
                    'https://www.youtube-nocookie.com/embed/h7pEn5sztoU', 'http://www.youtube.com/embed/h7pEn5sztoU'):
            self.assertEqual(youtube_video(url)[0], 'h7pEn5sztoU', url)

    def test_any_other_embed_stays_a_link(self):
        for url in ('https://www.youtube.com/embed/AAAAAAAAAAA', 'https://example.com/embed/h7pEn5sztoU',
                    'https://example.com/https://www.youtube.com/embed/h7pEn5sztoU'):
            self.assertIsNone(youtube_video(url), url)
            html = self.html({'kind': 'embed', 'src': url})
            self.assertIn('repair-related-link', html)
            self.assertNotIn('data-embed', html)

    def test_videos_in_a_row_share_a_grid_and_a_text_between_them_splits_it(self):
        video = {'kind': 'embed', 'src': self.known}
        together = self.html(video, {'kind': 'text', 'text': ''}, video)
        self.assertEqual(together.count('<div class="repair-video-grid repair-video-grid--varios">'), 1)
        apart = self.html(video, {'kind': 'text', 'text': 'Entre medias'}, video)
        self.assertEqual(apart.count('<div class="repair-video-grid">'), 2)
        self.assertLess(apart.index('</figure></div>'), apart.index('Entre medias'))

    def test_a_video_keeps_its_place_among_the_photos(self):
        photo = {'kind': 'image', 'src': '/assets/media/00/foto.webp', 'alt': 'Foto'}
        html = self.html(photo, {'kind': 'embed', 'src': self.known}, photo)
        self.assertEqual(html.count('<div class="repair-photo-grid">'), 2)
        self.assertLess(html.index('repair-photo-grid'), html.index('repair-video-grid'))
        self.assertLess(html.index('repair-video-grid'), html.rindex('repair-photo-grid'))


if __name__ == '__main__':
    unittest.main()
