def test_public_admin_pages_render_when_auth_is_disabled(client):
    for path in ("/", "/employees", "/prizes", "/draw", "/results", "/settings"):
        response = client.get(path)

        assert response.status_code == 200, path


def test_auth_only_pages_redirect_when_auth_is_disabled(client):
    for path in ("/login", "/register", "/account", "/accounts", "/checkin"):
        response = client.get(path, follow_redirects=False)

        assert response.status_code == 302, path
        assert response.headers["Location"].endswith("/")


def test_draw_settings_are_on_settings_page_not_prizes_page(client, module):
    with module.app.app_context():
        module.set_language("en")
        module.db.session.commit()

    settings_response = client.get("/settings")
    prizes_response = client.get("/prizes")

    assert settings_response.status_code == 200
    assert prizes_response.status_code == 200
    assert "Draw Settings" in settings_response.get_data(as_text=True)
    assert "Draw Settings" not in prizes_response.get_data(as_text=True)


def test_favicon_link_is_omitted_when_no_favicon_exists(client, module, tmp_path):
    original_static_folder = module.app.static_folder
    module.app.static_folder = str(tmp_path)
    try:
        response = client.get("/")
    finally:
        module.app.static_folder = original_static_folder

    assert response.status_code == 200
    assert 'rel="icon"' not in response.get_data(as_text=True)


def test_favicon_png_is_linked_when_present(client, module, tmp_path):
    original_static_folder = module.app.static_folder
    module.app.static_folder = str(tmp_path)
    (tmp_path / "favicon.png").write_bytes(b"png")
    try:
        response = client.get("/")
    finally:
        module.app.static_folder = original_static_folder

    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'rel="icon"' in html
    assert "/static/favicon.png?v=" in html


def test_favicon_ico_takes_priority_over_png(client, module, tmp_path):
    original_static_folder = module.app.static_folder
    module.app.static_folder = str(tmp_path)
    (tmp_path / "favicon.ico").write_bytes(b"ico")
    (tmp_path / "favicon.png").write_bytes(b"png")
    try:
        response = client.get("/")
    finally:
        module.app.static_folder = original_static_folder

    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "/static/favicon.ico?v=" in html
    assert "/static/favicon.png?v=" not in html
