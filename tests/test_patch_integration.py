import hashlib
import tempfile
import unittest
from pathlib import Path
from luna.patches import review_patch
from luna.patch_manifest import manifest_from_reviews, verify_manifest_bases, verify_replacement_contents, proposal_fingerprint, compare_proposal_fingerprint

class RealPreviewIntegrationTests(unittest.TestCase):
    def test_real_preview_to_verified_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'luna').mkdir()
            target=root/'luna/development.py'
            target.write_text('value = 1\n')
            base=hashlib.sha256(target.read_bytes()).hexdigest()
            candidate='value = 2\n'
            report=review_patch(root,'luna/development.py',base,candidate)
            report_manifest=manifest_from_reviews([report],['tests/test_development_engine.py'])
            manifest=report_manifest
            self.assertTrue(verify_manifest_bases(root,manifest)['base_revisions_verified'])
            self.assertTrue(verify_replacement_contents(manifest,{'luna/development.py':candidate})['replacement_contents_verified'])
            self.assertTrue(compare_proposal_fingerprint(manifest,proposal_fingerprint(manifest)))
            self.assertEqual(target.read_text(),'value = 1\n')
            target.write_text('value = 3\n')
            with self.assertRaises(ValueError):
                verify_manifest_bases(root,manifest)
    def test_real_preview_rejects_unchanged_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'luna').mkdir()
            target=root/'luna/development.py'
            target.write_text('x=1\n')
            sha=hashlib.sha256(target.read_bytes()).hexdigest()
            report=review_patch(root,'luna/development.py',sha,'x=1\n')
            with self.assertRaises(ValueError):
                manifest_from_reviews([report])

    def test_chained_review_rejects_forged_status(self):
        from luna.patch_manifest import validate_manifest
        base = {"files": [{"path": "luna/development.py", "base_sha256": "a"*64,
                            "replacement_sha256": "b"*64}], "tests": []}
        safe = validate_manifest(base)
        self.assertEqual(validate_manifest(safe), safe)
        for key, value in (("applied", True), ("tests_run", True),
                           ("requires_explicit_review", False)):
            tampered = dict(safe, **{key: value})
            with self.assertRaises(ValueError):
                validate_manifest(tampered)
        with self.assertRaises(ValueError):
            validate_manifest(dict(safe, base_revisions_verified=True))
