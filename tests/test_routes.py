def test_public_admin_pages_render_when_auth_is_disabled(client):
    for path in ("/", "/employees", "/prizes", "/draw", "/results", "/settings"):
        response = client.get(path)

        assert response.status_code == 200, path


def test_auth_only_pages_redirect_when_auth_is_disabled(client):
    for path in ("/login", "/register", "/account", "/accounts", "/checkin"):
        response = client.get(path, follow_redirects=False)

        assert response.status_code == 302, path
        assert response.headers["Location"].endswith("/")
