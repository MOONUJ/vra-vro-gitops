import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "tooling" / "vcf"))

from content_pull import ContentPullError, ContentPullService


class ContentPullServiceTest(unittest.TestCase):
    def _service(self, root):
        return ContentPullService(root, root / ".gitops" / "pull-previews", "test")

    def test_preview_does_not_change_content_and_accept_requires_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / "content" / "automation" / "policies"
            content.mkdir(parents=True)
            current = content / "lease.json"
            current.write_text('{"value": 1}\n', encoding="utf-8")
            service = self._service(root)

            def renderer(staging_root):
                target = staging_root / "content" / "automation" / "policies" / "lease.json"
                target.write_text('{"value": 2}\n', encoding="utf-8")

            preview_path, preview = service.create_preview(renderer, {"endpoint": "https://example.com"})

            self.assertEqual(current.read_text(encoding="utf-8"), '{"value": 1}\n')
            self.assertEqual(preview["spec"]["changes"][0]["action"], "UPDATE")
            with self.assertRaisesRegex(ContentPullError, "승인 hash"):
                service.accept(preview_path, "wrong")

            _, result = service.accept(preview_path, preview["metadata"]["previewHash"])
            self.assertEqual(result["spec"]["status"], "ACCEPTED")
            self.assertEqual(current.read_text(encoding="utf-8"), '{"value": 2}\n')
            with self.assertRaisesRegex(ContentPullError, "이미 accept"):
                service.accept(preview_path, preview["metadata"]["previewHash"])

    def test_local_change_after_preview_blocks_accept(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / "content"
            content.mkdir()
            current = content / "file.txt"
            current.write_text("before\n", encoding="utf-8")
            service = self._service(root)

            def renderer(staging_root):
                (staging_root / "content" / "file.txt").write_text("remote\n", encoding="utf-8")

            preview_path, preview = service.create_preview(renderer, {})
            current.write_text("local-change\n", encoding="utf-8")

            with self.assertRaisesRegex(ContentPullError, "로컬 content가 변경"):
                service.accept(preview_path, preview["metadata"]["previewHash"])

    def test_preview_rejects_implicit_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = root / "content"
            content.mkdir()
            (content / "file.txt").write_text("before\n", encoding="utf-8")
            service = self._service(root)

            def renderer(staging_root):
                (staging_root / "content" / "file.txt").unlink()

            with self.assertRaisesRegex(ContentPullError, "삭제"):
                service.create_preview(renderer, {})

    def test_tampered_preview_content_blocks_accept(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "content").mkdir()
            service = self._service(root)

            def renderer(staging_root):
                (staging_root / "content" / "new.txt").write_text("remote\n", encoding="utf-8")

            preview_path, preview = service.create_preview(renderer, {})
            (preview_path / "content" / "new.txt").write_text("tampered\n", encoding="utf-8")

            with self.assertRaisesRegex(ContentPullError, "content hash"):
                service.accept(preview_path, preview["metadata"]["previewHash"])


if __name__ == "__main__":
    unittest.main()
