from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from stage_distribution import PartReader, SplitWriter


class DistributionTests(unittest.TestCase):
    def test_split_parts_reconstruct_exact_bytes_across_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            writer = SplitWriter(root, 7)
            expected = b'first chunk and second chunk'
            self.assertEqual(writer.write(expected[:7]), 7)
            self.assertEqual(writer.write(expected[7:]), len(expected) - 7)
            writer.close()
            received = b''.join((root / name).read_bytes() for name in writer.parts)
            self.assertEqual(received, expected)
            self.assertTrue(all((root / name).stat().st_size == 7 for name in writer.parts[:-1]))
            reader = PartReader([root / name for name in writer.parts])
            try:
                reconstructed = reader.read(3) + reader.read(20) + reader.read(100)
                self.assertEqual(reconstructed, expected)
                self.assertEqual(reader.read(1), b'')
            finally:
                reader.close()


if __name__ == '__main__':
    unittest.main()
