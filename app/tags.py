#!/usr/bin/env python3
"""Hashtag inbox cho ShopDesk — gắn tag thủ công/tự động lên hội thoại Messenger.

Tag là các nhãn ngắn giúp nhân viên lọc và nhận diện trạng thái hội thoại
(chưa chốt, thiếu địa chỉ, đã chốt đơn, đã đẩy sang ĐVVC...). Lưu ở SQLite
bảng conversation_tags, không động vào dữ liệu inbox của Meta.
"""
import os
import re
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from . import db as db_mod

tags_bp = Blueprint("tags", __name__)

# Định nghĩa tag chuẩn: tag -> (label hiển thị, màu badge)
TAG_DEFS = {
    "chot_don": ("Chốt đơn", "#16a34a"),
    "chua_chot": ("Chưa chốt", "#d97706"),
    "thieu_dia_chi": ("Thiếu địa chỉ", "#dc2626"),
    "thieu_sdt": ("Thiếu SĐT", "#dc2626"),
    "da_chot_don": ("Đã chốt đơn", "#2563eb"),
    "da_day_dvvc": ("Đã đẩy sang ĐVVC", "#7c3aed"),
}

CUSTOM_TAG_RE = re.compile(r"^[a-z0-9_]{1,30}$")
CUSTOM_COLOR = "#6b7280"


def init_conversation_tags():
    """Tạo bảng conversation_tags nếu chưa có (idempotent)."""
    conn = db_mod._connect()
    try:
        conn.executescript(
            """
CREATE TABLE IF NOT EXISTS conversation_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id TEXT NOT NULL DEFAULT '',
    thread_id TEXT NOT NULL DEFAULT '',
    tag TEXT NOT NULL DEFAULT '',
    created_at TEXT DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ctag_unique
    ON conversation_tags(page_id, thread_id, tag);
CREATE INDEX IF NOT EXISTS idx_ctag_tag ON conversation_tags(tag);
CREATE INDEX IF NOT EXISTS idx_ctag_page ON conversation_tags(page_id, thread_id);
"""
        )
        # Migration: cột source ('auto'|'manual') cho tag tự động từ daemon
        try:
            conn.execute("ALTER TABLE conversation_tags ADD COLUMN source TEXT DEFAULT 'manual'")
        except Exception:
            pass  # cột đã tồn tại
        conn.commit()
    finally:
        conn.close()


def validate_tag(tag):
    """Chuẩn hóa và kiểm tra tag.

    - Nằm trong TAG_DEFS → giữ nguyên.
    - Custom: chỉ chữ thường, số, gạch dưới, tối đa 30 ký tự.
    - Sai → ValueError tiếng Việt.
    """
    t = str(tag or "").strip().lower()
    if not t:
        raise ValueError("Tag không được để trống.")
    if t in TAG_DEFS:
        return t
    if not CUSTOM_TAG_RE.match(t):
        raise ValueError(
            "Tag chỉ gồm chữ thường, số và gạch dưới, tối đa 30 ký tự."
        )
    return t


def tag_label_color(tag):
    """(label, color) cho một tag hợp lệ."""
    t = validate_tag(tag)
    if t in TAG_DEFS:
        return TAG_DEFS[t]
    return t, CUSTOM_COLOR


# ---- Helpers dữ liệu (coordinator / auto-tag gọi trực tiếp) ----

