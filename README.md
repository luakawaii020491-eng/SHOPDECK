# 🛍️ ShopDesk — Quản lý bán hàng 2 shop dép

ShopDesk là **app web dùng tay** (thủ công) dành cho **chủ shop / nhân viên** của
**Dép Hana** (dép sục khoét lỗ) và **Shop Bé Đan** (dép sục đế 3 phân).
App chạy trên máy tính của bạn, dữ liệu lưu local — không phụ thuộc internet
ngoài trừ khi nhắn tin Meta hoặc tạo đơn vận chuyển.

## 6 tính năng chính

| # | Tính năng | Mô tả |
|---|-----------|-------|
| 1 | 📥 **Inbox gộp** | Xem và trả lời tin nhắn Messenger của **cả 2 fanpage trong 1 màn hình**. Thread **chưa trả lời in đậm**, đã trả lời chữ thường; lọc theo hashtag; gắn hashtag nhanh (#️⃣ Chốt đơn, Thiếu SĐT, Đã đẩy sang ĐVVC...). Tag **🤖 tự động** khi hệ thống automation chốt đơn. Gửi chữ, gửi ảnh sản phẩm nhanh, **chốt đơn từ hội thoại theo mã SKU**. |
| 2 | 🧾 **Quản lý đơn hàng** | Tạo / sửa / xóa đơn, lọc theo shop & trạng thái, **xuất Excel (CSV)**. **Chốt đơn nhanh từ SKU**: chọn mã sản phẩm → tự tính tiền + trừ kho. |
| 3 | 📦 **Quản lý sản phẩm** | 30 mã SKU có sẵn (Dép Hana 65k/đôi, Bé Đan 49k/đôi; size 36–40; Đen/Nâu/Kem). Thêm/sửa/xóa, theo dõi tồn kho. |
| 4 | 👥 **Quản lý khách hàng** | Lưu tên/SĐT/địa chỉ, tự động cập nhật khi chốt đơn, tra nhanh theo SĐT, xem lịch sử đơn của khách. |
| 5 | 🚚 **Vận chuyển** | Tạo **mã vận đơn thật** và tra cứu hành trình của 5 hãng: **GHN, GHTK, Viettel Post, J&T Express, Best Express** ngay từ đơn hàng — hoặc "lên đơn luôn" khi chốt đơn. |
| 6 | 🖥️ **Triển khai VPS** | Chạy 24/7 trên VPS Ubuntu bằng waitress + systemd + nginx (thư mục `deploy/`). Cách chạy local không đổi. |

> ⚠️ **ShopDesk KHÔNG thay thế hệ thống trả lời tự động** đang chạy (automation
> inbox 24/7). ShopDesk là công cụ **thủ công**: tin bạn gửi từ ShopDesk là tin
> của người thật, không thêm chữ ký tự động.

---

## Cách chạy app (từng bước)

### Bước 1 — Cài Python (chỉ làm 1 lần)

- **Windows:** tải Python **3.10 trở lên** tại <https://www.python.org/downloads/>,
  khi cài nhớ tick chọn **"Add python.exe to PATH"**.
- **Mac:** tải tại trang trên, hoặc chạy `brew install python3`.
- **Linux (Ubuntu/Debian):** `sudo apt install python3 python3-pip`

### Bước 2 — Chạy app

- **Windows:** mở thư mục `shopdesk`, **nhấp đúp file `start.bat`**.
- **Linux / Mac:** mở Terminal, vào thư mục `shopdesk`, chạy:
  ```bash
  ./start.sh
  ```
  (Lần đầu chạy, script tự cài thư viện Flask + requests.)

### Bước 3 — Mở trình duyệt

Vào địa chỉ: **http://localhost:8000**

- Tab **📥 Inbox** — trả lời tin nhắn 2 page (lọc hashtag, chốt đơn theo SKU)
- Tab **🧾 Đơn hàng** — quản lý & xuất đơn
- Tab **📦 Sản phẩm** — quản lý 30 mã SKU, tồn kho
- Tab **👥 Khách hàng** — danh bạ khách, lịch sử đơn
- Tab **⚙️ Cài đặt** — thêm page, nhập key vận chuyển

> Để dừng app: quay lại cửa sổ đen (Terminal/cmd) và nhấn **Ctrl+C**.

---

## Cài đặt ban đầu

### 1. Thêm 2 fanpage (tab Cài đặt → Page)

App cần **Page Access Token** của từng page để đọc/gửi tin nhắn. Cách lấy:

1. Vào <https://developers.facebook.com> → **My Apps** → chọn (hoặc tạo) một Meta App.
2. Trong App, vào **Add Product** → thêm sản phẩm **Messenger**.
3. Vào **Messenger → Settings**, mục **Access Tokens** → chọn fanpage → **Generate Token**
   (cần quyền `pages_messaging` và bạn phải là quản trị viên của page).
4. Copy token, dán vào **Cài đặt → Thêm page** trong ShopDesk (kèm Page ID và tên shop).

> ⏳ **Token Meta có thể hết hạn** (đặc biệt khi đổi mật khẩu Facebook hoặc token
> ngắn hạn). Nếu Inbox báo *"Token page đã hết hạn"*, chỉ cần lấy token mới theo
> các bước trên và nhập lại ở **Cài đặt** — không cần cài lại app.

### 2. Nhập API key 5 hãng vận chuyển (tab Cài đặt → Vận chuyển)

> Chi tiết đầy đủ xem file `docs/shipping_research.md` (tiếng Việt).

- **GHN (Giao Hàng Nhanh)** ✅ — Đăng ký tại `khachhang.ghn.vn` → bấm tên tài khoản
  (góc trái trên) → **Thông tin tài khoản** → tab **Bảo mật** → **Token API & IP tin cậy**
  → nhập OTP SMS để hiện token → copy. Lấy **ShopId** ở mục *Quản lý cửa hàng*
  (hoặc gọi API `GET /shiip/public-api/v2/shop/all`, trường `_id`).
  Nhập vào ShopDesk: `api_key` + `shop_id`. *Không cần ký hợp đồng.*
- **GHTK (Giao Hàng Tiết Kiệm)** ✅ — Đăng nhập `khachhang.giaohangtietkiem.vn` →
  **Thông tin shop → Cấu hình API** → **+ Tạo token**, đặt tên (VD "ShopDesk"), chọn
  ngày hết hạn, tick đủ quyền: **Tính phí, Tạo đơn hàng, Trạng thái đơn hàng,
  Huỷ đơn hàng, In nhãn đơn hàng** (dễ sót quyền Tính phí).
  Nhập vào ShopDesk: `api_key` + `partner_code` (mã shop) + thông tin lấy hàng
  (`pick_name`, `pick_tel`, `pick_address`, `pick_province`, `pick_district`).
  *Không cần ký hợp đồng.*
- **Viettel Post** 🟡 — Đăng ký tài khoản tại `viettelpost.vn`, rồi **đăng nhập 1 lần**
  tại `partner.viettelpost.vn` để kích hoạt API. Vào tab **Developers** lấy API Key,
  bổ sung địa chỉ kho lấy hàng (*Cài đặt tài khoản → Cài đặt thông tin người gửi*).
  Nhập vào ShopDesk: `username` + `password` + `groupaddress_id` + `cus_id`.
  ⚠️ *Cần đối chiếu tài liệu trong tài khoản Partner trước khi dùng thật (xem bảng dưới).*
- **J&T Express** 🔴 — **Bắt buộc ký hợp đồng** với J&T trước (liên hệ bưu cục/kinh
  doanh J&T) để được cấp **mã khách hàng (customer code)** → đăng ký tại
  `open.jtexpress.vn` → hoàn thành **chứng thực developer** mới có quyền gọi API.
  Nhập vào ShopDesk: `api_account` + `customer_code` + `private_key`.
- **Best Express** 🔴 — Liên hệ bộ phận kinh doanh **Best Express (hotline 1900 1031
  hoặc (028) 730 86998)** để **kích hoạt tài khoản** (định dạng `V9Cus…`/`cus...`)
  và xin tài liệu API đối tác — hãng không công bố tài liệu công khai.
  Nhập vào ShopDesk: `username` + `password`.
  Tra cứu tay tại `bestexpress.vn` hoặc Zalo OA "BEST Express Vietnam".

### 3. Bảng trạng thái kiểm chứng từng hãng

| Hãng | Trạng thái | Ghi chú |
|------|-----------|---------|
| **GHN** | ✅ Đã xác minh từ tài liệu chính thức (`developer.ghn.vn`) | Tự lấy token dùng ngay, có sandbox miễn phí |
| **GHTK** | ✅ Tốt nhất — đọc trực tiếp tài liệu chính thức (`pro-docs.ghtk.vn`) | Tự tạo token dùng ngay, chú ý tick đủ quyền và ngày hết hạn token |
| **Viettel Post** | 🟡 Cần đối chiếu | Không có tài liệu công khai; endpoint theo blog kỹ thuật + sandbox mô phỏng — **đối chiếu tài liệu trong tài khoản Partner trước khi dùng thật**. Token dài hạn 1 năm, app cần tự đăng nhập lại khi hết hạn |
| **J&T Express** | 🔴 Chưa kiểm chứng | **Bắt buộc ký hợp đồng** lấy customer code trước; endpoint chi tiết nằm sau đăng nhập `open.jtexpress.vn`. Chưa có hợp đồng thì để trạng thái "chờ hợp đồng" |
| **Best Express** | 🔴 Chưa kiểm chứng | Hãng **không công bố tài liệu API công khai** — liên hệ kinh doanh **1900 1031** để kích hoạt tài khoản (`V9Cus…`/`cus...`) và xin tài liệu đối tác trước khi dùng |

---

## Lưu ý quan trọng

1. **Dữ liệu lưu trên máy bạn**, gồm 2 file:
   - `config.json` — token page + API key các hãng (**giữ bí mật, đừng gửi cho ai**)
   - `data/shopdesk.db` — toàn bộ đơn hàng
   - 💾 **Hãy backup 2 file này định kỳ** (copy sang USB/Drive) để không mất đơn khi đổi máy.
2. API key hãng vận chuyển **không bao giờ** hiện lại ra màn hình sau khi lưu —
   trang Cài đặt chỉ hiện "đã nhập" (dạng `api_key_set: true`).
3. Gửi ảnh nhanh từ Inbox dùng ảnh mẫu trong thư mục `static/` — muốn thêm ảnh mới,
   copy file `.jpg/.png` vào đó rồi tải lại trang.
4. Nếu gặp lỗi khi tạo đơn vận chuyển, đọc kỹ **thông báo tiếng Việt** hiện ra —
   app đã dịch sẵn lỗi thường gặp (thiếu key, token hết hạn, thread bị app khác giữ...).

## Chốt đơn nhanh từ mã SKU (mới)

Trong **Inbox** (nút 🧾 Tạo đơn) hoặc tab **Đơn hàng** (nút ➕ Thêm đơn):

1. Gõ mã SKU (VD `HANA-SUC-DEN-37`) — có gợi ý tự động, nhập số lượng từng mã.
2. App tự tính tổng = Σ(giá SKU × số lượng) + ship (Hana: 1 đôi +25k, ≥2 đôi miễn
   ship; Bé Đan: 1 đôi +30k, ≥2 đôi miễn ship).
3. Nhập SĐT → nếu là khách cũ, tên/địa chỉ tự điền.
4. Tích chọn hãng vận chuyển để **"lên đơn luôn"** (tạo vận đơn ngay khi chốt đơn).

Khi chốt đơn: tồn kho tự trừ (nếu có giới hạn), khách hàng tự lưu/cập nhật theo
SĐT, hội thoại tự gắn hashtag **#️⃣ Chốt đơn**; khi tạo vận đơn → hashtag
**Đã đẩy sang ĐVVC** (và gỡ **Chưa chốt** nếu có).

> Lưu ý: Bé Đan 2 đôi theo công thức SKU = 98k (2×49k), trong khi giá bán lẻ cho
> khách là 99k — kiểm tra lại tổng tiền trước khi xác nhận đơn.

## Hashtag inbox (mới)

Mỗi hội thoại có thể gắn hashtag để lọc và nhận diện nhanh: **Chốt đơn, Chưa
chốt, Thiếu địa chỉ, Thiếu SĐT, Đã chốt đơn, Đã đẩy sang ĐVVC** + tag tự do.
Có 2 nguồn:

- **🤖 Tự động**: khi hệ thống automation (trả lời tự động 24/7) chốt đơn trong
  thread, ShopDesk tự đọc log của automation và gắn tag **Đã chốt đơn** kèm icon
  🤖 (đồng bộ ngầm mỗi 5 phút, hoặc bấm nút đồng bộ trong Inbox).
- **Thủ công**: nhân viên gắn/gỡ tag bằng nút trong cửa sổ chat.

Thread có tin nhắn mới nhất của khách mà page **chưa trả lời** hiển thị **in đậm**
trong danh sách; đã trả lời thì chữ thường. Có bộ lọc "Chưa trả lời" riêng.

## Cấu trúc thư mục (tham khảo)

```
shopdesk/
├── app.py            # file chạy chính
├── start.sh / start.bat
├── config.json       # token + key (BÍ MẬT — backup)
├── data/shopdesk.db  # đơn hàng (backup)
├── app/              # code backend (Flask)
│   ├── carriers/     # tích hợp 5 hãng VC (ghn, ghtk, viettelpost, jt, best)
│   ├── products.py   # quản lý SKU
│   ├── customers.py  # quản lý khách hàng
│   └── tags.py       # hashtag inbox
├── templates/        # giao diện 5 trang
├── static/           # CSS, JS, ảnh gửi nhanh
├── deploy/           # triển khai VPS (systemd, nginx, hướng dẫn)
├── docs/             # tài liệu kỹ thuật (hợp đồng API, nghiên cứu hãng VC)
└── requirements.txt  # thư viện Python
```
