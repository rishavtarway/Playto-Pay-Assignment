"""Shared test fixtures for the KYC app."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def merchant_a(db):
    user = User.objects.create_user(
        username="merchant_a",
        email="merchant_a@test.com",
        password="pw123456",
        role=User.ROLE_MERCHANT,
    )
    return user


@pytest.fixture
def merchant_b(db):
    return User.objects.create_user(
        username="merchant_b",
        email="merchant_b@test.com",
        password="pw123456",
        role=User.ROLE_MERCHANT,
    )


@pytest.fixture
def reviewer(db):
    return User.objects.create_user(
        username="reviewer1",
        email="reviewer1@test.com",
        password="pw123456",
        role=User.ROLE_REVIEWER,
    )


@pytest.fixture
def merchant_a_token(merchant_a):
    return Token.objects.create(user=merchant_a).key


@pytest.fixture
def merchant_b_token(merchant_b):
    return Token.objects.create(user=merchant_b).key


@pytest.fixture
def reviewer_token(reviewer):
    return Token.objects.create(user=reviewer).key