def add_tag(page_id, thread_id, tag, source="manual"):
    """Gắn tag cho hội thoại. Idempotent — đã có thì không sao.

    source: 'manual' (nhân viên gắn tay) | 'auto' (hệ thống tự gắn).
    """
    t = validate_tag(tag)
    if source not in ("auto", "manual"):
        source = "manual"
    conn = db_mod._connect()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO conversation_tags "
            "(page_id, thread_id, tag, source, created_at) VALUES (?,?,?,?,?)",
            (
                str(page_id or ""),
                str(thread_id or ""),
                t,
                source,
                db_mod._now(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def remove_tag(page_id, thread_id, tag):
    """Gỡ tag khỏi hội thoại. Không có thì vẫn ok."""
    t = validate_tag(tag)
    conn = db_mod._connect()
    try:
        conn.execute(
            "DELETE FROM conversation_tags WHERE page_id = ? AND thread_id = ? AND tag = ?",
            (str(page_id or ""), str(thread_id or ""), t),
        )
        conn.commit()
    finally:
        conn.close()


def get_thread_tags(page_id, thread_id):
    """Danh sách [{tag, label, color, source}] của một hội thoại."""
    conn = db_mod._connect()
    try:
        rows = conn.execute(
            "SELECT tag, source FROM conversation_tags WHERE page_id = ? AND thread_id = ? "
            "ORDER BY created_at, tag",
            (str(page_id or ""), str(thread_id or "")),
        ).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        label, color = tag_label_color(r["tag"])
        out.append({"tag": r["tag"], "label": label, "color": color,
                    "source": r["source"] or "manual"})
    return out


def parse_source_thread(s):
    """s dạng 'fb:{page_id}/{conv_id}' → (page_id, conv_id), hoặc (None, None)."""
    if not isinstance(s, str):
        return None, None
    s = s.strip()
    if not s.startswith("fb:"):
        return None, None
    rest = s[3:].strip()
    if "/" not in rest:
        return None, None
    page_id, conv_id = rest.split("/", 1)
    page_id, conv_id = page_id.strip(), conv_id.strip()
    if not page_id or not conv_id:
        return None, None
    return page_id, conv_id


def _tag_row_with_meta(row):
    label, color = tag_label_color(row["tag"])
    return {
        "page_id": row["page_id"],
        "thread_id": row["thread_id"],
        "tag": row["tag"],
        "label": label,
        "color": color,
        "source": (row["source"] if "source" in row.keys() else None) or "manual",
        "created_at": row["created_at"],
    }


def _err(msg, code=400):
    return jsonify({"ok": False, "error_vi": msg}), code


# ---- API ----

@tags_bp.get("/api/inbox/tag-defs")
def list_tag_defs():
    defs = {t: {"label": label, "color": color} for t, (label, color) in TAG_DEFS.items()}
    return jsonify({"defs": defs})


@tags_bp.get("/api/inbox/tags")
def list_tags():
    tag = request.args.get("tag") or ""
    page_id = request.args.get("page_id") or ""
    _maybe_auto_sync()
    clauses, params = [], []
    if tag:
        try:
            clauses.append("tag = ?")
            params.append(validate_tag(tag))
        except ValueError as e:
            return _err(str(e))
    if page_id:
        clauses.append("page_id = ?")
        params.append(page_id)
    sql = "SELECT * FROM conversation_tags"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC"
    conn = db_mod._connect()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return jsonify({"tags": [_tag_row_with_meta(r) for r in rows]})


@tags_bp.get("/api/inbox/tags/by-page/<page_id>")
def tags_by_page(page_id):
    """Toàn bộ tag của một page, gom theo thread_id — 1 request để render badge."""
    _maybe_auto_sync()
    conn = db_mod._connect()
    try:
        rows = conn.execute(
            "SELECT thread_id, tag, source FROM conversation_tags WHERE page_id = ? "
            "ORDER BY thread_id, created_at",
            (str(page_id or ""),),
        ).fetchall()
    finally:
        conn.close()
    threads = {}
    for r in rows:
        label, color = tag_label_color(r["tag"])
        threads.setdefault(r["thread_id"], []).append(
            {"tag": r["tag"], "label": label, "color": color,
             "source": r["source"] or "manual"}
        )
    return jsonify({"threads": threads})


@tags_bp.get("/api/inbox/<page_id>/<thread_id>/tags")
def thread_tags(page_id, thread_id):
    return jsonify({"tags": get_thread_tags(page_id, thread_id)})


@tags_bp.post("/api/inbox/<page_id>/<thread_id>/tags")
def attach_tag(page_id, thread_id):
    body = request.get_json(silent=True) or {}
    tag = body.get("tag") or ""
    try:
        add_tag(page_id, thread_id, tag)
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err("Không gắn được tag. Vui lòng thử lại.", 500)
    return jsonify({"ok": True})


@tags_bp.delete("/api/inbox/<page_id>/<thread_id>/tags")
def detach_tag(page_id, thread_id):
    body = request.get_json(silent=True) or {}
    tag = body.get("tag") or request.args.get("tag") or ""
    try:
        remove_tag(page_id, thread_id, tag)
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err("Không gỡ được tag. Vui lòng thử lại.", 500)
    return jsonify({"ok": True})


# ---- Đồng bộ tag tự động từ log của automation (daemon/cron) ----
# Đọc READ-ONLY các file của hệ thống automation Muse:
#   ~/workspace/custom-connectors/custom.meta-page-inbox/hidden_files/         (Dép Hana)
#   ~/workspace/custom-connectors/custom.meta-page-inbox-bedan/hidden_files/   (Bé Đan)
# Nguồn: inbox_state.json -> closed_order_ids; inbox_log_YYYY-MM-DD.jsonl ->
# dòng hanh_dong == "instant_close" (lấy cid). Thread nào automation đã chốt
# đơn thì tự gắn tag "da_chot_don" với source='auto' (hiển thị icon 🤖).

_AUTO_SOURCES = [
    ("custom.meta-page-inbox", "441747482366131"),        # Dép Hana
    ("custom.meta-page-inbox-bedan", "209825435542158"),  # Shop Bé Đan
]

_last_auto_sync = None
_AUTO_SYNC_INTERVAL = timedelta(minutes=5)


def _read_closed_threads():
    """Quét file automation, trả về set {(page_id, thread_id)} đã chốt đơn."""
    import json

    found = set()
    base = os.path.expanduser("~/workspace/custom-connectors")
    today = datetime.now()
    dates = [today.strftime("%Y-%m-%d"), (today - timedelta(days=1)).strftime("%Y-%m-%d")]
    for dirname, page_id in _AUTO_SOURCES:
        hdir = os.path.join(base, dirname, "hidden_files")
        # Nguồn 1: closed_order_ids trong inbox_state.json
        try:
            with open(os.path.join(hdir, "inbox_state.json"), "r", encoding="utf-8") as f:
                state = json.load(f)
            for cid in state.get("closed_order_ids") or []:
                if cid:
                    found.add((page_id, str(cid)))
        except (OSError, ValueError):
            pass  # file chưa tồn tại / hỏng → bỏ qua
        # Nguồn 2: dòng instant_close trong log hôm nay + hôm qua
        for d in dates:
            try:
                with open(os.path.join(hdir, f"inbox_log_{d}.jsonl"), "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or "instant_close" not in line:
                            continue
                        try:
                            entry = json.loads(line)
                        except ValueError:
                            continue
                        if entry.get("hanh_dong") == "instant_close" and entry.get("cid"):
                            found.add((page_id, str(entry["cid"])))
            except (OSError, ValueError):
                pass
    return found


def sync_auto_tags(force=False):
    """Gắn tag 'da_chot_don' (source='auto') cho thread automation đã chốt.

    Idempotent, không quét lại nếu chưa quá 5 phút (trừ force=True).
    Trả về số tag mới được thêm. Không bao giờ ném exception ra ngoài.
    """
    global _last_auto_sync
    now = datetime.now()
    if not force and _last_auto_sync and (now - _last_auto_sync) < _AUTO_SYNC_INTERVAL:
        return 0
    added = 0
    try:
        for page_id, thread_id in _read_closed_threads():
            try:
                existing = {t["tag"] for t in get_thread_tags(page_id, thread_id)}
                if "da_chot_don" not in existing:
                    add_tag(page_id, thread_id, "da_chot_don", source="auto")
                    added += 1
            except Exception:
                continue
        _last_auto_sync = now
    except Exception:
        pass
    return added


def _maybe_auto_sync():
    """Đồng bộ ngầm trước khi trả danh sách tag — lỗi thì bỏ qua."""
    try:
        sync_auto_tags()
    except Exception:
        pass


@tags_bp.post("/api/inbox/tags/sync-auto")
def sync_auto_endpoint():
    """Đồng bộ thủ công tag tự động từ log automation."""
    try:
        added = sync_auto_tags(force=True)
    except Exception:
        return _err("Không đồng bộ được tag tự động. Vui lòng thử lại.", 500)
    return jsonify({"ok": True, "added": added})


# ---- Auto-tag khi nhân viên tạo đơn / tạo vận đơn từ thread trong ShopDesk ----
# (source='manual' vì đây là thao tác của nhân viên; 'auto' chỉ dành cho daemon)

def auto_tag_order_created(source_thread):
    """Đơn mới tạo từ thread → gắn 'chot_don'."""
    page_id, thread_id = parse_source_thread(source_thread)
    if page_id and thread_id:
        try:
            add_tag(page_id, thread_id, "chot_don", source="manual")
        except Exception:
            pass


def auto_tag_shipped(source_thread):
    """Đã tạo vận đơn cho đơn từ thread → gắn 'da_day_dvvc', gỡ 'chua_chot'."""
    page_id, thread_id = parse_source_thread(source_thread)
    if page_id and thread_id:
        try:
            add_tag(page_id, thread_id, "da_day_dvvc", source="manual")
            remove_tag(page_id, thread_id, "chua_chot")
        except Exception:
            pass
