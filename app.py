import csv
import os
import random
import uuid
from datetime import datetime, timedelta
from functools import wraps
from io import StringIO

from flask import Flask, Response, flash, g, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()
ADMIN_USERNAME = "superadmin"
ADMIN_INITIAL_PASSWORD = "Changeme123!"
ROLES = ("superadmin", "admin", "user")
STATUSES = ("pending", "active", "disabled")
PERMISSIONS = {
    "account.create": "Create accounts",
    "account.delete": "Delete accounts",
    "account.disable": "Disable accounts",
    "account.role.update": "Change account roles",
    "account.permission.update": "Change role permissions",
    "account.self.employee.request": "Request employee binding",
    "account.employee.link.review": "Review employee binding requests",
    "account.employee.link.manage": "Manage employee bindings",
    "registration.review": "Review registrations",
    "dashboard.view": "View dashboard",
    "employee.view": "View employees",
    "employee.create": "Create employees",
    "employee.import": "Import employees",
    "employee.update": "Update employees",
    "employee.reset": "Reset employees",
    "prize.view": "View prizes",
    "prize.create": "Create prizes",
    "prize.update": "Update prizes",
    "prize.disable": "Disable prizes",
    "prize.delete": "Delete prizes",
    "prize.reset": "Reset prizes",
    "draw.configure": "Configure draw",
    "draw.execute": "Run draw",
    "draw.result.view": "View draw results",
    "draw.result.export": "Export draw results",
    "draw.result.reset": "Reset draw results",
    "checkin.self": "Check in",
    "checkin.view_all": "View all check-ins",
    "checkin.manage": "Manage check-ins",
}
DEFAULT_ROLE_PERMISSIONS = {
    "admin": {
        "dashboard.view",
        "registration.review",
        "employee.view",
        "employee.create",
        "employee.import",
        "employee.update",
        "employee.reset",
        "prize.view",
        "prize.create",
        "prize.update",
        "prize.disable",
        "prize.delete",
        "prize.reset",
        "draw.configure",
        "draw.execute",
        "draw.result.view",
        "draw.result.export",
        "draw.result.reset",
        "checkin.view_all",
        "checkin.manage",
        "checkin.self",
        "account.disable",
        "account.employee.link.review",
        "account.employee.link.manage",
    },
    "user": {"checkin.self", "account.self.employee.request"},
}


def safe_next_url(next_url):
    if not next_url or next_url.startswith("//"):
        return url_for("index")
    if next_url.startswith("/") and not next_url.startswith(("/login", "/logout")):
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


def china_day_bounds_utc():
    china_offset = timedelta(hours=8)
    today_in_china = (datetime.utcnow() + china_offset).date()
    start = datetime.combine(today_in_china, datetime.min.time()) - china_offset
    return start, start + timedelta(days=1)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="user", nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    approved_by = db.relationship("User", remote_side=[id])
    employee = db.relationship("Employee", foreign_keys=[employee_id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return self.status == "active"


class RolePermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    permission = db.Column(db.String(80), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("role", "permission", name="uq_role_permission"),
    )


class CheckIn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")


class EmployeeLinkRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    user = db.relationship("User", foreign_keys=[user_id])
    employee = db.relationship("Employee")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])


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
        migrate_user_employee_link_column()
        seed_auth_data()
        migrate_draw_result_duplicate_winners()
        migrate_prize_active_column()

    register_routes(app)
    return app


def migrate_user_employee_link_column():
    if not db.engine.url.drivername.startswith("sqlite"):
        return

    columns = db.session.execute(text("PRAGMA table_info(user)")).mappings().all()
    if not any(column["name"] == "employee_id" for column in columns):
        db.session.execute(text("ALTER TABLE user ADD COLUMN employee_id INTEGER"))

    indexes = db.session.execute(text("PRAGMA index_list(user)")).mappings().all()
    if not any(index["name"] == "uq_user_employee_id" for index in indexes):
        db.session.execute(
            text("CREATE UNIQUE INDEX uq_user_employee_id ON user (employee_id)")
        )
    db.session.commit()


