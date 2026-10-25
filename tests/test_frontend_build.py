from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_frontend import build


class FrontendBuildTests(unittest.TestCase):
    def test_each_destination_has_a_real_standalone_html_page(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(project / 'frontend', root / 'frontend')
            (root / 'public').mkdir()
            build(root)
            pages = {'index.html': 'home', 'library.html': 'library', 'languages.html': 'languages', 'packages.html': 'packages', 'recovery.html': 'recovery', 'reader.html': 'reader'}
            for filename, page in pages.items():
                with self.subTest(page=page):
                    content = (root / 'public' / filename).read_text(encoding='utf-8')
                    self.assertIn(f'data-page="{page}"', content)
                    self.assertNotIn('{{', content)
                    for target in ['library.html', 'languages.html', 'packages.html', 'recovery.html']:
                        self.assertIn(f'href="{target}"', content)
                    self.assertNotIn('href="#library"', content)
                    self.assertNotIn('保存是一件持续的事', content)
                    self.assertNotIn('不把钥匙交给网站', content)
            home = (root / 'public/index.html').read_text(encoding='utf-8')
            self.assertIn('href="languages.html"><strong id="stat-languages"', home)
            self.assertNotIn('id="catalog-body"', home)
            library = (root / 'public/library.html').read_text(encoding='utf-8')
            self.assertIn('value="simplified">简体阅读', library)
            self.assertNotIn('class="hero"', library)


if __name__ == '__main__':
    unittest.main()
