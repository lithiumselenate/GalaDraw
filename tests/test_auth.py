def test_protected_page_redirects_to_login_when_auth_is_enabled(client, module):
    module.AUTH_ENABLED = True

    response = client.get("/employees", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_superadmin_can_log_in_and_reach_dashboard(
    client,
    module,
    login_as_superadmin,
):
    module.AUTH_ENABLED = True

    login_response = login_as_superadmin(client)
    dashboard_response = client.get("/")

    assert login_response.status_code == 302
    assert dashboard_response.status_code == 200


def test_pending_registered_user_cannot_log_in(client, module):
    module.AUTH_ENABLED = True

    client.post(
        "/register",
        data={"username": "pending-user", "password": "password123"},
    )
    response = client.post(
        "/login",
        data={"username": "pending-user", "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_admin_can_create_user_account_after_login(
    client,
    module,
    login_as_superadmin,
):
    module.AUTH_ENABLED = True
    login_as_superadmin(client)

    response = client.post(
        "/accounts",
        data={
            "username": "operator",
            "password": "password123",
            "role": "user",
            "status": "active",
        },
        follow_redirects=False,
    )

    with module.app.app_context():
        user = module.User.query.filter_by(username="operator").first()

    assert response.status_code == 302
    assert user is not None
    assert user.role == "user"
    assert user.status == "active"
