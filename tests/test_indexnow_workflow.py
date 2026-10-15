"""Regression checks for the actual IndexNow readiness code, without network calls."""
import contextlib
import io
import os
from pathlib import Path
import tempfile
import textwrap
import unittest
from unittest.mock import patch


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/indexnow.yml"
BLOCK = WORKFLOW.read_text(encoding="utf-8").split("python3 - <<'PY'\n", 1)[1]
READINESS = textwrap.dedent(BLOCK.split("\n          PY", 1)[0])
HOST = "https://xn--80aafwvmkbibjcl2m.xn--p1ai"
KEY = "91f7e03d63fefe7098456dca52d83d4a"
PAGE = b"<!doctype html><html><head><title>Original</title></head><body><h1>Article</h1></body></html>"


class Response:
    def __init__(self, url, body, *, headers=None, status=200):
        self.url, self.body, self.status = url, body, status
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.body


class IndexNowPublicationTests(unittest.TestCase):
    def run_readiness(self, source=PAGE, published=PAGE, *, headers=None, status=200):
        sitemap = (f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                   f'<url><loc>{HOST}/article.html</loc></url></urlset>').encode()
        requested = []

        def open_public(request, timeout):
            url = request.full_url
            requested.append(url)
            if url == f"{HOST}/{KEY}.txt":
                return Response(url, KEY.encode())
            if url == f"{HOST}/sitemap.xml":
                return Response(url, sitemap)
            if url == f"{HOST}/article.html":
                return Response(url, published, headers=headers, status=status)
            raise AssertionError(f"Unexpected request: {url}")

        original_dir = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                Path("sitemap.xml").write_bytes(sitemap)
                Path("article.html").write_bytes(source)
                output = str(Path(directory) / "outputs")
                with patch.dict(os.environ, {"GITHUB_OUTPUT": output}), \
                        patch("urllib.request.urlopen", open_public), \
                        contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(READINESS, str(WORKFLOW), "exec"), {})
                values = dict(line.split("=", 1) for line in Path(output).read_text().splitlines())
                self.assertEqual(len(requested), 3)
                return values
            finally:
                os.chdir(original_dir)

    def test_content_edit_changes_notification_key_without_sitemap_change(self):
        before = self.run_readiness()
        updated = PAGE.replace(b"Original", b"Updated")
        after = self.run_readiness(updated, updated)
        self.assertEqual(before["site_ready"], "true")
        self.assertEqual(after["site_ready"], "true")
        self.assertNotEqual(before["file_hash"], after["file_hash"])
        self.assertEqual(after, self.run_readiness(updated, updated))

    def test_http_200_with_stale_article_defers_notification(self):
        updated = PAGE.replace(b"Original", b"Updated")
        stale = self.run_readiness(updated, PAGE)
        published = self.run_readiness(updated, updated)
        self.assertEqual(stale["site_ready"], "false")
        self.assertEqual(published["site_ready"], "true")
        self.assertEqual(stale["file_hash"], published["file_hash"])

    def test_noindex_or_missing_page_never_confirms_publication(self):
        blocked = PAGE.replace(b"</head>", b'<meta name="robots" content="noindex"></head>')
        self.assertEqual(self.run_readiness(blocked, blocked)["site_ready"], "false")
        self.assertEqual(self.run_readiness(headers={"Content-Type": "text/html", "X-Robots-Tag": "noindex"})["site_ready"], "false")
        self.assertEqual(self.run_readiness(status=404)["site_ready"], "false")


if __name__ == "__main__":
    unittest.main()
