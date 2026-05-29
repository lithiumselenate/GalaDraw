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
AUTH_ENABLED = False
ADMIN_USERNAME = "superadmin"
ADMIN_INITIAL_PASSWORD = "Changeme123!"
ROLES = ("superadmin", "admin", "user")
STATUSES = ("pending", "active", "disabled")
AUTH_DISABLED_PERMISSIONS = {
    "account.create",
    "account.delete",
    "account.disable",
    "account.role.update",
    "account.permission.update",
    "account.self.employee.request",
    "account.employee.link.review",
    "account.employee.link.manage",
    "registration.review",
    "checkin.self",
    "checkin.view_all",
    "checkin.manage",
}
AUTH_ONLY_ENDPOINTS = {
    "login",
    "login_submit",
    "logout",
    "register",
    "register_submit",
    "account",
    "change_account_password",
    "request_employee_link",
    "accounts",
    "create_account",
    "update_account_role",
    "update_account_status",
    "delete_account",
    "unlink_account_employee",
    "update_role_permissions",
    "registrations",
    "approve_registration",
    "reject_registration",
    "employee_link_requests",
    "approve_employee_link",
    "reject_employee_link",
    "checkin",
    "submit_checkin",
    "sync_employee_eligibility_from_checkins",
    "no_access",
}
PERMISSIONS = {
    "account.create": "创建账户",
    "account.delete": "删除账户",
    "account.disable": "禁用账户",
    "account.role.update": "修改账户角色",
    "account.permission.update": "修改角色权限",
    "account.self.employee.request": "申请员工信息关联",
    "account.employee.link.review": "审核员工信息关联",
    "account.employee.link.manage": "管理员工信息关联",
    "registration.review": "审核注册申请",
    "dashboard.view": "查看概览",
    "employee.view": "查看员工",
    "employee.create": "新增员工",
    "employee.import": "导入员工",
    "employee.update": "更新员工",
    "employee.reset": "重置员工",
    "prize.view": "查看奖项",
    "prize.create": "新增奖项",
    "prize.update": "更新奖项",
    "prize.disable": "禁用奖项",
    "prize.delete": "删除奖项",
    "prize.reset": "重置奖项",
    "draw.configure": "配置抽奖",
    "draw.execute": "执行抽奖",
    "draw.result.view": "查看抽奖结果",
    "draw.result.export": "导出抽奖结果",
    "draw.result.reset": "重置抽奖结果",
    "checkin.self": "本人签到",
    "checkin.view_all": "查看所有签到",
    "checkin.manage": "管理签到",
}
PERMISSION_LABELS_EN = {
    "account.create": "Create accounts",
    "account.delete": "Delete accounts",
    "account.disable": "Disable accounts",
    "account.role.update": "Update account roles",
    "account.permission.update": "Update role permissions",
    "account.self.employee.request": "Request employee link",
    "account.employee.link.review": "Review employee links",
    "account.employee.link.manage": "Manage employee links",
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
    "checkin.self": "Self check-in",
    "checkin.view_all": "View all check-ins",
    "checkin.manage": "Manage check-ins",
}
ROLE_LABELS = {
    "superadmin": "超级管理员",
    "admin": "管理员",
    "user": "普通用户",
}
STATUS_LABELS = {
    "pending": "待审核",
    "active": "已启用",
    "disabled": "已禁用",
}
REQUEST_STATUS_LABELS = {
    "pending": "待审核",
    "approved": "已批准",
    "rejected": "已拒绝",
}
SUPPORTED_LANGUAGES = ("zh", "en")
TRANSLATIONS = {
    "zh": {
        "app.name": "BEE 幸运抽奖",
        "nav.dashboard": "概览",
        "nav.employees": "员工配置",
        "nav.prizes": "奖项管理",
        "nav.draw": "抽奖页面",
        "nav.results": "抽奖结果",
        "nav.registrations": "账户审核",
        "nav.accounts": "账户管理",
        "nav.account": "我的账户",
        "nav.employee_links": "员工信息关联",
        "nav.checkin": "签到",
        "nav.settings": "系统设置",
        "nav.logout": "退出登录",
        "settings.eyebrow": "后台",
        "settings.title": "系统设置",
        "settings.language.title": "语言设置",
        "settings.language.label": "后台语言",
        "settings.language.zh": "中文",
        "settings.language.en": "English",
        "settings.language.save": "保存语言设置",
        "settings.language.updated": "语言设置已更新。",
        "settings.language.invalid": "请选择有效的语言。",
    },
    "en": {
        "app.name": "BEE Lucky Draw",
        "nav.dashboard": "Dashboard",
        "nav.employees": "Employees",
        "nav.prizes": "Prizes",
        "nav.draw": "Draw",
        "nav.results": "Results",
        "nav.registrations": "Registration Review",
        "nav.accounts": "Accounts",
        "nav.account": "My Account",
        "nav.employee_links": "Employee Links",
        "nav.checkin": "Check-in",
        "nav.settings": "Settings",
        "nav.logout": "Log out",
        "settings.eyebrow": "Admin",
        "settings.title": "Settings",
        "settings.language.title": "Language",
        "settings.language.label": "Admin language",
        "settings.language.zh": "中文",
        "settings.language.en": "English",
        "settings.language.save": "Save language",
        "settings.language.updated": "Language setting updated.",
        "settings.language.invalid": "Please select a valid language.",
    },
}
TRANSLATIONS["zh"].update(
    {
        "role.superadmin": "超级管理员",
        "role.admin": "管理员",
        "role.user": "普通用户",
        "status.pending": "待审核",
        "status.active": "已启用",
        "status.disabled": "已禁用",
        "request.pending": "待审核",
        "request.approved": "已批准",
        "request.rejected": "已拒绝",
        "common.yes": "是",
        "common.no": "否",
        "common.enabled": "开启",
        "common.disabled": "关闭",
        "common.on": "已开启",
        "common.off": "已关闭",
        "common.actions": "操作",
        "common.status": "状态",
        "common.name": "姓名",
        "common.department": "部门",
        "common.time": "时间",
        "common.search": "搜索",
        "common.clear": "清除",
        "common.previous": "上一页",
        "common.next": "下一页",
        "common.back_admin": "返回后台",
        "dashboard.eyebrow": "后台管理",
        "dashboard.title": "BEE 幸运抽奖",
        "dashboard.description": "管理员工、配置奖项、执行抽奖，并导出中奖结果。",
        "dashboard.start": "开始抽奖",
        "dashboard.stat.employees": "员工",
        "dashboard.stat.eligible": "可参与",
        "dashboard.stat.prizes": "奖项",
        "dashboard.stat.winners": "已中奖",
        "dashboard.recent": "最近中奖",
        "dashboard.no_recent": "暂无中奖记录。",
        "employee.eyebrow": "参与人员",
        "employee.title": "员工",
        "employee.export": "导出员工列表",
        "employee.sync": "按今日签到同步参与资格",
        "employee.sync.confirm": "确认按今日签到同步所有员工的参与资格？已签到员工将可参与，未签到员工将不可参与。",
        "employee.enable_all": "全部设为可参与",
        "employee.add_title": "新增员工",
        "employee.number": "员工编号",
        "employee.eligible": "参与抽奖",
        "employee.add": "新增",
        "employee.import_title": "导入员工文件",
        "employee.import_hint": "文件表头：员工编号、姓名、部门。",
        "employee.import": "导入",
        "employee.reset_title": "重置员工信息",
        "employee.reset_hint": "删除所有员工记录，并清空已有抽奖结果。提交前请输入“清空员工”。",
        "employee.reset_confirm": "确认重置所有员工信息并清空抽奖结果？",
        "employee.confirm_text": "确认文本",
        "employee.confirm_placeholder": "清空员工",
        "employee.reset": "重置员工",
        "employee.list": "员工列表",
        "employee.search_label": "搜索员工姓名或编号",
        "employee.search_placeholder": "输入姓名或员工编号",
        "employee.number_short": "编号",
        "employee.set_ineligible": "设为不可参与",
        "employee.set_eligible": "设为可参与",
        "employee.ineligible": "不可参与",
        "employee.eligible_state": "可参与",
        "employee.empty": "暂无员工。",
        "employee.page_status": "第 {page} / {pages} 页，共 {total} 位员工",
        "prize.eyebrow": "配置",
        "prize.title": "奖项",
        "prize.add_title": "新增奖项",
        "prize.name": "奖项名称",
        "prize.name_placeholder": "一等奖",
        "prize.level": "奖项等级",
        "prize.winner_count": "中奖人数",
        "prize.add": "新增",
        "prize.settings": "抽奖设置",
        "prize.roll_names": "姓名滚动",
        "prize.current": "当前为{state}。",
        "prize.roll_off": "关闭滚动",
        "prize.roll_on": "开启滚动",
        "prize.auto_disable": "中奖后自动设为不可参与",
        "prize.auto_disable_off": "关闭自动禁用",
        "prize.auto_disable_on": "开启自动禁用",
        "prize.reset_title": "重设抽奖项目",
        "prize.reset_hint": "删除所有奖项，并清空已有抽奖结果。",
        "prize.reset_confirm": "确认重设所有抽奖项目并清空抽奖结果？",
        "prize.reset": "重设奖项",
        "prize.list": "奖项列表",
        "prize.active": "可抽取",
        "prize.removed": "已移除",
        "prize.remove": "移除奖项",
        "prize.restore": "恢复奖项",
        "prize.delete": "删除奖项",
        "prize.delete_confirm": "确认删除该奖项及其关联抽奖结果？",
        "prize.empty": "暂无奖项。",
        "draw.title": "现场抽奖",
        "draw.live_title": "幸运抽奖",
        "draw.subtitle": "选择奖项。",
        "draw.candidates": "可参与：{count}人",
        "draw.prize_count": "{count} 个奖项",
        "draw.roll_status": "姓名滚动：{state}",
        "draw.prize": "奖项",
        "draw.people": "人",
        "draw.no_slots": "暂无可抽取名额",
        "draw.placeholder": "即将抽出 {count} 位中奖者",
        "draw.start": "开始抽奖",
        "draw.no_prizes": "请先在后台创建至少一个奖项。",
        "draw.no_candidates": "当前没有可参与抽奖的员工。",
        "draw.result_title": "中奖结果",
        "draw.winner_count": "{count} 位中奖者",
        "draw.congrats": "恭喜中奖",
        "draw.view_results": "查看结果",
        "draw.next": "下一次抽奖",
        "results.eyebrow": "记录",
        "results.title": "抽奖结果",
        "results.export": "导出结果文件",
        "results.reset": "重置结果",
        "results.prize": "奖项",
        "results.empty": "暂无抽奖结果。",
        "account.eyebrow": "个人资料",
        "account.title": "我的账户",
        "account.role_status": "角色：{role} | 状态：{status}",
        "account.employee_number": "员工编号",
        "account.draw_eligible": "抽奖资格",
        "account.pending_link": "{employee} #{number} 的关联申请正在等待审核。",
        "account.no_employee": "当前账户尚未关联员工信息。",
        "account.link_title": "申请关联员工信息",
        "account.name_placeholder": "建议填写",
        "account.submit_review": "提交审核",
        "account.password_title": "修改密码",
        "account.current_password": "当前密码",
        "account.new_password": "新密码",
        "account.confirm_password": "确认新密码",
        "account.update_password": "更新密码",
        "account.recent_requests": "最近申请",
        "account.request_employee": "员工",
        "account.requested_at": "申请时间",
        "account.reviewed_at": "审核时间",
        "account.no_requests": "暂无关联申请。",
        "accounts.eyebrow": "访问",
        "accounts.title": "账户管理",
        "accounts.create_title": "创建账户",
        "accounts.username": "用户名",
        "accounts.password": "密码",
        "accounts.role": "角色",
        "accounts.status": "状态",
        "accounts.create": "创建",
        "accounts.permissions": "角色权限",
        "accounts.save_permissions": "保存权限",
        "accounts.all": "所有账户",
        "accounts.employee": "员工",
        "accounts.created": "创建时间",
        "accounts.delete": "删除",
        "accounts.delete_confirm": "确认删除该账户？",
        "accounts.unlink": "解除员工关联",
        "accounts.unlink_confirm": "确认解除该员工关联？",
        "accounts.empty": "没有账户。",
        "checkin.eyebrow": "出席",
        "checkin.title": "签到",
        "checkin.employee": "员工：{employee} #{number}",
        "checkin.no_employee": "没有已关联的员工信息。请提交关联请求。",
        "checkin.done": "已签到",
        "checkin.submit": "签到",
        "checkin.recent": "近期签到",
        "checkin.time": "签到时间",
        "checkin.empty": "暂无签到记录。",
        "links.eyebrow": "访问",
        "links.title": "员工信息关联审核",
        "links.pending": "待处理请求",
        "links.user": "用户",
        "links.employee": "员工",
        "links.requested": "申请时间",
        "links.approve": "批准",
        "links.reject": "拒绝",
        "links.no_pending": "没有待处理的员工关联请求。",
        "links.recent": "近期请求",
        "links.reviewer": "审核人",
        "links.empty": "没有员工关联请求。",
        "login.title": "登录 - BEE 幸运抽奖",
        "login.brand": "幸运抽奖",
        "login.username": "用户名",
        "login.password": "密码",
        "login.submit": "登录",
        "login.register": "注册账户",
        "register.title": "注册 - BEE 幸运抽奖",
        "register.brand": "账户注册",
        "register.submit": "提交注册申请",
        "register.back": "返回登录",
        "registrations.eyebrow": "访问",
        "registrations.title": "账户审核",
        "registrations.requested": "申请时间",
        "registrations.approve": "批准",
        "registrations.reject": "拒绝",
        "registrations.empty": "没有待审核的账户。",
        "no_access.title": "暂无权限",
        "no_access.message": "你的账户已启用，但尚未分配可访问的权限。",
    }
)
TRANSLATIONS["en"].update(
    {
        "role.superadmin": "Super Admin",
        "role.admin": "Admin",
        "role.user": "User",
        "status.pending": "Pending",
        "status.active": "Active",
        "status.disabled": "Disabled",
        "request.pending": "Pending",
        "request.approved": "Approved",
        "request.rejected": "Rejected",
        "common.yes": "Yes",
        "common.no": "No",
        "common.enabled": "On",
        "common.disabled": "Off",
        "common.on": "On",
        "common.off": "Off",
        "common.actions": "Actions",
        "common.status": "Status",
        "common.name": "Name",
        "common.department": "Department",
        "common.time": "Time",
        "common.search": "Search",
        "common.clear": "Clear",
        "common.previous": "Previous",
        "common.next": "Next",
        "common.back_admin": "Back to Admin",
        "dashboard.eyebrow": "Admin",
        "dashboard.title": "BEE Lucky Draw",
        "dashboard.description": "Manage employees, configure prizes, run the draw, and export winner results.",
        "dashboard.start": "Start Draw",
        "dashboard.stat.employees": "Employees",
        "dashboard.stat.eligible": "Eligible",
        "dashboard.stat.prizes": "Prizes",
        "dashboard.stat.winners": "Winners",
        "dashboard.recent": "Recent Winners",
        "dashboard.no_recent": "No winner records yet.",
        "employee.eyebrow": "Participants",
        "employee.title": "Employees",
        "employee.export": "Export Employees",
        "employee.sync": "Sync Eligibility from Today's Check-ins",
        "employee.sync.confirm": "Sync all employees by today's check-ins? Checked-in employees will be eligible; others will be ineligible.",
        "employee.enable_all": "Set All Eligible",
        "employee.add_title": "Add Employee",
        "employee.number": "Employee No.",
        "employee.eligible": "Draw Eligible",
        "employee.add": "Add",
        "employee.import_title": "Import Employee File",
        "employee.import_hint": "File headers: Employee No., Name, Department.",
        "employee.import": "Import",
        "employee.reset_title": "Reset Employees",
        "employee.reset_hint": "Delete all employee records and clear existing draw results. Enter the confirmation text before submitting.",
        "employee.reset_confirm": "Reset all employee information and clear draw results?",
        "employee.confirm_text": "Confirmation text",
        "employee.confirm_placeholder": "Clear employees",
        "employee.reset": "Reset Employees",
        "employee.list": "Employee List",
        "employee.search_label": "Search by employee name or number",
        "employee.search_placeholder": "Enter name or employee number",
        "employee.number_short": "No.",
        "employee.set_ineligible": "Set Ineligible",
        "employee.set_eligible": "Set Eligible",
        "employee.ineligible": "Ineligible",
        "employee.eligible_state": "Eligible",
        "employee.empty": "No employees.",
        "employee.page_status": "Page {page} / {pages}, {total} employees",
        "prize.eyebrow": "Configuration",
        "prize.title": "Prizes",
        "prize.add_title": "Add Prize",
        "prize.name": "Prize Name",
        "prize.name_placeholder": "First Prize",
        "prize.level": "Prize Level",
        "prize.winner_count": "Winner Count",
        "prize.add": "Add",
        "prize.settings": "Draw Settings",
        "prize.roll_names": "Name Rolling",
        "prize.current": "Currently {state}.",
        "prize.roll_off": "Turn Rolling Off",
        "prize.roll_on": "Turn Rolling On",
        "prize.auto_disable": "Set winners ineligible automatically",
        "prize.auto_disable_off": "Turn Auto-disable Off",
        "prize.auto_disable_on": "Turn Auto-disable On",
        "prize.reset_title": "Reset Prizes",
        "prize.reset_hint": "Delete all prizes and clear existing draw results.",
        "prize.reset_confirm": "Reset all prizes and clear draw results?",
        "prize.reset": "Reset Prizes",
        "prize.list": "Prize List",
        "prize.active": "Drawable",
        "prize.removed": "Removed",
        "prize.remove": "Remove Prize",
        "prize.restore": "Restore Prize",
        "prize.delete": "Delete Prize",
        "prize.delete_confirm": "Delete this prize and related draw results?",
        "prize.empty": "No prizes.",
        "draw.title": "Live Draw",
        "draw.live_title": "Lucky Draw",
        "draw.subtitle": "Select a prize.",
        "draw.candidates": "Eligible: {count}",
        "draw.prize_count": "{count} prizes",
        "draw.roll_status": "Name rolling: {state}",
        "draw.prize": "Prize",
        "draw.people": "people",
        "draw.no_slots": "No draw slots",
        "draw.placeholder": "{count} winner(s) will be drawn",
        "draw.start": "Start Draw",
        "draw.no_prizes": "Create at least one prize in the admin area first.",
        "draw.no_candidates": "There are no eligible employees.",
        "draw.result_title": "Winner Results",
        "draw.winner_count": "{count} winner(s)",
        "draw.congrats": "Congratulations",
        "draw.view_results": "View Results",
        "draw.next": "Next Draw",
        "results.eyebrow": "Records",
        "results.title": "Draw Results",
        "results.export": "Export Results",
        "results.reset": "Reset Results",
        "results.prize": "Prize",
        "results.empty": "No draw results.",
        "account.eyebrow": "Profile",
        "account.title": "My Account",
        "account.role_status": "Role: {role} | Status: {status}",
        "account.employee_number": "Employee No.",
        "account.draw_eligible": "Draw Eligibility",
        "account.pending_link": "Binding request for {employee} #{number} is pending review.",
        "account.no_employee": "No employee is linked to this account yet.",
        "account.link_title": "Request Employee Link",
        "account.name_placeholder": "Recommended",
        "account.submit_review": "Submit for Review",
        "account.password_title": "Change Password",
        "account.current_password": "Current Password",
        "account.new_password": "New Password",
        "account.confirm_password": "Confirm New Password",
        "account.update_password": "Update Password",
        "account.recent_requests": "Recent Requests",
        "account.request_employee": "Employee",
        "account.requested_at": "Requested",
        "account.reviewed_at": "Reviewed",
        "account.no_requests": "No binding requests.",
        "accounts.eyebrow": "Access",
        "accounts.title": "Accounts",
        "accounts.create_title": "Create Account",
        "accounts.username": "Username",
        "accounts.password": "Password",
        "accounts.role": "Role",
        "accounts.status": "Status",
        "accounts.create": "Create",
        "accounts.permissions": "Role Permissions",
        "accounts.save_permissions": "Save Permissions",
        "accounts.all": "All Accounts",
        "accounts.employee": "Employee",
        "accounts.created": "Created",
        "accounts.delete": "Delete",
        "accounts.delete_confirm": "Delete this account?",
        "accounts.unlink": "Unlink Employee",
        "accounts.unlink_confirm": "Unlink this employee?",
        "accounts.empty": "No accounts.",
        "checkin.eyebrow": "Attendance",
        "checkin.title": "Check-in",
        "checkin.employee": "Employee: {employee} #{number}",
        "checkin.no_employee": "No employee is linked. Please submit a link request.",
        "checkin.done": "Checked in",
        "checkin.submit": "Check in",
        "checkin.recent": "Recent Check-ins",
        "checkin.time": "Check-in Time",
        "checkin.empty": "No check-ins yet.",
        "links.eyebrow": "Access",
        "links.title": "Employee Link Review",
        "links.pending": "Pending Requests",
        "links.user": "User",
        "links.employee": "Employee",
        "links.requested": "Requested",
        "links.approve": "Approve",
        "links.reject": "Reject",
        "links.no_pending": "No pending employee link requests.",
        "links.recent": "Recent Requests",
        "links.reviewer": "Reviewer",
        "links.empty": "No employee link requests.",
        "login.title": "Log in - BEE Lucky Draw",
        "login.brand": "Lucky Draw",
        "login.username": "Username",
        "login.password": "Password",
        "login.submit": "Log in",
        "login.register": "Register Account",
        "register.title": "Register - BEE Lucky Draw",
        "register.brand": "Account Registration",
        "register.submit": "Submit Registration",
        "register.back": "Back to Login",
        "registrations.eyebrow": "Access",
        "registrations.title": "Registration Review",
        "registrations.requested": "Requested",
        "registrations.approve": "Approve",
        "registrations.reject": "Reject",
        "registrations.empty": "No pending accounts.",
        "no_access.title": "No Access",
        "no_access.message": "Your account is active, but no permissions are assigned yet.",
    }
)
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


