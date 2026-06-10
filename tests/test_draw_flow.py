from io import BytesIO


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
    assert export_response.get_data().startswith(b"\xef\xbb\xbf")
    assert "First Prize" in export_response.get_data(as_text=True)


def test_draw_page_renders_after_disabling_roll_animation(client):
    response = client.post(
        "/settings/draw",
        data={
            "roll_names": "0",
            "auto_disable_winners": "0",
            "countdown_seconds": "5",
        },
        follow_redirects=False,
    )
    page_response = client.get("/draw")

    assert response.status_code == 302
    assert page_response.status_code == 200


def test_draw_countdown_defaults_to_five_and_can_be_configured(client):
    default_response = client.get("/draw")
    update_response = client.post(
        "/settings/draw",
        data={
            "roll_names": "1",
            "auto_disable_winners": "1",
            "countdown_seconds": "7",
        },
        follow_redirects=False,
    )
    updated_response = client.get("/draw")

    assert 'data-seconds="5"' in default_response.get_data(as_text=True)
    assert update_response.status_code == 302
    assert 'data-seconds="7"' in updated_response.get_data(as_text=True)


def test_export_and_import_prize_config(client, module):
    client.post(
        "/prizes",
        data={"name": "First Prize", "level": "1", "winner_count": "1"},
    )

    export_response = client.get("/prizes/export.csv")

    with module.app.app_context():
        existing = module.Prize.query.filter_by(name="First Prize").one()
        existing_id = existing.id

    upload = BytesIO(
        (
            "id,name,level,winner_count,active\n"
            f"{existing_id},First Prize,1,2,0\n"
            ",Second Prize,2,3,1\n"
        ).encode("utf-8")
    )
    import_response = client.post(
        "/prizes/import",
        data={"file": (upload, "prizes.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    with module.app.app_context():
        prizes = module.Prize.query.order_by(module.Prize.level).all()

    assert export_response.status_code == 200
    assert export_response.mimetype == "text/csv"
    assert export_response.get_data().startswith(b"\xef\xbb\xbf")
    assert "First Prize" in export_response.get_data(as_text=True)
    assert import_response.status_code == 302
    assert [(item.name, item.level, item.winner_count, item.active) for item in prizes] == [
        ("First Prize", 1, 2, False),
        ("Second Prize", 2, 3, True),
    ]


def test_update_prize_winner_count(client, module):
    client.post(
        "/prizes",
        data={"name": "First Prize", "level": "1", "winner_count": "1"},
    )

    with module.app.app_context():
        prize = module.Prize.query.filter_by(name="First Prize").one()
        prize_id = prize.id

    response = client.post(
        f"/prizes/{prize_id}/winner-count",
        data={"winner_count": "4"},
        follow_redirects=False,
    )

    with module.app.app_context():
        updated_prize = module.db.session.get(module.Prize, prize_id)

    assert response.status_code == 302
    assert updated_prize.winner_count == 4


def test_prize_config_csv_headers_follow_language_and_import_chinese_headers(
    client,
    module,
):
    client.post(
        "/prizes",
        data={"name": "一等奖", "level": "1", "winner_count": "1"},
    )

    with module.app.app_context():
        module.set_language("en")
        module.db.session.commit()
    english_export = client.get("/prizes/export.csv").get_data().decode("utf-8-sig")

    with module.app.app_context():
        module.set_language("zh")
        module.db.session.commit()
        existing = module.Prize.query.filter_by(name="一等奖").one()
        existing_id = existing.id
    chinese_export = client.get("/prizes/export.csv").get_data().decode("utf-8-sig")

    upload = BytesIO(
        (
            "ID,奖项名称,奖项等级,中奖人数,状态\n"
            f"{existing_id},一等奖,1,2,否\n"
            ",二等奖,2,3,可抽取\n"
        ).encode("utf-8")
    )
    response = client.post(
        "/prizes/import",
        data={"file": (upload, "prizes-zh.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    with module.app.app_context():
        prizes = module.Prize.query.order_by(module.Prize.level).all()

    assert english_export.startswith("id,name,level,winner_count,active")
    assert chinese_export.startswith("id,奖项名称,奖项等级,中奖人数,可抽取")
    assert response.status_code == 302
    assert [(item.name, item.level, item.winner_count, item.active) for item in prizes] == [
        ("一等奖", 1, 2, False),
        ("二等奖", 2, 3, True),
    ]


def test_result_export_headers_follow_language(client, module):
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
        "/prizes",
        data={"name": "First Prize", "level": "1", "winner_count": "1"},
    )

    with module.app.app_context():
        prize = module.Prize.query.filter_by(name="First Prize").one()

    client.post(
        "/draw",
        data={"prize_id": str(prize.id), "request_id": "result-header-request"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )

    with module.app.app_context():
        module.set_language("en")
        module.db.session.commit()
    english_export = client.get("/results/export.csv").get_data().decode("utf-8-sig")

    with module.app.app_context():
        module.set_language("zh")
        module.db.session.commit()
    chinese_export = client.get("/results/export.csv").get_data().decode("utf-8-sig")

    assert english_export.startswith("prize,employee_no,name,department,status,draw_time")
    assert chinese_export.startswith("奖项,员工编号,姓名,部门,状态,抽奖时间")


def test_winner_can_waive_prize_and_redraw_replacement(client, module):
    for employee_no, name in (
        ("E001", "Alice"),
        ("E002", "Bob"),
        ("E003", "Carol"),
    ):
        client.post(
            "/employees",
            data={
                "employee_no": employee_no,
                "name": name,
                "department": "Team",
                "eligible": "on",
            },
        )
    client.post(
        "/prizes",
        data={"name": "First Prize", "level": "1", "winner_count": "1"},
    )

    with module.app.app_context():
        prize = module.Prize.query.filter_by(name="First Prize").one()

    client.post(
        "/draw",
        data={"prize_id": str(prize.id), "request_id": "waive-redraw-request"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )

    with module.app.app_context():
        original = module.DrawResult.query.filter_by(status="active").one()
        original_employee_id = original.employee_id
        original_result_id = original.id

    response = client.post(
        f"/draw/results/{original_result_id}/redraw",
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
        follow_redirects=False,
    )

    with module.app.app_context():
        results = module.DrawResult.query.order_by(module.DrawResult.id).all()
        original_employee = module.db.session.get(module.Employee, original_employee_id)
        active_results = [item for item in results if item.status == "active"]
        waived_results = [item for item in results if item.status == "waived"]

    assert response.status_code == 200
    assert response.json["ok"] is True
    assert response.json["old_winner"]["name"] in {"Alice", "Bob", "Carol"}
    assert response.json["new_winner"]["name"] in {"Alice", "Bob", "Carol"}
    assert response.json["old_winner"]["name"] != response.json["new_winner"]["name"]
    assert response.json["old_winner"]["name"] not in response.json["candidates"]
    assert response.json["new_winner"]["name"] in response.json["candidates"]
    assert "/draw/sessions/" in response.json["session_url"]
    assert len(results) == 2
    assert len(active_results) == 1
    assert len(waived_results) == 1
    assert waived_results[0].employee_id == original_employee_id
    assert waived_results[0].waived_at is not None
    assert active_results[0].employee_id != original_employee_id
    assert original_employee.eligible is True
