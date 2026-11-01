#!/usr/bin/env python3
"""Routes /api/pages* — inbox Meta cho 2 fanpage (Dép Hana & Bé Đan).

Tin nhắn gửi từ app KHÔNG thêm chữ ký.
"""
import os

import requests
from flask import Blueprint, jsonify, request, Response

from . import config as config_mod
from .meta_client import MetaAPIError, MetaPageClient

pages_bp = Blueprint("pages", __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


def _client_for(page_id):
    page = config_mod.get_page(page_id)
    if not page:
        return None, _err("Chưa cấu hình page này. Vào Cài đặt để thêm page.")
    if not page.get("token"):
        return None, _err("Page chưa có token. Vào Cài đặt để nhập token mới.")
    return MetaPageClient(page["page_id"], page["token"]), None


def _customer_info(conv, page_id):
    """Tên khách = participant không phải page."""
    name = "Khách"
    try:
        for p in (conv.get("participants") or {}).get("data", []):
            if str(p.get("id")) != str(page_id):
                name = p.get("name") or "Khách"
                break
    except (AttributeError, TypeError):
        pass
    return name


def _latest_messages(client, conv_id, limit=10):
    try:
        data = client.messages(conv_id, limit=limit)
        return (data.get("data") or [])
    except MetaAPIError:
        return []


@pages_bp.get("/api/pages")
def list_pages():
    pages = []
    for p in config_mod.list_pages():
        pid = p.get("page_id")
        entry = {"page_id": pid, "name": p.get("name") or "", "status": "ok", "status_msg": ""}
        try:
            client = MetaPageClient(pid, p.get("token") or "")
            client.conversations(limit=1)
        except MetaAPIError as e:
            entry["status"] = "error"
            entry["status_msg"] = e.error_vi
        except Exception as e:
            entry["status"] = "error"
            entry["status_msg"] = f"Lỗi không xác định: {e.__class__.__name__}"
        pages.append(entry)
    return jsonify({"pages": pages})


@pages_bp.post("/api/pages")
def add_page():
    body = request.get_json(silent=True) or {}
    page_id = str(body.get("page_id") or "").strip()
    name = str(body.get("name") or "").strip()
    token = str(body.get("token") or "").strip()
    if not page_id or not token:
        return _err("Thiếu page_id hoặc token.")
    # Kiểm tra token thật trước khi lưu
    try:
        MetaPageClient(page_id, token).conversations(limit=1)
    except MetaAPIError as e:
        return jsonify({"ok": False, "error_vi": f"Token không dùng được: {e.error_vi}"})
    except Exception:
        return jsonify({"ok": False, "error_vi": "Không kiểm tra được token (lỗi mạng). Thử lại sau."})
    config_mod.add_page(page_id, name, token)
    return jsonify({"ok": True})


@pages_bp.delete("/api/pages/<page_id>")
def delete_page(page_id):
    config_mod.delete_page(page_id)
    return jsonify({"ok": True})


@pages_bp.get("/api/pages/<page_id>/conversations")
def list_conversations(page_id):
    client, err = _client_for(page_id)
    if err:
        return err
    limit = request.args.get("limit", 25)
    try:
        limit = max(1, min(50, int(limit)))
    except (TypeError, ValueError):
        limit = 25
    try:
        data = client.conversations(limit=limit)
    except MetaAPIError as e:
        return jsonify({"ok": False, "error_vi": e.error_vi})
    page_name = (config_mod.get_page(page_id) or {}).get("name") or ""
    conversations = []
    for conv in data.get("data") or []:
        cid = conv.get("id")
        name = _customer_info(conv, page_id)
        msgs = _latest_messages(client, cid, limit=10)
        # psid: from_id của tin nhắn gần nhất KHÔNG phải của page
        # (bỏ qua tin auto-greeting của page). Chưa có tin khách → null.
        psid = None
        snippet = ""
        for m in msgs:
            frm = m.get("from") or {}
            if str(frm.get("id")) != str(page_id):
                if psid is None:
                    psid = str(frm.get("id"))
            if not snippet and m.get("message"):
                snippet = m["message"]
        conversations.append({
            "id": cid,
            "name": name,
            "page_name": page_name,
            "psid": psid,
            "snippet": snippet[:160],
            "updated_time": conv.get("updated_time") or "",
            "unread": conv.get("unread_count") or 0,
            # True khi tin mới nhất là của KHÁCH (page chưa trả lời) → frontend in đậm
            "needs_reply": _needs_reply(msgs, page_id),
        })
    return jsonify({"conversations": conversations})


def _needs_reply(msgs, page_id):
    """Tin mới nhất có phải của khách không.

    Bỏ qua tin auto-greeting của Facebook (sender chứa "business").
    msgs: list mới nhất trước (Graph API). Trả False khi không có tin nào.
    """
    try:
        for m in msgs or []:
            frm = m.get("from") or {}
            fid = str(frm.get("id") or "")
            if not fid:
                continue
            sender_name = str(frm.get("name") or "").lower()
            if "business" in sender_name:
                continue  # auto-greeting của Facebook, không tính là đã trả lời
            return fid != str(page_id)
    except (AttributeError, TypeError):
        pass
    return False


def _attachment_url(att):
    payload = att.get("payload") or {}
    url = payload.get("url")
    if not url:
        url = (payload.get("image_data") or {}).get("url")
    if not url:
        url = payload.get("file_url")
    return url


@pages_bp.get("/api/pages/<page_id>/conversations/<conv_id>/messages")
def list_messages(page_id, conv_id):
    client, err = _client_for(page_id)
    if err:
        return err
    limit = request.args.get("limit", 30)
    try:
        limit = max(1, min(100, int(limit)))
    except (TypeError, ValueError):
        limit = 30
    try:
        data = client.messages(conv_id, limit=limit)
    except MetaAPIError as e:
        return jsonify({"ok": False, "error_vi": e.error_vi})
    messages = []
    for m in data.get("data") or []:
        frm = m.get("from") or {}
        atts = []
        try:
            for att in (m.get("attachments") or {}).get("data", []):
                url = _attachment_url(att)
                if url:
                    atts.append({"type": att.get("type") or "file", "url": url})
        except (AttributeError, TypeError):
            pass
        messages.append({
            "id": m.get("id"),
            "from_id": str(frm.get("id") or ""),
            "from_name": frm.get("name") or "",
            "text": m.get("message") or "",
            "attachments": atts,
            "created_time": m.get("created_time") or "",
            "mine": str(frm.get("id")) == str(page_id),
        })
    return jsonify({"messages": messages})


@pages_bp.post("/api/pages/<page_id>/send")
def send_text(page_id):
    client, err = _client_for(page_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    psid = str(body.get("psid") or "").strip()
    text = str(body.get("text") or "")
    if not psid:
        return _err("Thiếu PSID người nhận.")
    if not text.strip():
        return _err("Tin nhắn trống.")
    try:
        message_id = client.send_text(psid, text)  # KHÔNG thêm chữ ký
        return jsonify({"ok": True, "message_id": message_id})
    except MetaAPIError as e:
        return jsonify({"ok": False, "error_vi": e.error_vi})
    except Exception as e:
        return jsonify({"ok": False, "error_vi": f"Lỗi không xác định: {e.__class__.__name__}"})


@pages_bp.post("/api/pages/<page_id>/send_image")
def send_image(page_id):
    client, err = _client_for(page_id)
    if err:
        return err
    body = request.get_json(silent=True) or {}
    psid = str(body.get("psid") or "").strip()
    image = str(body.get("image") or "").strip()
    if not psid:
        return _err("Thiếu PSID người nhận.")
    if not image:
        return _err("Thiếu tên file ảnh.")
    # Chặn path traversal — chỉ cho phép file nằm trực tiếp trong static/
    safe_name = os.path.basename(image)
    local_path = os.path.realpath(os.path.join(STATIC_DIR, safe_name))
    if not local_path.startswith(os.path.realpath(STATIC_DIR) + os.sep):
        return _err("Tên file ảnh không hợp lệ.")
    if not os.path.isfile(local_path):
        return _err(f"Không tìm thấy ảnh '{safe_name}' trong static/.")
    try:
        message_id = client.send_image(psid, local_path)  # KHÔNG thêm chữ ký
        return jsonify({"ok": True, "message_id": message_id})
    except MetaAPIError as e:
        return jsonify({"ok": False, "error_vi": e.error_vi})
    except Exception as e:
        return jsonify({"ok": False, "error_vi": f"Lỗi không xác định: {e.__class__.__name__}"})


@pages_bp.get("/api/assets")
def list_assets():
    """Danh sách ảnh gửi nhanh: hana = dép sục khoét lỗ, bedan = dép sục đế 3 phân."""
    hana, bedan = [], []
    try:
        files = sorted(os.listdir(STATIC_DIR))
    except OSError:
        files = []
    for f in files:
        if not f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            continue
        if "3phan" in f:
            bedan.append(f)
        else:
            hana.append(f)
    return jsonify({"hana": hana, "bedan": bedan})


@pages_bp.get("/api/media")
def media_proxy():
    """Proxy ảnh đính kèm Messenger (tránh lỗi hotlink/CORS ở frontend)."""
    url = request.args.get("url", "")
    if not url.startswith("https://"):
        return _err("URL ảnh không hợp lệ.")
    try:
        resp = requests.get(url, timeout=30, stream=True)
    except requests.RequestException:
        return _err("Không tải được ảnh.")
    if resp.status_code != 200:
        return _err("Không tải được ảnh.")
    ctype = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    if not ctype.startswith(("image/", "video/", "audio/")):
        return _err("URL không phải media.")
    return Response(resp.iter_content(chunk_size=65536), content_type=ctype)
