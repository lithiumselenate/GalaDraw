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
    assert "Alice" in export_response.get_data(as_text=True)


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
    english_export = client.get("/employees/export.csv").get_data(as_text=True)

    with module.app.app_context():
        module.set_language("zh")
        module.db.session.commit()
    chinese_export = client.get("/employees/export.csv").get_data(as_text=True)

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
