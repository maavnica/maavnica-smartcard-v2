import unittest

from app.main import _sanitize_public_slug


class SanitizePublicSlugTests(unittest.TestCase):
    def test_demo2_unchanged(self):
        self.assertEqual(_sanitize_public_slug("demo2"), "demo2")

    def test_demo2_trailing_quote_removed(self):
        self.assertEqual(_sanitize_public_slug('demo2"'), "demo2")

    def test_demo2_with_invisible_unicode_removed(self):
        self.assertEqual(_sanitize_public_slug("demo2'\u2060"), "demo2")

    def test_latam_slug_kept(self):
        self.assertEqual(_sanitize_public_slug("demo-latam-plomero"), "demo-latam-plomero")

    def test_arnaud_slug_kept(self):
        self.assertEqual(_sanitize_public_slug("arnaud-huard"), "arnaud-huard")

    def test_arnaud_slug_trimmed(self):
        self.assertEqual(_sanitize_public_slug(" arnaud-huard "), "arnaud-huard")


if __name__ == "__main__":
    unittest.main()
