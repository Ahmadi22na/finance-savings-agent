"""
سلوك المصادقة الثابت: أي طلب بدون توكن صالح = 401 + WWW-Authenticate، بغض النظر عن إصدار FastAPI
(الإصدارات القديمة كانت ترجّع 403 للتوكن المفقود).
"""
import pytest

PROTECTED = [
    ("GET", "/api/v1/users/me"),
    ("GET", "/api/v1/goals"),
    ("GET", "/api/v1/transactions"),
    ("POST", "/api/v1/agent/chat"),
    ("DELETE", "/api/v1/users/me"),
]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_missing_token_is_401_with_challenge_header(client, method, path):
    response = client.request(method, path, json={} if method != "GET" else None)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic dXNlcjpwYXNz", "Bearer", "Bearer not.a.jwt"])
def test_malformed_or_invalid_authorization_is_401(client, header):
    response = client.get("/api/v1/users/me", headers={"Authorization": header})
    assert response.status_code == 401


def test_public_endpoints_still_work_without_a_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/personas").status_code == 200
