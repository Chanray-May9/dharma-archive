import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_archive import make_package, manifest, xml_record
from verify import parse_manifest, verify_directory, verify_zip


class PreservationTests(unittest.TestCase):
    def test_original_bytes_survive_package_and_deep_verification(self):
        original = b'{"text":"\xe8\x88\xac\xe8\x8b\xa5"}\r\n'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'test.zip'
            make_package(path, {'data/original/input.json': original}, [{'revision': 'fixed'}])
            self.assertEqual(verify_zip(path), 2)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.read('data/original/input.json'), original)

    def test_corruption_is_detected_even_when_zip_crc_is_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'damaged.zip'
            digest = hashlib.sha256(b'original').hexdigest()
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('data/original.txt', b'changed')
                archive.writestr('manifest-sha256.txt', f'{digest}  data/original.txt\n')
            with self.assertRaisesRegex(ValueError, 'Corrupt ZIP'):
                verify_zip(path)

    def test_missing_or_unlisted_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'data').mkdir()
            (root / 'data/catalog.json').write_text('[]', encoding='utf-8')
            (root / 'data/status.json').write_text(json.dumps({'documents': 0}), encoding='utf-8')
            manifest(root)
            self.assertEqual(verify_directory(root), 2)
            (root / 'data/unlisted.txt').write_text('new', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Payload set'):
                verify_directory(root)

    def test_unsafe_manifest_paths_and_duplicates_are_rejected(self):
        digest = '0' * 64
        for name in ('../escape', '/absolute', 'C:/escape', 'data/../../escape', 'data\\escape'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_manifest(f'{digest}  {name}\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            parse_manifest(f'{digest}  data/text\n{digest}  data/text\n')

    def test_tei_gaiji_notes_and_variant_readings_remain_visible(self):
        xml = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title level="m">心經</title><author>玄奘</author></titleStmt></fileDesc><encodingDesc><charDecl><char xml:id="CB1"><mapping type="unicode">U+822C</mapping></char></charDecl></encodingDesc></teiHeader><text><body><p><g ref="#CB1"/>若<g ref="#CB2"/><note>校注</note><app><lem>一</lem><rdg>二</rdg></app></p></body></text></TEI>'''
        title, author, reading = xml_record(xml.encode('utf-8'))
        self.assertEqual((title, author), ('心經', '玄奘'))
        self.assertIn('般若[CB2]', reading)
        self.assertIn('【校注：校注】', reading)
        self.assertIn('一【異讀：二】', reading)


if __name__ == '__main__':
    unittest.main()
