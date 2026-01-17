import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
import factory
from factory.django import DjangoModelFactory
from faker import Faker

fake = Faker()

User = get_user_model()

@pytest.fixture
def api_client():
    """Create API client for testing"""
    return APIClient()

@pytest.fixture
def auth_client(user):
    """Create authenticated API client"""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client

@pytest.fixture
def admin_client(admin_user):
    """Create admin authenticated API client"""
    client = APIClient()
    refresh = RefreshToken.for_user(admin_user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client

@pytest.fixture
def user(db):
    """Create regular test user"""
    return User.objects.create_user(
        email=fake.email(),
        password='testpass123',
        first_name=fake.first_name(),
        last_name=fake.last_name()
    )

@pytest.fixture
def admin_user(db):
    """Create admin test user"""
    return User.objects.create_superuser(
        email='admin@test.com',
        password='adminpass123',
        first_name='Admin',
        last_name='User'
    )

@pytest.fixture
def auth_headers(user):
    """Create authentication headers for API requests"""
    refresh = RefreshToken.for_user(user)
    return {
        'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'
    }

@pytest.fixture
def admin_auth_headers(admin_user):
    """Create admin authentication headers for API requests"""
    refresh = RefreshToken.for_user(admin_user)
    return {
        'HTTP_AUTHORIZATION': f'Bearer {refresh.access_token}'
    }

# Factory for creating test users
class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.LazyAttribute(lambda x: fake.email())
    first_name = factory.LazyAttribute(lambda x: fake.first_name())
    last_name = factory.LazyAttribute(lambda x: fake.last_name())
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True

@pytest.fixture
def user_factory():
    """Factory fixture for creating test users"""
    return UserFactory

@pytest.fixture
def auth_headers_for_user(user):
    """Create auth headers for a specific user"""
    refresh = RefreshToken.for_user(user)
    return {
        'Authorization': f'Bearer {refresh.access_token}'
    }
