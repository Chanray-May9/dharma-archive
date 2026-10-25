import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import mirror


class MirrorTests(unittest.TestCase):
    def run_check(self, output, allow_shards):
        payload = b'preserved original'
        digest = hashlib.sha256(payload).hexdigest()
        manifest = f'{digest}  data/example.txt\n'.encode('utf-8')
        registry = {'files': {'data/example.txt': [{'url': 'https://alternate.invalid/data/example.txt'}]}}

        def retrieve(base, name):
            if name == 'manifest-sha256.txt':
                return manifest
            if name == 'data/mirrors.json':
                return json.dumps(registry).encode('utf-8')
            return b'damaged primary bytes'

        arguments = ['mirror.py', 'check', '--base', 'https://primary.invalid', '--output', str(output), '--manifest-sha256', hashlib.sha256(manifest).hexdigest()]
        if allow_shards:
            arguments.append('--allow-shards')
        with patch.object(sys, 'argv', arguments), patch.object(mirror, 'retrieve', side_effect=retrieve), patch.object(mirror, 'urlopen', return_value=io.BytesIO(payload)) as alternate:
            if allow_shards:
                mirror.main()
                alternate.assert_called_once()
            else:
                with self.assertRaises(SystemExit):
                    mirror.main()
                alternate.assert_not_called()
        return json.loads((output / 'mirror-receipt.json').read_text(encoding='utf-8'))

    def test_strict_audit_cannot_hide_primary_corruption_with_another_replica(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = self.run_check(Path(temporary), False)
            self.assertFalse(receipt['ok'])
            self.assertEqual(receipt['verified'], 0)

    def test_explicit_shard_check_can_recover_from_wrong_primary_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = self.run_check(Path(temporary), True)
            self.assertTrue(receipt['ok'])
            self.assertEqual(receipt['verified'], 1)


if __name__ == '__main__':
    unittest.main()