def seed_auth_data():
    superadmin = User.query.filter_by(username=ADMIN_USERNAME).first()
    if superadmin is None:
        superadmin = User(
            username=ADMIN_USERNAME,
            role="superadmin",
            status="active",
            approved_at=datetime.utcnow(),
        )
        superadmin.set_password(ADMIN_INITIAL_PASSWORD)
        db.session.add(superadmin)
    else:
        superadmin.role = "superadmin"
        superadmin.status = "active"

    seed_marker = AppSetting.query.filter_by(
        name="AUTH_DEFAULT_PERMISSIONS_SEEDED",
    ).first()
    if seed_marker is None:
        for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
            for permission in permissions:
                existing = RolePermission.query.filter_by(
                    role=role,
                    permission=permission,
                ).first()
                if existing is None:
                    db.session.add(
                        RolePermission(
                            role=role,
                            permission=permission,
                            enabled=True,
                        )
                    )
        db.session.add(AppSetting(name="AUTH_DEFAULT_PERMISSIONS_SEEDED", value="1"))

    db.session.commit()


def role_permissions(role):
    rows = RolePermission.query.filter_by(role=role, enabled=True).all()
    return {row.permission for row in rows}


def has_permission(permission):
    user = getattr(g, "current_user", None)
    if user is None or not user.is_active:
        return False
    if user.role == "superadmin":
        return True
    return permission in role_permissions(user.role)


def has_any_permission(*permissions):
    return any(has_permission(permission) for permission in permissions)


def require_permission(permission):
    if has_permission(permission):
        return None
    flash("You do not have permission to access that page.", "error")
    if getattr(g, "current_user", None) and has_permission("checkin.self"):
        return redirect(url_for("checkin"))
    return redirect(url_for("login"))


