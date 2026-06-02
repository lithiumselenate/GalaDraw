def test_prize_draw_and_result_export_flow(client, module):
    client.post(
        "/employees",
        data={
            "employee_no": "E001",
            "name": "Alice",
            "department": "Engineering",
            "eligible": "on",
        },
    )
    client.post(
        "/employees",
        data={
            "employee_no": "E002",
            "name": "Bob",
            "department": "Sales",
            "eligible": "on",
        },
    )
    prize_response = client.post(
        "/prizes",
        data={"name": "First Prize", "level": "1", "winner_count": "1"},
        follow_redirects=False,
    )

    with module.app.app_context():
        prize = module.Prize.query.filter_by(name="First Prize").one()

    draw_response = client.post(
        "/draw",
        data={"prize_id": str(prize.id), "request_id": "fixed-request-id"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    duplicate_response = client.post(
        "/draw",
        data={"prize_id": str(prize.id), "request_id": "fixed-request-id"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    results_response = client.get("/results")
    export_response = client.get("/results/export.csv")

    with module.app.app_context():
        sessions = module.DrawSession.query.all()
        results = module.DrawResult.query.all()
        eligible_count = module.Employee.query.filter_by(eligible=True).count()

    assert prize_response.status_code == 302
    assert draw_response.status_code == 200
    assert duplicate_response.status_code == 200
    assert draw_response.json["ok"] is True
    assert duplicate_response.json["winners"] == draw_response.json["winners"]
    assert len(sessions) == 1
    assert len(results) == 1
    assert eligible_count == 1
    assert results_response.status_code == 200
    assert export_response.status_code == 200
    assert "First Prize" in export_response.get_data(as_text=True)


def test_draw_page_renders_after_disabling_roll_animation(client):
    response = client.post(
        "/settings/draw",
        data={"roll_names": "0", "auto_disable_winners": "0"},
        follow_redirects=False,
    )
    page_response = client.get("/draw")

    assert response.status_code == 302
    assert page_response.status_code == 200
