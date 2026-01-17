import pytest
from django.urls import reverse
from rest_framework import status

class TestAuthenticationAPI:
    """Test authentication API endpoints"""

    def test_user_registration(self, api_client):
        """Test user registration endpoint"""
        url = reverse('register')
        data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_201_CREATED
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_user_login(self, api_client, user):
        """Test user login endpoint"""
        url = reverse('login')
        data = {
            'email': user.email,
            'password': 'testpass123'
        }

        response = api_client.post(url, data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data
        assert 'refresh' in response.data

    def test_token_refresh(self, api_client, user):
        """Test token refresh endpoint"""
        # First get tokens
        login_url = reverse('login')
        login_data = {
            'email': user.email,
            'password': 'testpass123'
        }
        login_response = api_client.post(login_url, login_data, format='json')

        # Then refresh token
        refresh_url = reverse('token_refresh')
        refresh_data = {
            'refresh': login_response.data['refresh']
        }
        response = api_client.post(refresh_url, refresh_data, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert 'access' in response.data

    def test_protected_endpoint_unauthorized(self, api_client):
        """Test that protected endpoints require authentication"""
        # Use a protected endpoint URL
        url = reverse('client-info')  # Assuming this is a protected endpoint

        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_protected_endpoint_authorized(self, auth_client):
        """Test that protected endpoints work with authentication"""
        url = reverse('client-info')

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Add more assertions based on the expected response

class TestPermissionAPI:
    """Test permission and role-based access control"""

    def test_admin_access_to_admin_endpoints(self, admin_client):
        """Test that admin users can access admin-only endpoints"""
        # Use an admin-only endpoint URL
        url = reverse('admin-dashboard')  # Assuming this is an admin endpoint

        response = admin_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_regular_user_cannot_access_admin_endpoints(self, auth_client):
        """Test that regular users cannot access admin-only endpoints"""
        url = reverse('admin-dashboard')

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_can_access_own_resources(self, auth_client, user):
        """Test that users can access their own resources"""
        # This would test endpoints like /api/users/{id}/ where id is the current user
        url = reverse('user-detail', args=[user.id])

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == user.id

    def test_user_cannot_access_other_users_resources(self, auth_client, user_factory):
        """Test that users cannot access other users' resources"""
        other_user = user_factory()
        url = reverse('user-detail', args=[other_user.id])

        response = auth_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