def permission_required(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            denied = require_permission(permission)
            if denied:
                return denied
            return view(*args, **kwargs)

        return wrapped

    return decorator


def landing_url_for(user):
    if user.role == "superadmin" or has_permission("dashboard.view"):
        return url_for("index")
    if has_permission("account.disable"):
        return url_for("accounts")
    if has_permission("registration.review"):
        return url_for("registrations")
    if has_permission("account.employee.link.review"):
        return url_for("employee_link_requests")
    if has_permission("draw.execute"):
        return url_for("draw_page")
    if has_permission("employee.view"):
        return url_for("employees")
    if has_permission("prize.view"):
        return url_for("prizes")
    if has_permission("draw.result.view"):
        return url_for("results")
    if has_permission("checkin.self"):
        return url_for("checkin")
    return url_for("no_access")


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
        g.current_user = None
        user_id = session.get("user_id")
        if user_id:
            g.current_user = User.query.get(user_id)

        public_endpoints = {"login", "login_submit", "register", "register_submit", "static"}
        if request.endpoint in public_endpoints:
            return None
        if g.current_user and g.current_user.is_active:
            return None
        return redirect(url_for("login", next=request.full_path))

    @app.get("/login")
    def login():
        if g.current_user and g.current_user.is_active:
            return redirect(landing_url_for(g.current_user))
        return render_template("login.html")

    @app.get("/register")
    def register():
        if g.current_user and g.current_user.is_active:
            return redirect(landing_url_for(g.current_user))
        return render_template("register.html")

    @app.post("/register")
    def register_submit():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("Please enter a username and password.", "error")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("That username is already registered.", "error")
            return redirect(url_for("register"))

        user = User(username=username, role="user", status="pending")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Registration submitted. Please wait for approval.", "success")
        return redirect(url_for("login"))

    @app.post("/login")
    def login_submit():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        next_url = safe_next_url(request.args.get("next"))
        user = User.query.filter_by(username=username).first()
        if user and user.is_active and user.check_password(password):
            session.clear()
            session["user_id"] = user.id
            g.current_user = user
            flash("登录成功。", "success")
            if next_url == url_for("index") and not has_permission("dashboard.view"):
                next_url = landing_url_for(user)
            return redirect(next_url)

        flash("用户名或密码不正确，或账户尚未启用。", "error")
        return redirect(url_for("login", next=next_url))

    @app.post("/logout")
    def logout():
        session.clear()
        flash("已退出登录。", "success")
        return redirect(url_for("login"))

    @app.get("/no-access")
    def no_access():
        return render_template("no_access.html")

    @app.context_processor
    def inject_auth_context():
        return {
            "current_user": getattr(g, "current_user", None),
            "has_permission": has_permission,
            "permissions": PERMISSIONS,
            "roles": ROLES,
        }

    @app.get("/account")
    @permission_required("account.self.employee.request")
    def account():
        pending_request = (
            EmployeeLinkRequest.query.filter_by(
                user_id=g.current_user.id,
                status="pending",
            )
            .order_by(EmployeeLinkRequest.requested_at.desc())
            .first()
        )
        recent_requests = (
            EmployeeLinkRequest.query.filter_by(user_id=g.current_user.id)
            .order_by(EmployeeLinkRequest.requested_at.desc())
            .limit(5)
            .all()
        )
        return render_template(
            "account.html",
            pending_request=pending_request,
            recent_requests=recent_requests,
        )

    @app.post("/account/employee-link")
    @permission_required("account.self.employee.request")
    def request_employee_link():
        if g.current_user.employee_id:
            flash("Your account is already linked to an employee.", "error")
            return redirect(url_for("account"))

        employee_no = request.form.get("employee_no", "").strip()
        name = request.form.get("name", "").strip()
        if not employee_no:
            flash("Please enter your employee number.", "error")
            return redirect(url_for("account"))

        employee = Employee.query.filter_by(employee_no=employee_no).first()
        if employee is None or (name and employee.name.strip() != name):
            flash("No matching employee was found.", "error")
            return redirect(url_for("account"))
        if User.query.filter_by(employee_id=employee.id).first():
            flash("That employee is already linked to another account.", "error")
            return redirect(url_for("account"))
        pending_request = EmployeeLinkRequest.query.filter_by(
            user_id=g.current_user.id,
            status="pending",
        ).first()
        if pending_request:
            flash("You already have a pending binding request.", "error")
            return redirect(url_for("account"))

        db.session.add(
            EmployeeLinkRequest(
                user_id=g.current_user.id,
                employee_id=employee.id,
                status="pending",
            )
        )
        db.session.commit()
        flash("Employee binding request submitted for review.", "success")
        return redirect(url_for("account"))

    @app.get("/employee-links")
    @permission_required("account.employee.link.review")
    def employee_link_requests():
        pending_requests = (
            EmployeeLinkRequest.query.filter_by(status="pending")
            .order_by(EmployeeLinkRequest.requested_at)
            .all()
        )
        recent_requests = (
            EmployeeLinkRequest.query.order_by(EmployeeLinkRequest.requested_at.desc())
            .limit(20)
            .all()
        )
        return render_template(
            "employee_links.html",
            pending_requests=pending_requests,
            recent_requests=recent_requests,
        )

    @app.post("/employee-links/<int:request_id>/approve")
    @permission_required("account.employee.link.review")
    def approve_employee_link(request_id):
        link_request = EmployeeLinkRequest.query.get_or_404(request_id)
        if link_request.status != "pending":
            flash("This request has already been reviewed.", "error")
            return redirect(url_for("employee_link_requests"))
        if link_request.user.employee_id:
            link_request.status = "rejected"
            link_request.reviewed_at = datetime.utcnow()
            link_request.reviewed_by_id = g.current_user.id
            db.session.commit()
            flash("The user is already linked to an employee.", "error")
            return redirect(url_for("employee_link_requests"))
        if User.query.filter_by(employee_id=link_request.employee_id).first():
            link_request.status = "rejected"
            link_request.reviewed_at = datetime.utcnow()
            link_request.reviewed_by_id = g.current_user.id
            db.session.commit()
            flash("The employee is already linked to another account.", "error")
            return redirect(url_for("employee_link_requests"))

        link_request.user.employee_id = link_request.employee_id
        link_request.status = "approved"
        link_request.reviewed_at = datetime.utcnow()
        link_request.reviewed_by_id = g.current_user.id
        db.session.commit()
        flash("Employee binding approved.", "success")
        return redirect(url_for("employee_link_requests"))

    @app.post("/employee-links/<int:request_id>/reject")
    @permission_required("account.employee.link.review")
    def reject_employee_link(request_id):
        link_request = EmployeeLinkRequest.query.get_or_404(request_id)
        if link_request.status != "pending":
            flash("This request has already been reviewed.", "error")
            return redirect(url_for("employee_link_requests"))
        link_request.status = "rejected"
        link_request.reviewed_at = datetime.utcnow()
        link_request.reviewed_by_id = g.current_user.id
        db.session.commit()
        flash("Employee binding rejected.", "success")
        return redirect(url_for("employee_link_requests"))

    @app.get("/accounts")
    @permission_required("account.disable")
    def accounts():
        query = User.query
        if g.current_user.role != "superadmin":
            query = query.filter_by(role="user")
        users = query.order_by(User.created_at.desc()).all()
        role_permissions_map = {
            role: role_permissions(role) if role != "superadmin" else set(PERMISSIONS)
            for role in ROLES
        }
        return render_template(
            "accounts.html",
            users=users,
            role_permissions=role_permissions_map,
            statuses=STATUSES,
        )

    @app.post("/accounts")
    @permission_required("account.create")
    def create_account():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")
        status = request.form.get("status", "active")
        if role not in ROLES or status not in STATUSES:
            flash("Invalid role or status.", "error")
            return redirect(url_for("accounts"))
        if not username or not password:
            flash("Please enter a username and password.", "error")
            return redirect(url_for("accounts"))
        if User.query.filter_by(username=username).first():
            flash("That username already exists.", "error")
            return redirect(url_for("accounts"))

        user = User(username=username, role=role, status=status)
        if status == "active":
            user.approved_at = datetime.utcnow()
            user.approved_by_id = g.current_user.id
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Account created.", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/role")
    @permission_required("account.role.update")
    def update_account_role(user_id):
        user = User.query.get_or_404(user_id)
        role = request.form.get("role", "user")
        if role not in ROLES:
            flash("Invalid role.", "error")
            return redirect(url_for("accounts"))
        if user.username == ADMIN_USERNAME and role != "superadmin":
            flash("The built-in superadmin cannot be demoted.", "error")
            return redirect(url_for("accounts"))
        active_superadmins = User.query.filter_by(
            role="superadmin",
            status="active",
        ).count()
        if user.role == "superadmin" and role != "superadmin" and active_superadmins <= 1:
            flash("At least one active superadmin is required.", "error")
            return redirect(url_for("accounts"))
        user.role = role
        db.session.commit()
        flash("Role updated.", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/status")
    @permission_required("account.disable")
    def update_account_status(user_id):
        user = User.query.get_or_404(user_id)
        status = request.form.get("status", "active")
        if status not in STATUSES:
            flash("Invalid status.", "error")
            return redirect(url_for("accounts"))
        if g.current_user.role != "superadmin" and user.role != "user":
            flash("Only a superadmin can change staff account status.", "error")
            return redirect(url_for("accounts"))
        if user.username == ADMIN_USERNAME and status != "active":
            flash("The built-in superadmin cannot be disabled.", "error")
            return redirect(url_for("accounts"))
        active_superadmins = User.query.filter_by(
            role="superadmin",
            status="active",
        ).count()
        if user.role == "superadmin" and status != "active" and active_superadmins <= 1:
            flash("At least one active superadmin is required.", "error")
            return redirect(url_for("accounts"))
        user.status = status
        if status == "active" and user.approved_at is None:
            user.approved_at = datetime.utcnow()
            user.approved_by_id = g.current_user.id
        db.session.commit()
        flash("Account status updated.", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/delete")
    @permission_required("account.delete")
    def delete_account(user_id):
        user = User.query.get_or_404(user_id)
        if user.username == ADMIN_USERNAME or user.id == g.current_user.id:
            flash("This account cannot be deleted.", "error")
            return redirect(url_for("accounts"))
        active_superadmins = User.query.filter_by(
            role="superadmin",
            status="active",
        ).count()
        if user.role == "superadmin" and user.status == "active" and active_superadmins <= 1:
            flash("At least one active superadmin is required.", "error")
            return redirect(url_for("accounts"))
        CheckIn.query.filter_by(user_id=user.id).delete()
        EmployeeLinkRequest.query.filter_by(user_id=user.id).delete()
        EmployeeLinkRequest.query.filter_by(reviewed_by_id=user.id).update(
            {"reviewed_by_id": None},
            synchronize_session=False,
        )
        User.query.filter_by(approved_by_id=user.id).update(
            {"approved_by_id": None},
            synchronize_session=False,
        )
        db.session.delete(user)
        db.session.commit()
        flash("Account deleted.", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/employee/unlink")
    @permission_required("account.employee.link.manage")
    def unlink_account_employee(user_id):
        user = User.query.get_or_404(user_id)
        if g.current_user.role != "superadmin" and user.role != "user":
            flash("Only a superadmin can unlink staff accounts.", "error")
            return redirect(url_for("accounts"))
        user.employee_id = None
        db.session.commit()
        flash("Employee link removed.", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/permissions")
    @permission_required("account.permission.update")
    def update_role_permissions():
        for role in ("admin", "user"):
            selected = set(request.form.getlist(f"{role}_permissions"))
            RolePermission.query.filter_by(role=role).delete()
            for permission in selected:
                if permission in PERMISSIONS:
                    db.session.add(
                        RolePermission(
                            role=role,
                            permission=permission,
                            enabled=True,
                        )
                    )
        db.session.commit()
        flash("Role permissions updated.", "success")
        return redirect(url_for("accounts"))

    @app.get("/registrations")
    @permission_required("registration.review")
    def registrations():
        pending_users = User.query.filter_by(status="pending").order_by(User.created_at).all()
        return render_template("registrations.html", pending_users=pending_users)

    @app.post("/registrations/<int:user_id>/approve")
    @permission_required("registration.review")
    def approve_registration(user_id):
        user = User.query.get_or_404(user_id)
        user.status = "active"
        user.role = "user"
        user.approved_at = datetime.utcnow()
        user.approved_by_id = g.current_user.id
        db.session.commit()
        flash("Registration approved.", "success")
        return redirect(url_for("registrations"))

    @app.post("/registrations/<int:user_id>/reject")
    @permission_required("registration.review")
    def reject_registration(user_id):
        user = User.query.get_or_404(user_id)
        if user.username == ADMIN_USERNAME:
            flash("The built-in superadmin cannot be rejected.", "error")
            return redirect(url_for("registrations"))
        user.status = "disabled"
        db.session.commit()
        flash("Registration rejected.", "success")
        return redirect(url_for("registrations"))

    @app.get("/checkin")
    @permission_required("checkin.self")
    def checkin():
        checkins = (
            CheckIn.query.filter_by(user_id=g.current_user.id)
            .order_by(CheckIn.created_at.desc())
            .limit(10)
            .all()
        )
        today_start, tomorrow_start = china_day_bounds_utc()
        checked_in_today = any(
            today_start <= item.created_at < tomorrow_start for item in checkins
        )
        return render_template(
            "checkin.html",
            checkins=checkins,
            checked_in_today=checked_in_today,
        )

    @app.post("/checkin")
    @permission_required("checkin.self")
    def submit_checkin():
        today_start, tomorrow_start = china_day_bounds_utc()
        existing = (
            CheckIn.query.filter_by(user_id=g.current_user.id)
            .order_by(CheckIn.created_at.desc())
            .first()
        )
        if existing and today_start <= existing.created_at < tomorrow_start:
            flash("You have already checked in today.", "success")
            return redirect(url_for("checkin"))
        db.session.add(CheckIn(user_id=g.current_user.id))
        db.session.commit()
        flash("Check-in recorded.", "success")
        return redirect(url_for("checkin"))

    @app.get("/")
    @permission_required("dashboard.view")
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
    @permission_required("employee.view")
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
    @permission_required("employee.create")
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
    @permission_required("employee.import")
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
    @permission_required("employee.update")
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
    @permission_required("employee.update")
    def enable_all_employees():
        updated = Employee.query.filter_by(eligible=False).update(
            {"eligible": True},
            synchronize_session=False,
        )
        db.session.commit()
        flash(f"已将 {updated} 位员工设为可参与抽奖。", "success")
        return redirect(url_for("employees"))

    @app.post("/employees/sync-eligibility-from-checkins")
    @permission_required("employee.update")
    def sync_employee_eligibility_from_checkins():
        today_start, tomorrow_start = china_day_bounds_utc()
        checked_in_employee_ids = {
            employee_id
            for (employee_id,) in (
                db.session.query(User.employee_id)
                .join(CheckIn, CheckIn.user_id == User.id)
                .filter(
                    User.status == "active",
                    User.employee_id.isnot(None),
                    CheckIn.created_at >= today_start,
                    CheckIn.created_at < tomorrow_start,
                )
                .distinct()
                .all()
            )
        }

        Employee.query.update({"eligible": False}, synchronize_session=False)
        enabled_count = 0
        if checked_in_employee_ids:
            enabled_count = Employee.query.filter(
                Employee.id.in_(checked_in_employee_ids)
            ).update({"eligible": True}, synchronize_session=False)
        db.session.commit()
        disabled_count = Employee.query.filter_by(eligible=False).count()
        flash(
            f"已按今日签到同步参与资格：{enabled_count} 位员工可参与，{disabled_count} 位员工不可参与。",
            "success",
        )
        return redirect(url_for("employees"))

    @app.get("/prizes")
    @permission_required("prize.view")
    def prizes():
        rows = Prize.query.order_by(Prize.level, Prize.id).all()
        return render_template(
            "prizes.html",
            prizes=rows,
            settings=get_draw_settings(),
        )

    @app.post("/prizes")
    @permission_required("prize.create")
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
    @permission_required("prize.reset")
    def reset_prizes():
        DrawResult.query.delete()
        DrawSession.query.delete()
        Prize.query.delete()
        db.session.commit()
        flash("所有奖项和抽奖结果已重设。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/<int:prize_id>/remove")
    @permission_required("prize.disable")
    def remove_prize(prize_id):
        prize = Prize.query.get_or_404(prize_id)
        prize.active = False
        db.session.commit()
        flash(f"{prize.name} 已从后续抽奖中移除，历史结果已保留。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/<int:prize_id>/restore")
    @permission_required("prize.update")
    def restore_prize(prize_id):
        prize = Prize.query.get_or_404(prize_id)
        prize.active = True
        db.session.commit()
        flash(f"{prize.name} 已恢复到抽奖列表。", "success")
        return redirect(url_for("prizes"))

    @app.post("/prizes/<int:prize_id>/delete")
    @permission_required("prize.delete")
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
    @permission_required("draw.configure")
    def update_draw_settings():
        roll_names = request.form.get("roll_names") == "1"
        auto_disable_winners = request.form.get("auto_disable_winners") == "1"
        set_bool_setting("DRAW_ROLL_NAMES", roll_names)
        set_bool_setting("DRAW_AUTO_DISABLE_WINNERS", auto_disable_winners)
        db.session.commit()
        flash("抽奖设置已更新。", "success")
        return redirect(url_for("prizes"))

    @app.post("/employees/reset")
    @permission_required("employee.reset")
    def reset_employees():
        confirmation = request.form.get("confirmation", "").strip()
        if confirmation != "清空员工":
            flash("员工重置已取消。请输入“清空员工”进行确认。", "error")
            return redirect(url_for("employees"))

        DrawResult.query.delete()
        DrawSession.query.delete()
        EmployeeLinkRequest.query.delete()
        User.query.update({"employee_id": None}, synchronize_session=False)
        Employee.query.delete()
        db.session.commit()
        flash("所有员工信息和抽奖结果已重置。", "success")
        return redirect(url_for("employees"))

    @app.get("/draw")
    @permission_required("draw.execute")
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
    @permission_required("draw.result.view")
    def draw_session_result(session_id):
        session = DrawSession.query.get_or_404(session_id)
        return render_template(
            "draw_result.html",
            session=session,
            show_animation=False,
        )

    @app.post("/draw")
    @permission_required("draw.execute")
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
    @permission_required("draw.result.view")
    def results():
        rows = DrawResult.query.order_by(DrawResult.created_at.desc()).all()
        return render_template("results.html", results=rows)

    @app.get("/results/export.csv")
    @permission_required("draw.result.export")
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
    @permission_required("draw.result.reset")
    def reset_results():
        DrawResult.query.delete()
        DrawSession.query.delete()
        db.session.commit()
        flash("所有抽奖结果已重置。", "success")
        return redirect(url_for("results"))


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
