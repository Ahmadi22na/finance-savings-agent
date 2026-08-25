"""اختبارات تدفق التسجيل والدخول — تستخدم client من conftest.py المشترك."""


def test_register_creates_user_and_returns_tokens(client):
    response = client.post("/api/v1/auth/register", json={
        "name": "أحمد",
        "phone": "0790000000",
        "password": "strongpassword123",
        "income_type": "variable",
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["name"] == "أحمد"
    assert data["user"]["agent_name"] == "رشيد"


def test_register_duplicate_phone_fails(client):
    payload = {"name": "أحمد", "phone": "0790000001", "password": "strongpassword123"}
    client.post("/api/v1/auth/register", json=payload)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


def test_login_with_correct_credentials(client):
    client.post("/api/v1/auth/register", json={
        "name": "سارة", "phone": "0790000002", "password": "mypassword123",
    })
    response = client.post("/api/v1/auth/login", json={
        "phone": "0790000002", "password": "mypassword123",
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_wrong_password_fails(client):
    client.post("/api/v1/auth/register", json={
        "name": "سارة", "phone": "0790000003", "password": "mypassword123",
    })
    response = client.post("/api/v1/auth/login", json={
        "phone": "0790000003", "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_protected_route_requires_token(client):
    response = client.get("/api/v1/users/me")
    assert response.status_code in (401, 403)


def test_protected_route_with_valid_token(client):
    register_response = client.post("/api/v1/auth/register", json={
        "name": "ليلى", "phone": "0790000004", "password": "mypassword123",
    })
    token = register_response.json()["access_token"]
    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["phone"] == "0790000004"
