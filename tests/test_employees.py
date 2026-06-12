from io import BytesIO


def test_create_update_and_export_employee(client, module):
    create_response = client.post(
        "/employees",
        data={
            "employee_no": "E001",
            "name": "Alice",
            "department": "Engineering",
            "eligible": "on",
        },
        follow_redirects=False,
    )

    with module.app.app_context():
        employee = module.Employee.query.filter_by(employee_no="E001").one()
        employee_id = employee.id

    update_response = client.post(
        f"/employees/{employee_id}/eligibility",
        data={"eligible": "0"},
        follow_redirects=False,
    )
    export_response = client.get("/employees/export.csv")

    with module.app.app_context():
        employee = module.Employee.query.filter_by(employee_no="E001").one()

    assert create_response.status_code == 302
    assert update_response.status_code == 302
    assert employee.eligible is False
    assert export_response.status_code == 200
    assert export_response.mimetype == "text/csv"
    assert export_response.get_data().startswith(b"\xef\xbb\xbf")
    assert "Alice" in export_response.get_data(as_text=True)


def test_update_employee_eligibility_ajax_returns_row_state(client, module):
    client.post(
        "/employees",
        data={
            "employee_no": "E001",
            "name": "Alice",
            "department": "Engineering",
            "eligible": "on",
        },
    )

    with module.app.app_context():
        employee = module.Employee.query.filter_by(employee_no="E001").one()
        employee_id = employee.id

    disable_response = client.post(
        f"/employees/{employee_id}/eligibility",
        data={"eligible": "0"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    enable_response = client.post(
        f"/employees/{employee_id}/eligibility",
        data={"eligible": "1"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )

    with module.app.app_context():
        updated_employee = module.db.session.get(module.Employee, employee_id)

    assert disable_response.status_code == 200
    assert disable_response.json["ok"] is True
    assert disable_response.json["eligible"] is False
    assert disable_response.json["next_value"] == "1"
    assert enable_response.status_code == 200
    assert enable_response.json["ok"] is True
    assert enable_response.json["eligible"] is True
    assert enable_response.json["next_value"] == "0"
    assert updated_employee.eligible is True


def test_import_employees_csv_creates_and_updates_rows(client, module):
    first_upload = BytesIO(
        b"employee_no,name,department\nE001,Alice,Engineering\nE002,Bob,Sales\n"
    )
    second_upload = BytesIO(b"employee_no,name,department\nE001,Alicia,Product\n")

    first_response = client.post(
        "/employees/import",
        data={"file": (first_upload, "employees.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    second_response = client.post(
        "/employees/import",
        data={"file": (second_upload, "employees.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    with module.app.app_context():
        employees = module.Employee.query.order_by(module.Employee.employee_no).all()

    assert first_response.status_code == 302
    assert second_response.status_code == 302
    assert [(item.employee_no, item.name, item.department) for item in employees] == [
        ("E001", "Alicia", "Product"),
        ("E002", "Bob", "Sales"),
    ]


def test_employee_csv_headers_follow_language_and_import_english_headers(
    client,
    module,
):
    client.post(
        "/employees",
        data={
            "employee_no": "E001",
            "name": "Alice",
            "department": "Engineering",
            "eligible": "on",
        },
    )

    with module.app.app_context():
        module.set_language("en")
        module.db.session.commit()
    english_export = client.get("/employees/export.csv").get_data().decode("utf-8-sig")

    with module.app.app_context():
        module.set_language("zh")
        module.db.session.commit()
    chinese_export = client.get("/employees/export.csv").get_data().decode("utf-8-sig")

    upload = BytesIO(
        (
            "Employee No.,Name,Department\n"
            "E001,Alicia,Product\n"
            "E002,Bob,Sales\n"
        ).encode("utf-8")
    )
    response = client.post(
        "/employees/import",
        data={"file": (upload, "employees-natural-headers.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    with module.app.app_context():
        employees = module.Employee.query.order_by(module.Employee.employee_no).all()

    assert english_export.startswith("employee_no,name,department,eligible,created_at")
    assert chinese_export.startswith("员工编号,姓名,部门,可参与抽奖,创建时间")
    assert response.status_code == 302
    assert [(item.employee_no, item.name, item.department) for item in employees] == [
        ("E001", "Alicia", "Product"),
        ("E002", "Bob", "Sales"),
    ]


def test_delete_employee_ajax_returns_success(client, module):
    client.post(
        "/employees",
        data={
            "employee_no": "E001",
            "name": "Alice",
            "department": "Engineering",
            "eligible": "on",
        },
    )

    with module.app.app_context():
        employee = module.Employee.query.filter_by(employee_no="E001").one()
        employee_id = employee.id

    response = client.post(
        f"/employees/{employee_id}/delete",
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )

    with module.app.app_context():
        deleted_employee = module.db.session.get(module.Employee, employee_id)

    assert response.status_code == 200
    assert response.json["ok"] is True
    assert deleted_employee is None


def test_delete_employee_cleans_related_records(client, module):
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
        employee = module.Employee.query.filter_by(employee_no="E001").one()
        prize = module.Prize.query.filter_by(name="First Prize").one()
        user = module.User(username="linked-user", role="user", status="active")
        user.set_password("password123")
        user.employee_id = employee.id
        module.db.session.add(user)
        module.db.session.flush()
        module.db.session.add(
            module.EmployeeLinkRequest(
                user_id=user.id,
                employee_id=employee.id,
                status="pending",
            )
        )
        module.db.session.commit()
        employee_id = employee.id
        prize_id = prize.id

    client.post(
        "/draw",
        data={"prize_id": str(prize_id), "request_id": "delete-employee-request"},
        headers={"X-Requested-With": "XMLHttpRequest", "Accept": "application/json"},
    )
    response = client.post(
        f"/employees/{employee_id}/delete",
        follow_redirects=False,
    )

    with module.app.app_context():
        linked_user = module.User.query.filter_by(username="linked-user").one()

        assert module.db.session.get(module.Employee, employee_id) is None
        assert module.DrawResult.query.count() == 0
        assert module.DrawSession.query.count() == 0
        assert module.EmployeeLinkRequest.query.count() == 0
        assert linked_user.employee_id is None

    assert response.status_code == 302
