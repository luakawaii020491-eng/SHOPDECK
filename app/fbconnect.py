#!/usr/bin/env python3
"""Luồng "Kết nối Facebook" kiểu Sapo cho ShopDesk.

User bấm "Kết nối Facebook" → OAuth đăng nhập Facebook → app quét các page
mà tài khoản quản lý (/me/accounts) → user tick chọn page nào được phép dùng
trong ShopDesk → lưu page_id + page token (kiểm tra token thật trước khi lưu,
giống luồng thêm page thủ công).

Yêu cầu chuẩn bị một lần (hướng dẫn ở trang Cài đặt):
  1. Có Facebook App (VD: app LuaKawaii) — lấy App ID + App Secret tại
     developers.facebook.com → ứng dụng → Cài đặt → Cơ bản.
  2. Thêm redirect URI (hiện ở trang Cài đặt) vào "Valid OAuth Redirect URIs"
     (Sản phẩm → Facebook Login → Cài đặt).
  3. Tài khoản Facebook dùng để kết nối phải có vai trò trong app (khi app còn
     ở chế độ Development) — đúng như tài khoản chủ shop vẫn dùng.
"""
import json
import secrets
import time
import urllib.parse
import urllib.request

from flask import Blueprint, jsonify, redirect, render_template, request

from . import config as config_mod
from .meta_client import MetaAPIError, MetaPageClient

fbconnect_bp = Blueprint("fbconnect", __name__)

GRAPH = "https://graph.facebook.com/v21.0"
OAUTH_SCOPES = "pages_show_list,pages_read_engagement,pages_messaging"

# Bộ nhớ tạm trong tiến trình (đủ dùng cho luồng OAuth vài phút)
_oauth_states = {}   # state -> expires_at
_fb_sessions = {}    # key -> {"pages": [...], "expires_at": ...}


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


def _redirect_uri():
    return request.host_url.rstrip("/") + "/connect/facebook/callback"


def _http_get_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "ShopDesk/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _prune():
    now = time.time()
    for store in (_oauth_states, _fb_sessions):
        for k in [k for k, v in store.items()
                  if (v if isinstance(v, (int, float)) else v.get("expires_at", 0)) < now]:
            store.pop(k, None)


@fbconnect_bp.get("/api/connect/facebook/app")
def fb_app_status():
    fb = config_mod.get_fb_app(masked=True)
    return jsonify({
        "ok": True,
        "app_id": fb.get("app_id") or "",
        "app_secret_set": bool((config_mod.get_fb_app() or {}).get("app_secret")),
        "redirect_uri": _redirect_uri(),
    })


@fbconnect_bp.post("/api/connect/facebook/app")
def fb_app_save():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return _err("Dữ liệu không hợp lệ.")
    app_id = str(body.get("app_id") or "").strip()
    app_secret = str(body.get("app_secret") or "").strip()
    fields = {"app_id": app_id}
    if "•" in app_secret:
        pass  # user giữ nguyên mask → không động vào secret đã lưu
    elif app_secret:
        fields["app_secret"] = app_secret   # secret mới
    else:
        fields["app_secret"] = ""           # xóa trắng → gỡ secret
    saved = config_mod.set_fb_app(fields)
    return jsonify({"ok": True, "saved": saved, "redirect_uri": _redirect_uri()})


@fbconnect_bp.get("/api/connect/facebook/start")
def fb_start():
    """Trả về URL OAuth để frontend chuyển hướng sang Facebook."""
    _prune()
    fb = config_mod.get_fb_app() or {}
    app_id = (fb.get("app_id") or "").strip()
    app_secret = (fb.get("app_secret") or "").strip()
    if not app_id or not app_secret:
        return _err("Chưa nhập App ID / App Secret ở mục Kết nối Facebook (trang Cài đặt).")
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = time.time() + 600
    params = urllib.parse.urlencode({
        "client_id": app_id,
        "redirect_uri": _redirect_uri(),
        "scope": OAUTH_SCOPES,
        "response_type": "code",
        "state": state,
    })
    return jsonify({"ok": True, "url": f"https://www.facebook.com/v21.0/dialog/oauth?{params}"})


