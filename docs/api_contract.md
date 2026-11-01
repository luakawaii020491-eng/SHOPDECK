# ShopDesk — Hợp đồng API (backend ↔ frontend)

Tất cả JSON, tiếng Việt cho message lỗi. Base: `http://localhost:8000`.

## Trang
- `GET /` → inbox (templates/inbox.html)
- `GET /orders` → đơn hàng (templates/orders.html)
- `GET /products` → sản phẩm (templates/products.html)
- `GET /customers` → khách hàng (templates/customers.html)
- `GET /settings` → cài đặt (templates/settings.html)

## Pages (Meta)
- `GET /api/pages` → `{pages: [{page_id, name, status: "ok"|"error", status_msg}]}`.
  `status` được kiểm tra bằng 1 lệnh `GET /{page_id}/conversations?limit=1`.
- `POST /api/pages` body `{page_id, name, token}` → thêm page (token lưu trong config.json).
- `DELETE /api/pages/<page_id>` → xóa page.
- `GET /api/pages/<page_id>/conversations?limit=25` → `{conversations: [{id, name, page_name, psid, snippet, updated_time, unread, needs_reply}]}`.
  `needs_reply` = true khi tin mới nhất là của KHÁCH (page chưa trả lời) — frontend
  in đậm thread đó; bỏ qua tin auto-greeting của Facebook (sender "facebook business").
  `name` = tên khách (lấy từ participants), `page_name` = tên page để phân biệt shop.
  `psid` = PSID của KHÁCH trong thread (lấy từ `from_id` của tin nhắn gần nhất mà
  `from_id != page_id`, bỏ qua tin auto-greeting của page; `null` nếu thread chưa
  có tin khách) — frontend dùng `psid` này để gọi `/send` và `/send_image`.
- `GET /api/pages/<page_id>/conversations/<conv_id>/messages?limit=30` →
  `{messages: [{id, from_id, from_name, text, attachments:[{type,url}], created_time, mine: true|false}]}`
  `mine` = true nếu tin do page gửi. Ảnh đính kèm trả về URL (proxy qua `/api/media?url=...` nếu cần).
- `POST /api/pages/<page_id>/send` body `{psid, text}` →
  gọi `POST https://graph.facebook.com/v21.0/me/messages` với `messaging_type: "RESPONSE"`,
  `recipient: {id: psid}`, `message: {text}`. Trả `{ok: true, message_id}` hoặc `{ok: false, error_vi}`.
  **KHÔNG thêm chữ ký "- ⭐"** (chỉ automation mới ký).
- `POST /api/pages/<page_id>/send_image` body `{psid, image}` → upload ảnh từ static/ qua
  `message: {attachment: {type: "image", payload: {url: <public-or-file>}}}`.
  Thực tế: dùng 2 bước — POST `/me/message_attachments` (multipart filedata) lấy attachment_id,
  rồi gửi `attachment_id`. `image` là tên file trong static/ (VD `dep_suc_all.jpg`).
- `GET /api/assets` → `{hana: [file...], bedan: [file...]}` danh sách ảnh gửi nhanh.

