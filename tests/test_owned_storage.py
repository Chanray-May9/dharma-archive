import json
from pathlib import Path
import unittest
from urllib.parse import urlparse


class OwnedStorageTests(unittest.TestCase):
    def test_every_archived_zip_has_an_actual_file_in_an_owned_repository(self):
        root = Path(__file__).resolve().parents[1] / 'public'
        registry = json.loads((root / 'data/mirrors.json').read_text(encoding='utf-8'))
        packages = json.loads((root / 'data/packages.json').read_text(encoding='utf-8'))
        self.assertEqual(len(packages), 741)
        for package in packages:
            with self.subTest(package=package['path']):
                mirrors = registry['files'][package['path']]
                self.assertTrue(mirrors)
                for mirror in mirrors:
                    url = urlparse(mirror['url'])
                    self.assertEqual(url.hostname, 'raw.githubusercontent.com')
                    self.assertIn(url.path.split('/')[2], ['dharma-archive-data-001', 'dharma-archive-data-002'])
                    self.assertTrue(url.path.startswith('/Chanray-May9/'))
                    self.assertTrue(url.path.endswith('/main/' + package['path']))
                    self.assertEqual(mirror['sha256'], package['sha256'])
                path = root / package['path']
                if path.exists():
                    self.assertGreater(path.stat().st_size, 0)
                    with path.open('rb') as stream:
                        self.assertEqual(stream.read(4), b'PK\x03\x04')


if __name__ == '__main__':
    unittest.main()
