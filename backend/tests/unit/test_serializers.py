import pytest
from django.test import TestCase
from api.serializers import (
    PostSerializer,
    PostDetailSerializer,
    ClientProductSerializer,
    ClientSettingsSerializer
)
from django.contrib.auth import get_user_model
from core.models import Post, Client, ClientProduct
from datetime import datetime

User = get_user_model()

class TestUserSerializer(TestCase):
    """Test User serializer validation and behavior"""

    def setUp(self):
        self.valid_data = {
            'email': 'test@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123'
        }

        self.invalid_data = {
            'email': 'invalid-email',
            'first_name': '',  # Empty first name
            'last_name': 'User',
            'password': 'short'
        }

    def test_valid_user_serialization(self):
        """Test serialization of valid user data"""
        serializer = UserSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

        user = serializer.save()
        self.assertEqual(user.email, self.valid_data['email'])
        self.assertEqual(user.first_name, self.valid_data['first_name'])
        self.assertEqual(user.last_name, self.valid_data['last_name'])
        self.assertTrue(user.check_password(self.valid_data['password']))

    def test_invalid_email_format(self):
        """Test that invalid email format is rejected"""
        serializer = UserSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)

    def test_empty_first_name(self):
        """Test that empty first name is rejected"""
        serializer = UserSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('first_name', serializer.errors)

    def test_short_password(self):
        """Test that short passwords are rejected"""
        serializer = UserSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_user_serializer_fields(self):
        """Test that user serializer contains expected fields"""
        serializer = UserSerializer()
        expected_fields = ['id', 'email', 'first_name', 'last_name', 'is_active', 'date_joined']
        for field in expected_fields:
            self.assertIn(field, serializer.fields)

class TestPostSerializer(TestCase):
    """Test Post serializer validation and behavior"""

    def setUp(self):
        self.client = Client.objects.create(
            name="Test Client",
            slug="test-client"
        )

        self.valid_data = {
            'client': self.client.id,
            'title': 'Test Post',
            'text': 'This is a test post content',
            'status': 'draft',
            'scheduled_time': datetime.now().isoformat()
        }

        self.invalid_data = {
            'client': 999,  # Non-existent client
            'title': '',  # Empty title
            'text': 'Short',
            'status': 'invalid_status'
        }

    def test_valid_post_serialization(self):
        """Test serialization of valid post data"""
        serializer = PostSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

        post = serializer.save()
        self.assertEqual(post.title, self.valid_data['title'])
        self.assertEqual(post.text, self.valid_data['text'])
        self.assertEqual(post.client, self.client)

    def test_invalid_client_id(self):
        """Test that invalid client ID is rejected"""
        serializer = PostSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('client', serializer.errors)

    def test_empty_post_title(self):
        """Test that empty post title is rejected"""
        serializer = PostSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('title', serializer.errors)

    def test_invalid_post_status(self):
        """Test that invalid post status is rejected"""
        serializer = PostSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('status', serializer.errors)

    def test_post_serializer_relations(self):
        """Test that post serializer handles relations correctly"""
        serializer = PostSerializer()
        self.assertIn('client', serializer.fields)
        self.assertEqual(serializer.fields['client'].__class__.__name__, 'PrimaryKeyRelatedField')

class TestProductSerializer(TestCase):
    """Test Product serializer validation and behavior"""

    def setUp(self):
        self.client = Client.objects.create(
            name="Test Client",
            slug="test-client"
        )

        self.valid_data = {
            'client': self.client.id,
            'name': 'Test Product',
            'description': 'This is a test product',
            'price': 99.99,
            'category': 'test_category'
        }

        self.invalid_data = {
            'client': 999,  # Non-existent client
            'name': '',  # Empty name
            'description': 'Short',
            'price': -10.00,  # Negative price
            'category': 'a' * 101  # Too long category
        }

    def test_valid_product_serialization(self):
        """Test serialization of valid product data"""
        serializer = ProductSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())

        product = serializer.save()
        self.assertEqual(product.name, self.valid_data['name'])
        self.assertEqual(product.price, self.valid_data['price'])
        self.assertEqual(product.client, self.client)

    def test_invalid_product_price(self):
        """Test that invalid product price is rejected"""
        serializer = ProductSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('price', serializer.errors)

    def test_empty_product_name(self):
        """Test that empty product name is rejected"""
        serializer = ProductSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)

    def test_product_category_length(self):
        """Test that product category length is validated"""
        serializer = ProductSerializer(data=self.invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('category', serializer.errors)
