from types import SimpleNamespace

from django.test import SimpleTestCase

from .telegram_client import TelegramPublisher
from .tasks.publishing import _compose_post_text


class TelegramPublisherSplitTests(SimpleTestCase):
    def setUp(self):
        self.publisher = TelegramPublisher(api_id="123", api_hash="456")

    def test_extract_first_chunk_prefers_sentence_boundary(self):
        text = "Sentence one. Sentence two remains in the feed."
        chunk, remainder = self.publisher._extract_first_chunk(text, 25)

        self.assertEqual(chunk, "Sentence one.")
        self.assertEqual(remainder, "Sentence two remains in the feed.")

    def test_extract_first_chunk_falls_back_to_space(self):
        text = "Alpha beta gamma"
        chunk, remainder = self.publisher._extract_first_chunk(text, 11)

        self.assertEqual(chunk, "Alpha beta")
        self.assertEqual(remainder, "gamma")

    def test_extract_first_chunk_hard_limit_without_breaks(self):
        text = "Supercalifragilisticexpialidocious"
        chunk, remainder = self.publisher._extract_first_chunk(text, 10)

        self.assertEqual(chunk, "Supercalif")
        self.assertEqual(remainder, "ragilisticexpialidocious")


class ComposePostTextTests(SimpleTestCase):
    def test_includes_title_and_body(self):
        post = SimpleNamespace(title="Headline", text="Body text", publish_text=True)
        self.assertEqual(_compose_post_text(post), "Headline\n\nBody text")

    def test_only_title_when_body_missing(self):
        post = SimpleNamespace(title="Headline", text="   ", publish_text=True)
        self.assertEqual(_compose_post_text(post), "Headline")

    def test_respects_publish_text_flag(self):
        post = SimpleNamespace(title="Headline", text="Body text", publish_text=False)
        self.assertEqual(_compose_post_text(post), "")

    def test_only_body_when_no_title(self):
        post = SimpleNamespace(title="", text="Body text", publish_text=True)
        self.assertEqual(_compose_post_text(post), "Body text")
