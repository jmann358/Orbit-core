import unittest
from luna.patch_manifest import validate_manifest

SHA = "a" * 64


def proposal():
    return {"files": [{"path": "luna/development.py", "base_sha256": SHA, "replacement_sha256": "b" * 64}], "tests": ["tests/test_development_engine.py"]}


class ManifestTests(unittest.TestCase):
    def test_valid_is_review_only(self):
        result = validate_manifest(proposal())
        self.assertFalse(result["applied"])
        self.assertFalse(result["tests_run"])
        self.assertTrue(result["requires_explicit_review"])

    def test_rejects_unauthorized_path(self):
        p = proposal(); p["files"][0]["path"] = "app.py"
        with self.assertRaises(ValueError): validate_manifest(p)

    def test_rejects_duplicate_path(self):
        p = proposal(); p["files"].append(dict(p["files"][0]))
        with self.assertRaises(ValueError): validate_manifest(p)

    def test_rejects_invalid_hash(self):
        p = proposal(); p["files"][0]["base_sha256"] = "0"
        with self.assertRaises(ValueError): validate_manifest(p)

    def test_rejects_extra_fields(self):
        p = proposal(); p["command"] = "echo hi"
        with self.assertRaises(ValueError): validate_manifest(p)

    def test_rejects_duplicate_tests(self):
        p = proposal(); p["tests"] *= 2
        with self.assertRaises(ValueError): validate_manifest(p)

    def test_rejects_non_dict(self):
        with self.assertRaises(ValueError): validate_manifest(None)


if __name__ == "__main__": unittest.main()


