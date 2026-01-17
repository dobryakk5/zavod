import pytest
from django.test import TestCase
from core.models import Post, Client
from core.tasks.generation import generate_post_from_trend
from core.services.product_relations import merge_related_products
from unittest.mock import patch

class TestCoreLogic(TestCase):
    """Test deterministic parts of core business logic"""

    def set_up(self):
        """Set up test data"""
        self.client = Client.objects.create(
            name="Test Client",
            slug="test-client",
            description="Test description"
        )

    def test_merge_related_products_basic(self):
        """Test basic product merging functionality"""
        existing = [{"id": 10, "name": "old"}, {"id": 11, "name": "keep"}]
        new_ref = {"id": 10, "name": "new"}

        result = merge_related_products(existing, new_ref)

        expected = [new_ref, {"id": 11, "name": "keep"}]
        self.assertEqual(result, expected)

    def test_merge_related_products_deduplication(self):
        """Test product deduplication with different ID formats"""
        existing = [10, "10", {"id": "10", "name": "old"}, {"id": 12}]
        new_ref = {"id": 10, "name": "new"}

        result = merge_related_products(existing, new_ref)

        expected = [new_ref, {"id": 12}]
        self.assertEqual(result, expected)

    def test_remove_related_product_by_id(self):
        """Test product removal by ID"""
        from core.services.product_relations import remove_related_product

        existing = [{"id": "10", "name": "a"}, 11, {"id": 12, "name": "b"}]
        result = remove_related_product(existing, 10)

        expected = [11, {"id": 12, "name": "b"}]
        self.assertEqual(result, expected)

    @patch('core.ai_generator_base.OpenRouterGenerator.generate_post_text')
    def test_generate_post_content_deterministic_parts(self, mock_generate):
        """Test deterministic parts of post content generation"""
        # Mock the LLM call to return predictable results
        mock_generate.return_value = {
            'text': 'Generated post content',
            'title': 'Generated Title',
            'hashtags': ['#test', '#content']
        }

        # Test that the function calls the generator with correct parameters
        post = Post.objects.create(
            client=self.client,
            title="Test Post",
            text="Original text"
        )

        result = generate_post_content(post)

        # Verify the generator was called with the post
        mock_generate.assert_called_once()
        self.assertIn('text', result)
        self.assertIn('title', result)
        self.assertIn('hashtags', result)

class TestContentGenerationLogic(TestCase):
    """Test content generation algorithms (deterministic parts)"""

    def test_compose_post_text_with_title_and_body(self):
        """Test post text composition with both title and body"""
        from core.tasks.publishing import _compose_post_text
        from types import SimpleNamespace

        post = SimpleNamespace(
            title="Headline",
            text="Body text",
            publish_text=True
        )

        result = _compose_post_text(post)
        expected = "Headline\n\nBody text"
        self.assertEqual(result, expected)

    def test_compose_post_text_title_only(self):
        """Test post text composition with title only"""
        from core.tasks.publishing import _compose_post_text
        from types import SimpleNamespace

        post = SimpleNamespace(
            title="Headline",
            text="   ",
            publish_text=True
        )

        result = _compose_post_text(post)
        expected = "Headline"
        self.assertEqual(result, expected)

    def test_compose_post_text_respects_publish_flag(self):
        """Test that publish_text flag is respected"""
        from core.tasks.publishing import _compose_post_text
        from types import SimpleNamespace

        post = SimpleNamespace(
            title="Headline",
            text="Body text",
            publish_text=False
        )

        result = _compose_post_text(post)
        expected = ""
        self.assertEqual(result, expected)