Lỗi Meta dịch ra tiếng Việt:
- (#10, subcode 2018300) → "Thread đang bị app khác giữ (VD: chatbot Sapo). Hãy trả lời tay trong Meta Business Suite."
- (#190) → "Token page đã hết hạn. Vào Cài đặt để nhập token mới."
- còn lại → message gốc rút gọn.

## Đơn hàng (SQLite data/shopdesk.db, bảng orders)
Trường: `id, shop ("hana"|"bedan"), customer_name, phone, address, items (JSON text),
total (int, VND), status ("new"|"pending"|"shipped"|"done"|"cancelled"),
shipping_carrier (""|"ghn"|"ghtk"|"viettelpost"|"jt"|"best"), shipping_code,
notes, source_thread, created_at, updated_at`.

- `GET /api/orders?status=&shop=&q=` → `{orders: [...]}` (mới nhất trước).
  Lọc mở rộng: `has_phone=true|false` (Có SĐT / Thiếu SĐT), `date_from`/`date_to`
  (YYYY-MM-DD, theo created_at giờ VN), `tag=<tag>` (đơn có hashtag đó;
  `tag=__none__` = nhóm "Không có tag"), `sku=<chuỗi>` (đơn có chứa mã SKU trong items).
- `GET /api/orders/<id>` → `{order: {...}}`.
- `POST /api/orders` body các trường trên (trừ id) → `{ok, id}`. Tự động: upsert
  khách hàng theo SĐT; nếu có `source_thread` → gắn tag `chot_don` cho thread.
  (Không trừ tồn kho — muốn trừ kho thì dùng `/api/orders/quick`.)
- `POST /api/orders/quick` — chốt đơn nhanh từ SKU ("chốt đơn và lên đơn luôn"):
  body `{shop, customer_name, phone, address, items: [{sku, qty}], notes,
  source_thread, create_shipment: {carrier} | null}` →
  `{ok, order_id, total, shipping_code, shipment_error_vi}`.
  Luồng: kiểm tra SKU + tồn kho → tổng = Σ(giá SKU × SL) + ship (hana: 1 đôi +25k,
  ≥2 đôi free; bedan: 1 đôi +30k, ≥2 đôi free) → trừ kho → upsert khách → tạo đơn
  → gắn tag `chot_don` (nếu từ thread) → tạo vận đơn luôn nếu có `create_shipment`
  (lỗi hãng VC → đơn vẫn tạo, lỗi nằm ở `shipment_error_vi`).
  Lưu ý: Bé Đan 2 đôi theo công thức này = 98k (2×49k), giá bán lẻ cho khách là 99k.
- `PUT /api/orders/<id>` body partial → `{ok}`.
- `DELETE /api/orders/<id>` → `{ok}`.
- `GET /api/orders/export.csv` → CSV UTF-8 BOM, cột: ID, Shop, Ngày tạo, Khách hàng, SĐT,
  Địa chỉ, Mặt hàng, Tổng tiền, Trạng thái, Hãng VC, Mã vận đơn, Ghi chú.
- `GET /api/price_suggest?shop=hana|bedan&qty=N` → `{total, note}` gợi ý tổng tiền theo bảng giá:
  - hana: 1 đôi = 90000 (65k+25k ship); ≥2 đôi = 65000*N miễn ship.
  - bedan: 1 đôi = 79000 (49k+30k ship); 2 đôi = 99000 miễn ship; ≥3 đôi = 139000 miễn ship.

## Sản phẩm (SQLite, bảng products)

Seed sẵn 30 SKU khi bảng còn trống: Dép Hana "Dép sục khoét lỗ" 65k/đôi
(`HANA-SUC-DEN-37`...), Bé Đan "Dép sục đế 3 phân" 49k/đôi (`BEDAN-3P-KEM-38`...);
size 36–40, màu Đen/Nâu/Kem; stock NULL = không giới hạn.

Trường: `id, sku (UNIQUE), name, shop, color, size, price (int VND/đôi),
stock (int|NULL), image, note, created_at, updated_at`.

- `GET /api/products?q=&shop=` → `{products: [...]}` (tìm theo sku/name).
- `POST /api/products` body các trường → `{ok, id}` (sku trùng → 400).
- `GET /api/products/<id>` → `{product: {...}}`.
- `PUT /api/products/<id>` body partial → `{ok}`.
- `DELETE /api/products/<id>` → `{ok}`.

## Khách hàng (SQLite, bảng customers)

Trường: `id, name, phone, address, shop, notes, created_at, updated_at`.
`phone` UNIQUE (chuẩn hóa khi tra cứu: bỏ khoảng trắng/`-`/`.`).

- `GET /api/customers?q=` → `{customers: [...]}` (tìm theo tên/SĐT).
- `POST /api/customers` → `{ok, id, updated}` — SĐT đã tồn tại thì UPDATE thông
  tin mới nhất (`updated: true`).
- `GET /api/customers/<id>`, `PUT /api/customers/<id>`, `DELETE /api/customers/<id>`.
- `GET /api/customers/by-phone?phone=` → `{customer: {...}|null}` (dùng cho tự
  điền thông tin khách cũ khi tạo đơn).

## Hashtag inbox (SQLite, bảng conversation_tags)

Tag định nghĩa sẵn: `chot_don` (Chốt đơn), `chua_chot` (Chưa chốt),
`thieu_dia_chi` (Thiếu địa chỉ), `thieu_sdt` (Thiếu SĐT),
`da_chot_don` (Đã chốt đơn), `da_day_dvvc` (Đã đẩy sang ĐVVC); cho phép tag tự do
(`^[a-z0-9_]{1,30}$`). Mỗi tag có `source`: `manual` (nhân viên gắn tay) |
`auto` (hệ thống tự gắn — hiển thị icon 🤖).

- `GET /api/inbox/tag-defs` → `{defs: {tag: {label, color}}}`.
- `GET /api/inbox/tags?tag=&page_id=` → `{tags: [{page_id, thread_id, tag, label, color, source, created_at}]}`.
- `GET /api/inbox/tags/by-page/<page_id>` → `{threads: {thread_id: [{tag, label, color, source}]}}`.
- `GET /api/inbox/<page_id>/<thread_id>/tags` → `{tags: [...]}`.
- `POST /api/inbox/<page_id>/<thread_id>/tags` body `{tag}` → `{ok}` (idempotent).
- `DELETE /api/inbox/<page_id>/<thread_id>/tags` (tag trong body hoặc `?tag=`) → `{ok}`.
- `POST /api/inbox/tags/sync-auto` → `{ok, added}` — đồng bộ tag `da_chot_don`
  (source `auto`) từ log của hệ thống automation: đọc READ-ONLY
  `~/workspace/custom-connectors/custom.meta-page-inbox*/hidden_files/`
  (`inbox_state.json` → `closed_order_ids`; `inbox_log_YYYY-MM-DD.jsonl` →
  dòng `hanh_dong == "instant_close"`). Ngoài ra tự đồng bộ ngầm (tối đa 5 phút/lần)
  mỗi khi gọi `GET /api/inbox/tags` hoặc `by-page`.

Auto-tag khi thao tác trong ShopDesk (source `manual`):
- Tạo đơn từ thread (`POST /api/orders`, `/api/orders/quick` có `source_thread`
  dạng `fb:{page_id}/{conv_id}`) → gắn `chot_don`.
- Tạo vận đơn cho đơn có `source_thread` → gắn `da_day_dvvc`, gỡ `chua_chot`.

## Cài đặt
- `GET /api/settings` → `{shipping: {ghn: {api_key_set: bool, ...}, ghtk: {...}, viettelpost: {...}, jt: {...}, best: {...}}}`
  (không bao giờ trả key thật ra ngoài).
- `POST /api/settings/shipping/<carrier>` body `{...fields}` → lưu vào config.json. `{ok}`.
- `POST /api/settings/test` body `{type: "page", page_id}` hoặc `{type: "carrier", carrier}` →
  `{ok: true, msg}` hoặc `{ok: false, msg}` tiếng Việt.

## Vận chuyển
- `POST /api/shipping/<carrier>/create` body `{order_id}` → lấy đơn từ DB, gọi API hãng,
  lưu `shipping_carrier` + `shipping_code` vào đơn. Trả `{ok, code}` hoặc `{ok: false, error_vi}`.
  Nếu chưa nhập key → `{ok: false, error_vi: "Chưa nhập API key GHN. Vào Cài đặt → Vận chuyển để nhập."}`.
  Mọi lần đẩy (thành công hay thất bại) đều ghi 1 dòng vào bảng `shipment_attempts`
  với message nguyên văn tiếng Việt (không nuốt lỗi).
- `GET /api/shipping/<carrier>/track?code=XXX` → `{ok, status_vi, history: [{time, desc}]}`.
- `GET /api/shipping/attempts?order_id=&limit=` → `{attempts: [{id, order_id, carrier,
  success: 0|1, message, created_at}]}` (mới nhất trước) — "Lịch sử đẩy đơn".

## Ghi chú kỹ thuật cho backend
- Mọi HTTP ra ngoài dùng `requests` (tự đọc proxy từ biến môi trường, không set cứng).
- Không log token/key. Lỗi ghi log rút gọn.
- config.json nằm ở `~/workspace/shopdesk/config.json`, app tự tạo nếu chưa có:
  `{"pages": [{"page_id","name","token"}], "shipping": {"ghn": {...}, ...}}`.