class ReviewIntegrationTests(unittest.TestCase):
    def review(self):
        return {'path': 'luna/development.py', 'base_sha256': SHA,
                'replacement_sha256': 'b'*64, 'changed': True,
                'syntax_valid': True, 'applied': False, 'tests_run': False,
                'requires_explicit_review': True}

    def test_preview_to_manifest(self):
        from luna.patch_manifest import manifest_from_reviews
        result = manifest_from_reviews([self.review()], ['tests/test_development_engine.py'])
        self.assertEqual(result['files'][0]['path'], 'luna/development.py')
        self.assertFalse(result['applied'])

    def test_rejects_failed_or_applied_preview(self):
        from luna.patch_manifest import manifest_from_reviews
        for key, value in [('applied', True), ('syntax_valid', False),
                           ('changed', False), ('tests_run', True),
                           ('requires_explicit_review', False)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                manifest_from_reviews([{**self.review(), key: value}])

    def test_rejects_duplicate_review_paths(self):
        from luna.patch_manifest import manifest_from_reviews
        with self.assertRaises(ValueError):
            manifest_from_reviews([self.review(), self.review()])

class SafetyRegressionTests(unittest.TestCase):
    def test_rejects_shell_like_test_identifiers(self):
        for value in ("pytest -q", "tests/test_a.py; rm -rf /",
                      "../tests/test_a.py", "tests/test_a.py\\nwhoami",
                      "tests/test_a.py::test_one", "/tmp/test_a.py"):
            with self.subTest(value=value):
                p = proposal()
                p["tests"] = [value]
                with self.assertRaises(ValueError):
                    validate_manifest(p)

    def test_allowlist_is_shared_with_preview_validator(self):
        from luna.patches import ALLOWED_PATHS
        from luna.patch_manifest import ALLOWED_PATHS as manifest_paths
        self.assertIs(ALLOWED_PATHS, manifest_paths)

    def test_rejects_unchanged_review(self):
        from luna.patch_manifest import manifest_from_reviews
        review = {"path": "luna/development.py", "base_sha256": SHA,
                  "replacement_sha256": "b" * 64, "changed": False,
                  "syntax_valid": True, "applied": False, "tests_run": False,
                  "requires_explicit_review": True}
        with self.assertRaises(ValueError):
            manifest_from_reviews([review])


class WorkspaceRevisionTests(unittest.TestCase):
    def test_checks_actual_source_hash_without_writing(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from luna.patch_manifest import verify_manifest_bases
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "luna" / "development.py"
            path.parent.mkdir()
            path.write_text("x=1\n")
            before = path.read_bytes()
            manifest = proposal()
            manifest["files"][0]["base_sha256"] = hashlib.sha256(before).hexdigest()
            result = verify_manifest_bases(folder, manifest)
            self.assertTrue(result["base_revisions_verified"])
            self.assertFalse(result["applied"])
            self.assertEqual(path.read_bytes(), before)
            path.write_text("x=2\n")
            with self.assertRaises(ValueError):
                verify_manifest_bases(folder, manifest)

    def test_rejects_symlink(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from luna.patch_manifest import verify_manifest_bases
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "luna").mkdir()
            (root / "original.py").write_text("x=1\n")
            (root / "luna" / "development.py").symlink_to(root / "original.py")
            manifest = proposal()
            manifest["files"][0]["base_sha256"] = hashlib.sha256(b"x=1\n").hexdigest()
            with self.assertRaises(ValueError):
                verify_manifest_bases(root, manifest)

    def test_rejects_missing_source(self):
        import tempfile
        from luna.patch_manifest import verify_manifest_bases
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                verify_manifest_bases(folder, proposal())

    def test_rejects_large_source(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from luna.patch_manifest import verify_manifest_bases
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "luna" / "development.py"
            path.parent.mkdir()
            payload = b"x" * 30_001
            path.write_bytes(payload)
            manifest = proposal()
            manifest["files"][0]["base_sha256"] = hashlib.sha256(payload).hexdigest()
            with self.assertRaises(ValueError):
                verify_manifest_bases(folder, manifest)


class ProposalFingerprintTests(unittest.TestCase):
    def test_deterministic_and_order_independent_keys(self):
        from luna.patch_manifest import proposal_fingerprint
        first = proposal()
        second = {"tests": list(first["tests"]), "files": [{"replacement_sha256": f["replacement_sha256"], "path": f["path"], "base_sha256": f["base_sha256"]} for f in first["files"]]}
        self.assertEqual(proposal_fingerprint(first), proposal_fingerprint(second))

    def test_changed_replacement_invalidates_review(self):
        from luna.patch_manifest import proposal_fingerprint, compare_proposal_fingerprint
        first = proposal()
        fingerprint = proposal_fingerprint(first)
        self.assertTrue(compare_proposal_fingerprint(first, fingerprint))
        modified = proposal()
        modified["files"][0]["replacement_sha256"] = "c" * 64
        with self.assertRaises(ValueError):
            compare_proposal_fingerprint(modified, fingerprint)

    def test_changed_test_list_invalidates_review(self):
        from luna.patch_manifest import proposal_fingerprint, compare_proposal_fingerprint
        first = proposal()
        fingerprint = proposal_fingerprint(first)
        modified = proposal()
        modified["tests"] = ["tests/test_changed.py"]
        with self.assertRaises(ValueError):
            compare_proposal_fingerprint(modified, fingerprint)

    def test_rejects_invalid_expected_fingerprint(self):
        from luna.patch_manifest import compare_proposal_fingerprint
        for value in (None, "abc", "A" * 64, 42):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare_proposal_fingerprint(proposal(), value)

class ReplacementIntegrityTests(unittest.TestCase):
    def test_exact_content_matches_and_is_not_written(self):
        import hashlib
        from luna.patch_manifest import verify_replacement_contents
        manifest = proposal()
        text = "x=42\n"
        manifest["files"][0]["replacement_sha256"] = hashlib.sha256(text.encode()).hexdigest()
        result = verify_replacement_contents(manifest, {"luna/development.py": text})
        self.assertTrue(result["replacement_contents_verified"])
        self.assertFalse(result["applied"])

    def test_tampered_content_rejected(self):
        from luna.patch_manifest import verify_replacement_contents
        with self.assertRaises(ValueError):
            verify_replacement_contents(proposal(), {"luna/development.py": "changed"})

    def test_missing_extra_and_invalid_payloads_rejected(self):
        from luna.patch_manifest import verify_replacement_contents
        for replacements in ({}, {"app.py": "x"}, None,
                             {"luna/development.py": b"bytes"},
                             {"luna/development.py": "x" * 30001}):
            with self.subTest(replacements=str(replacements)[:40]):
                with self.assertRaises(ValueError):
                    verify_replacement_contents(proposal(), replacements)