@fbconnect_bp.get("/connect/facebook/callback")
def fb_callback():
    """Facebook chuyển về đây sau khi user đồng ý. Đổi code lấy user token,
    quét /me/accounts rồi chuyển sang màn hình chọn page (không đưa token ra browser)."""
    _prune()
    err = request.args.get("error")
    if err:
        msg = request.args.get("error_description") or err
        return render_template("fb_error.html", message=f"Facebook từ chối kết nối: {msg}"), 400
    code = (request.args.get("code") or "").strip()
    state = (request.args.get("state") or "").strip()
    if not code or state not in _oauth_states:
        return render_template("fb_error.html",
                               message="Phiên kết nối hết hạn hoặc không hợp lệ. Thử bấm 'Kết nối Facebook' lại."), 400
    _oauth_states.pop(state, None)

    fb = config_mod.get_fb_app() or {}
    app_id = (fb.get("app_id") or "").strip()
    app_secret = (fb.get("app_secret") or "").strip()
    try:
        token_qs = urllib.parse.urlencode({
            "client_id": app_id,
            "redirect_uri": _redirect_uri(),
            "client_secret": app_secret,
            "code": code,
        })
        tok = _http_get_json(f"{GRAPH}/oauth/access_token?{token_qs}")
        user_token = tok.get("access_token") or ""
        if not user_token:
            raise ValueError("Facebook không trả về access token.")
        acc_qs = urllib.parse.urlencode({
            "fields": "id,name,access_token",
            "limit": 100,
            "access_token": user_token,
        })
        acc = _http_get_json(f"{GRAPH}/me/accounts?{acc_qs}")
        pages = [
            {"page_id": str(p.get("id") or ""), "name": p.get("name") or "",
             "token": p.get("access_token") or ""}
            for p in (acc.get("data") or []) if p.get("id") and p.get("access_token")
        ]
    except Exception as e:
        return render_template("fb_error.html",
                               message=f"Không lấy được danh sách page: {e}. "
                                       "Kiểm tra lại App Secret và redirect URI đã whitelist trong Facebook Login."), 502

    key = secrets.token_urlsafe(24)
    _fb_sessions[key] = {"pages": pages, "expires_at": time.time() + 900}
    return redirect(f"/connect/facebook/pages?key={key}", code=302)


@fbconnect_bp.get("/connect/facebook/pages")
def fb_pages_view():
    key = (request.args.get("key") or "").strip()
    sess = _fb_sessions.get(key)
    if not sess or sess.get("expires_at", 0) < time.time():
        return render_template("fb_error.html",
                               message="Phiên chọn page đã hết hạn. Thử kết nối lại từ trang Cài đặt."), 400
    return render_template("fb_pages.html", fb_key=key, page_count=len(sess["pages"]))


@fbconnect_bp.get("/api/connect/facebook/pages")
def fb_pages_list():
    """Danh sách page quét được — KHÔNG kèm token (token giữ ở server)."""
    _prune()
    key = (request.args.get("key") or "").strip()
    sess = _fb_sessions.get(key)
    if not sess:
        return _err("Phiên chọn page đã hết hạn. Kết nối lại.", 410)
    return jsonify({"ok": True, "pages": [
        {"page_id": p["page_id"], "name": p["name"]} for p in sess["pages"]
    ]})


@fbconnect_bp.post("/api/connect/facebook/save")
def fb_pages_save():
    """Lưu các page user đã tick — kiểm tra token thật từng page như luồng thủ công."""
    _prune()
    body = request.get_json(silent=True) or {}
    key = str((body or {}).get("key") or "").strip()
    want = (body or {}).get("page_ids") or []
    sess = _fb_sessions.get(key)
    if not sess:
        return _err("Phiên chọn page đã hết hạn. Kết nối lại.", 410)
    by_id = {p["page_id"]: p for p in sess["pages"]}
    results = []
    for pid in want:
        pid = str(pid)
        p = by_id.get(pid)
        if not p:
            results.append({"page_id": pid, "ok": False, "error_vi": "Page không nằm trong danh sách vừa quét."})
            continue
        try:
            MetaPageClient(pid, p["token"]).conversations(limit=1)
        except MetaAPIError as e:
            results.append({"page_id": pid, "name": p["name"], "ok": False,
                            "error_vi": f"Token không dùng được: {e.error_vi}"})
            continue
        except Exception:
            results.append({"page_id": pid, "name": p["name"], "ok": False,
                            "error_vi": "Không kiểm tra được token (lỗi mạng)."})
            continue
        try:
            config_mod.add_page(pid, p["name"], p["token"])
        except Exception as e:
            results.append({"page_id": pid, "name": p["name"], "ok": False,
                            "error_vi": f"Không lưu được: {e}"})
            continue
        results.append({"page_id": pid, "name": p["name"], "ok": True})
    _fb_sessions.pop(key, None)  # dùng 1 lần
    return jsonify({"ok": True, "results": results})
