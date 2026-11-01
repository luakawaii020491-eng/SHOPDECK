#!/usr/bin/env python3
"""Client Meta Graph API v21.0 cho ShopDesk.

Pattern copy từ connector custom.meta-page-inbox (bin/page_inbox.py):
- Gửi tin: POST /me/messages, messaging_type="RESPONSE", recipient.id = PSID khách
- Đọc: /{page_id}/conversations, /{conv_id}/messages
- Gửi ảnh 2 bước: POST /me/message_attachments (multipart filedata) → attachment_id
  → POST /me/messages với attachment_id.

Lỗi Meta được dịch sang tiếng Việt ở _translate_error().
"""
import json
import mimetypes
import os

import requests

API = "https://graph.facebook.com/v21.0"
TIMEOUT = 30  # giây cho mọi call Meta


class MetaAPIError(Exception):
    """Lỗi Meta đã dịch sang tiếng Việt."""

    def __init__(self, error_vi, raw=None):
        super().__init__(error_vi)
        self.error_vi = error_vi
        self.raw = raw


def _translate_error(payload):
    err = (payload or {}).get("error", {}) or {}
    code = err.get("code")
    subcode = err.get("error_subcode")
    msg = err.get("message") or ""
    if code == 10 and subcode == 2018300:
        return ("Thread đang bị app khác giữ (VD: chatbot Sapo). "
                "Hãy trả lời tay trong Meta Business Suite.")
    if code == 190:
        return "Token page đã hết hạn. Vào Cài đặt để nhập token mới."
    short = msg[:200] if msg else "Lỗi không xác định từ Meta."
    return f"Lỗi Meta (#{code}): {short}"


class MetaPageClient:
    """Client cho 1 fanpage. Token KHÔNG bao giờ được log."""

    def __init__(self, page_id, token):
        self.page_id = str(page_id)
        self.token = token or ""

    def _request(self, method, path, params=None, json_body=None, data=None, files=None):
        url = API + path
        q = dict(params or {})
        q["access_token"] = self.token
        try:
            resp = requests.request(
                method, url, params=q, json=json_body, data=data, files=files,
                timeout=TIMEOUT,
            )
        except requests.RequestException as e:
            raise MetaAPIError(f"Không kết nối được tới Meta: {e.__class__.__name__}")
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        if resp.status_code >= 400 or (isinstance(payload, dict) and "error" in payload):
            raise MetaAPIError(_translate_error(payload), raw=payload)
        return payload if isinstance(payload, dict) else {}

    # ---- Đọc ----

    def conversations(self, limit=25):
        """GET /{page_id}/conversations."""
        return self._request(
            "GET", f"/{self.page_id}/conversations",
            params={
                "fields": "id,updated_time,message_count,unread_count,participants",
                "limit": int(limit or 25),
            },
        )

    def messages(self, conv_id, limit=30):
        """GET /{conv_id}/messages."""
        return self._request(
            "GET", f"/{conv_id}/messages",
            params={
                "fields": "id,message,from,to,created_time,attachments",
                "limit": int(limit or 30),
            },
        )

    # ---- Gửi ----

    def send_text(self, psid, text):
        """POST /me/messages — trả về message_id. KHÔNG thêm chữ ký."""
        payload = self._request(
            "POST", "/me/messages",
            json_body={
                "recipient": {"id": str(psid)},
                "messaging_type": "RESPONSE",
                "message": {"text": text},
            },
        )
        return payload.get("message_id")

    def send_image(self, psid, local_image_path):
        """Gửi ảnh 2 bước, trả về message_id. KHÔNG thêm chữ ký."""
        if not os.path.isfile(local_image_path):
            raise MetaAPIError(f"Không tìm thấy file ảnh: {os.path.basename(local_image_path)}")
        fname = os.path.basename(local_image_path)
        mime = mimetypes.guess_type(local_image_path)[0] or "image/jpeg"
        with open(local_image_path, "rb") as f:
            up = self._request(
                "POST", "/me/message_attachments",
                data={
                    "message": json.dumps({
                        "attachment": {"type": "image", "payload": {"is_reusable": True}}
                    })
                },
                files={"filedata": (fname, f, mime)},
            )
        att_id = up.get("attachment_id")
        if not att_id:
            raise MetaAPIError("Upload ảnh thất bại (Meta không trả attachment_id).", raw=up)
        payload = self._request(
            "POST", "/me/messages",
            json_body={
                "recipient": {"id": str(psid)},
                "messaging_type": "RESPONSE",
                "message": {
                    "attachment": {
                        "type": "image",
                        "payload": {"attachment_id": att_id},
                    }
                },
            },
        )
        return payload.get("message_id")
