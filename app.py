import csv
import hashlib
import hmac
import os
import random
import uuid
from datetime import datetime
from io import StringIO

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text


db = SQLAlchemy()
ADMIN_USERNAME = "superadmin"
ADMIN_PASSWORD_SHA256 = "029b4fd16334ffa44e18d81e00de1e95e2467e66d00b4e043674861f6908234f"


def password_matches(password):
    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(password_hash, ADMIN_PASSWORD_SHA256)


def safe_next_url(next_url):
    if not next_url or next_url.startswith("//"):
        return url_for("index")
    if next_url.startswith("/") and not next_url.startswith("/login"):
        return next_url
    return url_for("index")


def get_bool_setting(name, default=True):
    saved_setting = AppSetting.query.filter_by(name=name).first()
    raw_value = saved_setting.value if saved_setting else os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() not in {"0", "false", "no", "off"}


def get_int_setting(name, default, minimum, maximum):
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def get_draw_settings():
    return {
        "roll_names": get_bool_setting("DRAW_ROLL_NAMES", True),
        "auto_disable_winners": get_bool_setting("DRAW_AUTO_DISABLE_WINNERS", True),
        "countdown": get_bool_setting("DRAW_COUNTDOWN", True),
        "countdown_seconds": get_int_setting("DRAW_COUNTDOWN_SECONDS", 3, 1, 10),
    }


def set_bool_setting(name, enabled):
    setting = AppSetting.query.filter_by(name=name).first()
    if setting is None:
        setting = AppSetting(name=name)
        db.session.add(setting)
    setting.value = "1" if enabled else "0"


class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_no = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120), default="")
    eligible = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Prize(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    winner_count = db.Column(db.Integer, default=1, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(120), nullable=False)


class DrawSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.String(64), unique=True, nullable=False)
    prize_id = db.Column(db.Integer, db.ForeignKey("prize.id"), nullable=False)
    count = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    prize = db.relationship("Prize")
    results = db.relationship(
        "DrawResult",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DrawResult.id",
    )


class DrawResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("draw_session.id"), nullable=False)
    prize_id = db.Column(db.Integer, db.ForeignKey("prize.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    session = db.relationship("DrawSession", back_populates="results")
    prize = db.relationship("Prize")
    employee = db.relationship("Employee")


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///gala_draw.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        migrate_draw_result_duplicate_winners()
        migrate_prize_active_column()

    register_routes(app)
    return app


def migrate_prize_active_column():
    if not db.engine.url.drivername.startswith("sqlite"):
        return

    columns = db.session.execute(text("PRAGMA table_info(prize)")).mappings().all()
    if any(column["name"] == "active" for column in columns):
        return

    db.session.execute(
        text("ALTER TABLE prize ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1")
    )
    db.session.commit()


def migrate_draw_result_duplicate_winners():
    if not db.engine.url.drivername.startswith("sqlite"):
        return

    indexes = db.session.execute(text("PRAGMA index_list(draw_result)")).mappings().all()
    has_employee_unique = False
    for index in indexes:
        if not index["unique"]:
            continue
        columns = db.session.execute(
            text(f"PRAGMA index_info({index['name']!r})")
        ).mappings().all()
        if [column["name"] for column in columns] == ["employee_id"]:
            has_employee_unique = True
            break

    if not has_employee_unique:
        return

    db.session.execute(text("PRAGMA foreign_keys=off"))
    db.session.execute(text("ALTER TABLE draw_result RENAME TO draw_result_old"))
    db.session.execute(
        text(
            """
            CREATE TABLE draw_result (
                id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                prize_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL,
                PRIMARY KEY (id),
                FOREIGN KEY(session_id) REFERENCES draw_session (id),
                FOREIGN KEY(prize_id) REFERENCES prize (id),
                FOREIGN KEY(employee_id) REFERENCES employee (id)
            )
            """
        )
    )
    db.session.execute(
        text(
            """
            INSERT INTO draw_result (id, session_id, prize_id, employee_id, created_at)
            SELECT id, session_id, prize_id, employee_id, created_at
            FROM draw_result_old
            """
        )
    )
    db.session.execute(text("DROP TABLE draw_result_old"))
    db.session.execute(text("PRAGMA foreign_keys=on"))
    db.session.commit()


def register_routes(app):
    @app.before_request
    def require_login():
        public_endpoints = {"login", "login_submit", "static"}
        if request.endpoint in public_endpoints:
            return None
        if session.get("admin_user") == ADMIN_USERNAME:
            return None
        return redirect(url_for("login", next=request.full_path))

    @app.get("/login")
    def login():
        if session.get("admin_user") == ADMIN_USERNAME:
            return redirect(url_for("index"))
        return render_template("login.html")

    @app.post("/login")
    def login_submit():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = safe_next_url(request.args.get("next"))
        if username == ADMIN_USERNAME and password_matches(password):
            session.clear()
            session["admin_user"] = ADMIN_USERNAME
            flash("登录成功。", "success")
            return redirect(next_url)

        flash("用户名或密码不正确。", "error")
        return redirect(url_for("login", next=next_url))

    @app.post("/logout")
    def logout():
        session.clear()
        flash("已退出登录。", "success")
        return redirect(url_for("login"))

    @app.get("/")
    def index():
        stats = {
            "employees": Employee.query.count(),
            "eligible": Employee.query.filter_by(eligible=True).count(),
            "prizes": Prize.query.count(),
            "winners": DrawResult.query.count(),
        }
        recent_results = (
            DrawResult.query.order_by(DrawResult.created_at.desc()).limit(8).all()
        )
        return render_template("index.html", stats=stats, recent_results=recent_results)

    @app.get("/employees")
    def employees():
        page = request.args.get("page", 1, type=int)
        search = request.args.get("q", "").strip()
        query = Employee.query
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Employee.employee_no.ilike(pattern),
                    Employee.name.ilike(pattern),
                )
            )
        pagination = query.order_by(Employee.department, Employee.employee_no).paginate(
            page=page,
            per_page=30,
            error_out=False,
        )
        return render_template(
            "employees.html",
            employees=pagination.items,
            pagination=pagination,
            search=search,
        )

    @app.post("/employees")
    def add_employee():
        employee_no = request.form.get("employee_no", "").strip()
        name = request.form.get("name", "").strip()
        department = request.form.get("department", "").strip()
        eligible = request.form.get("eligible") == "on"
        if not employee_no or not name:
            flash("请填写员工编号和姓名。", "error")
            return redirect(url_for("employees"))

        db.session.add(
            Employee(
                employee_no=employee_no,
                name=name,
                department=department,
                eligible=eligible,
            )
        )
        try:
            db.session.commit()
            flash("员工已新增。", "success")
        except Exception:
            db.session.rollback()
            flash("员工编号已存在。", "error")
        return redirect(url_for("employees"))

    @app.post("/employees/import")
    def import_employees():
        upload = request.files.get("file")
        if not upload:
            flash("请选择 CSV 文件。", "error")
            return redirect(url_for("employees"))

        text = upload.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(StringIO(text))
        added = 0
        for row in reader:
            employee_no = (row.get("employee_no") or row.get("number") or "").strip()
            name = (row.get("name") or "").strip()
            department = (row.get("department") or "").strip()
            if not employee_no or not name:
                continue
            exists = Employee.query.filter_by(employee_no=employee_no).first()
            if exists:
                exists.name = name
                exists.department = department
                exists.eligible = True
            else:
                db.session.add(
                    Employee(
                        employee_no=employee_no,
                        name=name,
                        department=department,
                        eligible=True,
                    )
                )
                added += 1
        db.session.commit()
        flash(f"导入完成，新增 {added} 位员工。", "success")
        return redirect(url_for("employees"))

    @app.post("/employees/<int:employee_id>/eligibility")
    def update_employee_eligibility(employee_id):
        employee = Employee.query.get_or_404(employee_id)
        employee.eligible = request.form.get("eligible") == "1"
        db.session.commit()
        flash(
            f"{employee.name} 已设为{'可参与' if employee.eligible else '不可参与'}。",
            "success",
        )
        return redirect(url_for("employees"))

    @app.post("/employees/enable-all")
    def enable_all_employees():
        updated = Employee.query.filter_by(eligible=False).update(
            {"eligible": True},
            synchronize_session=False,
        )
        db.session.commit()
        flash(f"已将 {updated} 位员工设为可参与抽奖。", "success")
        return redirect(url_for("employees"))

    @app.get("/prizes")
    def prizes():
        rows = Prize.query.order_by(Prize.level, Prize.id).all()
        return render_template(
            "prizes.html",
            prizes=rows,
            settings=get_draw_settings(),
        )

    @app.post("/prizes")
    def add_prize():
        name = request.form.get("name", "").strip()
        level = int(request.form.get("level", "1"))
        winner_count = int(request.form.get("winner_count", "1"))
        if not name:
            flash("请填写奖项名称。", "error")
            return redirect(url_for("prizes"))

        db.session.add(
            Prize(
                name=name,
                level=level,
                winner_count=winner_count,
            )
        )
        db.session.commit()
        flash("奖项已新增。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/reset")
    def reset_prizes():
        DrawResult.query.delete()
        DrawSession.query.delete()
        Prize.query.delete()
        db.session.commit()
        flash("所有奖项和抽奖结果已重设。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/<int:prize_id>/remove")
    def remove_prize(prize_id):
        prize = Prize.query.get_or_404(prize_id)
        prize.active = False
        db.session.commit()
        flash(f"{prize.name} 已从后续抽奖中移除，历史结果已保留。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/<int:prize_id>/restore")
    def restore_prize(prize_id):
        prize = Prize.query.get_or_404(prize_id)
        prize.active = True
        db.session.commit()
        flash(f"{prize.name} 已恢复到抽奖列表。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/<int:prize_id>/delete")
    def delete_prize(prize_id):
        prize = Prize.query.get_or_404(prize_id)
        prize_name = prize.name
        DrawResult.query.filter_by(prize_id=prize.id).delete()
        DrawSession.query.filter_by(prize_id=prize.id).delete()
        db.session.delete(prize)
        db.session.commit()
        flash(f"{prize_name} 已删除，关联抽奖结果也已清理。", "success")
        return redirect(url_for("prizes"))

    @app.post("/settings/draw")
    def update_draw_settings():
        roll_names = request.form.get("roll_names") == "1"
        auto_disable_winners = request.form.get("auto_disable_winners") == "1"
        set_bool_setting("DRAW_ROLL_NAMES", roll_names)
        set_bool_setting("DRAW_AUTO_DISABLE_WINNERS", auto_disable_winners)
        db.session.commit()
        flash("抽奖设置已更新。", "success")
        return redirect(url_for("prizes"))

    @app.post("/employees/reset")
    def reset_employees():
        confirmation = request.form.get("confirmation", "").strip()
        if confirmation != "清空员工":
            flash("员工重置已取消。请输入“清空员工”进行确认。", "error")
            return redirect(url_for("employees"))

        DrawResult.query.delete()
        DrawSession.query.delete()
        Employee.query.delete()
        db.session.commit()
        flash("所有员工信息和抽奖结果已重置。", "success")
        return redirect(url_for("employees"))

    @app.get("/draw")
    def draw_page():
        prizes = Prize.query.filter_by(active=True).order_by(Prize.level, Prize.id).all()
        candidates = (
            Employee.query.filter_by(eligible=True)
            .order_by(Employee.department, Employee.employee_no)
            .all()
        )
        selected_prize = prizes[0] if prizes else None
        selected_prize_id = request.args.get("prize_id", type=int)
        if selected_prize_id:
            selected_prize = next(
                (prize for prize in prizes if prize.id == selected_prize_id),
                selected_prize,
            )
        slot_count = selected_prize.winner_count if selected_prize else 0
        return render_template(
            "draw.html",
            prizes=prizes,
            candidates=candidates,
            selected_prize=selected_prize,
            slot_count=slot_count,
            settings=get_draw_settings(),
        )

    @app.get("/draw/sessions/<int:session_id>")
    def draw_session_result(session_id):
        session = DrawSession.query.get_or_404(session_id)
        return render_template(
            "draw_result.html",
            session=session,
            show_animation=False,
        )

    @app.post("/draw")
    def draw():
        prize_id = int(request.form.get("prize_id", "0"))
        request_id = request.form.get("request_id") or str(uuid.uuid4())
        settings = get_draw_settings()
        prize = Prize.query.get_or_404(prize_id)
        wants_json = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or request.accept_mimetypes.best == "application/json"
        )

        if not prize.active:
            flash("该奖项已被移除，请重新选择奖项。", "error")
            if wants_json:
                return jsonify({"ok": False, "redirect_url": url_for("draw_page")}), 400
            return redirect(url_for("draw_page"))

        def draw_response(session):
            if wants_json:
                return jsonify(
                    {
                        "ok": True,
                        "winners": [
                            result.employee.name for result in session.results
                        ],
                        "result_url": url_for(
                            "draw_session_result",
                            session_id=session.id,
                        ),
                    }
                )
            return render_template(
                "draw_result.html",
                session=session,
                show_animation=settings["roll_names"],
            )

        previous = DrawSession.query.filter_by(request_id=request_id).first()
        if previous:
            return draw_response(previous)

        query = Employee.query.filter_by(eligible=True)

        candidates = query.all()
        count = min(prize.winner_count, len(candidates))
        if count <= 0:
            flash("当前没有可参与该奖项抽奖的员工。", "error")
            if wants_json:
                return jsonify({"ok": False, "redirect_url": url_for("draw_page")}), 400
            return redirect(url_for("draw_page"))

        winners = random.sample(candidates, count)
        session = DrawSession(request_id=request_id, prize_id=prize.id, count=count)
        db.session.add(session)
        db.session.flush()

        for employee in winners:
            db.session.add(
                DrawResult(
                    session_id=session.id,
                    prize_id=prize.id,
                    employee_id=employee.id,
                )
            )
            if settings["auto_disable_winners"]:
                employee.eligible = False

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("抽奖失败，部分员工可能已被抽中过。", "error")
            if wants_json:
                return jsonify({"ok": False, "redirect_url": url_for("draw_page")}), 409
            return redirect(url_for("draw_page"))

        return draw_response(session)

    @app.get("/results")
    def results():
        rows = DrawResult.query.order_by(DrawResult.created_at.desc()).all()
        return render_template("results.html", results=rows)

    @app.get("/results/export.csv")
    def export_results():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["prize", "employee_no", "name", "department", "drawn_at"])
        for result in DrawResult.query.order_by(DrawResult.created_at).all():
            writer.writerow(
                [
                    result.prize.name,
                    result.employee.employee_no,
                    result.employee.name,
                    result.employee.department,
                    result.created_at.isoformat(),
                ]
            )
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=draw_results.csv"},
        )

    @app.post("/reset-results")
    def reset_results():
        DrawResult.query.delete()
        DrawSession.query.delete()
        db.session.commit()
        flash("所有抽奖结果已重置。", "success")
        return redirect(url_for("results"))


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