def get_language():
    setting = AppSetting.query.filter_by(name="APP_LANGUAGE").first()
    if setting and setting.value in SUPPORTED_LANGUAGES:
        return setting.value
    return "zh"


def set_language(language):
    setting = AppSetting.query.filter_by(name="APP_LANGUAGE").first()
    if setting is None:
        setting = AppSetting(name="APP_LANGUAGE")
        db.session.add(setting)
    setting.value = language


def translate(key):
    language = getattr(g, "language", None) or get_language()
    messages = TRANSLATIONS.get(language, TRANSLATIONS["zh"])
    return messages.get(key, TRANSLATIONS["zh"].get(key, key))


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
    if not AUTH_ENABLED:
        return permission not in AUTH_DISABLED_PERMISSIONS

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
    flash("你没有访问该页面的权限。", "error")
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
    if not AUTH_ENABLED:
        return url_for("index")
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
        g.language = get_language()
        if not AUTH_ENABLED:
            if request.endpoint in AUTH_ONLY_ENDPOINTS:
                return redirect(url_for("index"))
            return None

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
            flash("请输入用户名和密码。", "error")
            return redirect(url_for("register"))
        if len(password) < 8:
            flash("密码至少需要 8 个字符。", "error")
            return redirect(url_for("register"))
        if User.query.filter_by(username=username).first():
            flash("该用户名已注册。", "error")
            return redirect(url_for("register"))

        user = User(username=username, role="user", status="pending")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("注册申请已提交，请等待审核。", "success")
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

    @app.get("/settings")
    @permission_required("draw.configure")
    def settings():
        return render_template("settings.html")

    @app.post("/settings/language")
    @permission_required("draw.configure")
    def update_language():
        language = request.form.get("language", "zh")
        if language not in SUPPORTED_LANGUAGES:
            flash(translate("settings.language.invalid"), "error")
            return redirect(url_for("settings"))
        set_language(language)
        db.session.commit()
        g.language = language
        flash(translate("settings.language.updated"), "success")
        return redirect(url_for("settings"))

    @app.context_processor
    def inject_auth_context():
        return {
            "current_user": getattr(g, "current_user", None),
            "auth_enabled": AUTH_ENABLED,
            "language": getattr(g, "language", "zh"),
            "supported_languages": SUPPORTED_LANGUAGES,
            "t": translate,
            "has_permission": has_permission,
            "permissions": PERMISSIONS,
            "permission_labels": (
                PERMISSION_LABELS_EN
                if getattr(g, "language", "zh") == "en"
                else PERMISSIONS
            ),
            "roles": ROLES,
            "role_labels": {role: translate(f"role.{role}") for role in ROLES},
            "status_labels": {
                status: translate(f"status.{status}") for status in STATUSES
            },
            "request_status_labels": {
                status: translate(f"request.{status}")
                for status in REQUEST_STATUS_LABELS
            },
            "timedelta": timedelta,
        }

    @app.get("/account")
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

    @app.post("/account/password")
    def change_account_password():
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not g.current_user.check_password(current_password):
            flash("当前密码不正确。", "error")
            return redirect(url_for("account"))
        if len(new_password) < 8:
            flash("新密码至少需要 8 个字符。", "error")
            return redirect(url_for("account"))
        if new_password != confirm_password:
            flash("两次输入的新密码不一致。", "error")
            return redirect(url_for("account"))

        g.current_user.set_password(new_password)
        db.session.commit()
        flash("密码已更新。", "success")
        return redirect(url_for("account"))

    @app.post("/account/employee-link")
    @permission_required("account.self.employee.request")
    def request_employee_link():
        if g.current_user.employee_id:
            flash("你的账户已经关联了员工信息。", "error")
            return redirect(url_for("account"))

        employee_no = request.form.get("employee_no", "").strip()
        name = request.form.get("name", "").strip()
        if not employee_no:
            flash("请输入员工编号。", "error")
            return redirect(url_for("account"))

        employee = Employee.query.filter_by(employee_no=employee_no).first()
        if employee is None or (name and employee.name.strip() != name):
            flash("没有找到匹配的员工。", "error")
            return redirect(url_for("account"))
        if User.query.filter_by(employee_id=employee.id).first():
            flash("该员工已经关联到其他账户。", "error")
            return redirect(url_for("account"))
        pending_request = EmployeeLinkRequest.query.filter_by(
            user_id=g.current_user.id,
            status="pending",
        ).first()
        if pending_request:
            flash("你已经有一条待审核的关联申请。", "error")
            return redirect(url_for("account"))

        db.session.add(
            EmployeeLinkRequest(
                user_id=g.current_user.id,
                employee_id=employee.id,
                status="pending",
            )
        )
        db.session.commit()
        flash("员工信息关联申请已提交审核。", "success")
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
            flash("该申请已经审核过。", "error")
            return redirect(url_for("employee_link_requests"))
        if link_request.user.employee_id:
            link_request.status = "rejected"
            link_request.reviewed_at = datetime.utcnow()
            link_request.reviewed_by_id = g.current_user.id
            db.session.commit()
            flash("该用户已经关联了员工信息。", "error")
            return redirect(url_for("employee_link_requests"))
        if User.query.filter_by(employee_id=link_request.employee_id).first():
            link_request.status = "rejected"
            link_request.reviewed_at = datetime.utcnow()
            link_request.reviewed_by_id = g.current_user.id
            db.session.commit()
            flash("该员工已经关联到其他账户。", "error")
            return redirect(url_for("employee_link_requests"))

        link_request.user.employee_id = link_request.employee_id
        link_request.status = "approved"
        link_request.reviewed_at = datetime.utcnow()
        link_request.reviewed_by_id = g.current_user.id
        db.session.commit()
        flash("员工信息关联已批准。", "success")
        return redirect(url_for("employee_link_requests"))

    @app.post("/employee-links/<int:request_id>/reject")
    @permission_required("account.employee.link.review")
    def reject_employee_link(request_id):
        link_request = EmployeeLinkRequest.query.get_or_404(request_id)
        if link_request.status != "pending":
            flash("该申请已经审核过。", "error")
            return redirect(url_for("employee_link_requests"))
        link_request.status = "rejected"
        link_request.reviewed_at = datetime.utcnow()
        link_request.reviewed_by_id = g.current_user.id
        db.session.commit()
        flash("员工信息关联已拒绝。", "success")
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
            flash("角色或状态无效。", "error")
            return redirect(url_for("accounts"))
        if not username or not password:
            flash("请输入用户名和密码。", "error")
            return redirect(url_for("accounts"))
        if User.query.filter_by(username=username).first():
            flash("该用户名已存在。", "error")
            return redirect(url_for("accounts"))

        user = User(username=username, role=role, status=status)
        if status == "active":
            user.approved_at = datetime.utcnow()
            user.approved_by_id = g.current_user.id
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("账户已创建。", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/role")
    @permission_required("account.role.update")
    def update_account_role(user_id):
        user = User.query.get_or_404(user_id)
        role = request.form.get("role", "user")
        if role not in ROLES:
            flash("角色无效。", "error")
            return redirect(url_for("accounts"))
        if user.username == ADMIN_USERNAME and role != "superadmin":
            flash("内置超级管理员不能被降级。", "error")
            return redirect(url_for("accounts"))
        active_superadmins = User.query.filter_by(
            role="superadmin",
            status="active",
        ).count()
        if user.role == "superadmin" and role != "superadmin" and active_superadmins <= 1:
            flash("系统至少需要保留一个已启用的超级管理员。", "error")
            return redirect(url_for("accounts"))
        user.role = role
        db.session.commit()
        flash("角色已更新。", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/status")
    @permission_required("account.disable")
    def update_account_status(user_id):
        user = User.query.get_or_404(user_id)
        status = request.form.get("status", "active")
        if status not in STATUSES:
            flash("状态无效。", "error")
            return redirect(url_for("accounts"))
        if g.current_user.role != "superadmin" and user.role != "user":
            flash("只有超级管理员可以修改管理账户状态。", "error")
            return redirect(url_for("accounts"))
        if user.username == ADMIN_USERNAME and status != "active":
            flash("内置超级管理员不能被禁用。", "error")
            return redirect(url_for("accounts"))
        active_superadmins = User.query.filter_by(
            role="superadmin",
            status="active",
        ).count()
        if user.role == "superadmin" and status != "active" and active_superadmins <= 1:
            flash("系统至少需要保留一个已启用的超级管理员。", "error")
            return redirect(url_for("accounts"))
        user.status = status
        if status == "active" and user.approved_at is None:
            user.approved_at = datetime.utcnow()
            user.approved_by_id = g.current_user.id
        db.session.commit()
        flash("账户状态已更新。", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/delete")
    @permission_required("account.delete")
    def delete_account(user_id):
        user = User.query.get_or_404(user_id)
        if user.username == ADMIN_USERNAME or user.id == g.current_user.id:
            flash("该账户不能删除。", "error")
            return redirect(url_for("accounts"))
        active_superadmins = User.query.filter_by(
            role="superadmin",
            status="active",
        ).count()
        if user.role == "superadmin" and user.status == "active" and active_superadmins <= 1:
            flash("系统至少需要保留一个已启用的超级管理员。", "error")
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
        flash("账户已删除。", "success")
        return redirect(url_for("accounts"))

    @app.post("/accounts/<int:user_id>/employee/unlink")
    @permission_required("account.employee.link.manage")
    def unlink_account_employee(user_id):
        user = User.query.get_or_404(user_id)
        if g.current_user.role != "superadmin" and user.role != "user":
            flash("只有超级管理员可以解除管理账户的员工关联。", "error")
            return redirect(url_for("accounts"))
        user.employee_id = None
        db.session.commit()
        flash("员工关联已解除。", "success")
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
        flash("角色权限已更新。", "success")
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
        flash("注册申请已批准。", "success")
        return redirect(url_for("registrations"))

    @app.post("/registrations/<int:user_id>/reject")
    @permission_required("registration.review")
    def reject_registration(user_id):
        user = User.query.get_or_404(user_id)
        if user.username == ADMIN_USERNAME:
            flash("内置超级管理员不能被拒绝。", "error")
            return redirect(url_for("registrations"))
        user.status = "disabled"
        db.session.commit()
        flash("注册申请已拒绝。", "success")
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
            flash("你今天已经签到。", "success")
            return redirect(url_for("checkin"))
        db.session.add(CheckIn(user_id=g.current_user.id))
        db.session.commit()
        flash("签到已记录。", "success")
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
            employee_no = (
                row.get("employee_no")
                or row.get("number")
                or row.get("员工编号")
                or row.get("编号")
                or ""
            ).strip()
            name = (row.get("name") or row.get("姓名") or "").strip()
            department = (
                row.get("department") or row.get("部门") or ""
            ).strip()
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

    @app.get("/employees/export.csv")
    @permission_required("employee.view")
    def export_employees():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["员工编号", "姓名", "部门", "可参与抽奖", "创建时间"])
        for employee in Employee.query.order_by(
            Employee.department,
            Employee.employee_no,
        ).all():
            writer.writerow(
                [
                    employee.employee_no,
                    employee.name,
                    employee.department,
                    "是" if employee.eligible else "否",
                    employee.created_at.isoformat(),
                ]
            )
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=employees.csv"},
        )

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
        writer.writerow(["奖项", "员工编号", "姓名", "部门", "抽奖时间"])
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
