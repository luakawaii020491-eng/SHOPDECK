# Đưa ShopDesk lên mạng bằng Render (miễn phí) — hướng dẫn từng bước

Thời gian: khoảng 15–20 phút. Cần: 1 tài khoản GitHub + 1 tài khoản Render
(cả hai đều miễn phí, đăng ký Render bằng nút "GitHub" cho nhanh).

## Bước 1 — Đẩy code ShopDesk lên GitHub

Trên máy tính của bạn, mở thư mục `shopdesk` (giải nén từ file zip) rồi chạy:

```bash
cd shopdesk
git init
git add .
git commit -m "ShopDesk"
```

Yên tâm: file `config.json` (chứa token page thật) và database `*.db` đã được
loại trừ khỏi git nhờ file `.gitignore` có sẵn — chúng sẽ KHÔNG bị đẩy lên GitHub.

Tạo repository mới trên github.com (tên ví dụ `shopdesk`), rồi:

```bash
git remote add origin https://github.com/TEN-CUA-BAN/shopdesk.git
git branch -M main
git push -u origin main
```

## Bước 2 — Tạo Web Service trên Render

1. Vào https://dashboard.render.com → **New +** → **Web Service**
2. Chọn repository `shopdesk` vừa đẩy → **Connect**
3. Điền thông tin:
   - **Name:** `shopdesk`
   - **Region:** Singapore (gần Việt Nam nhất)
   - **Runtime:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `waitress-serve --listen=0.0.0.0:$PORT --call 'app:create_app'`
   - **Plan:** Free
4. Mục **Environment Variables** → **Add Environment Variable**, thêm:
   - Key: `SHOPDESK_PAGES_JSON`
   - Value: (thay TOKEN_HANA và TOKEN_BEDAN bằng token page thật của bạn)
     ```json
     [{"page_id":"441747482366131","name":"Dép Hana","token":"TOKEN_HANA"},{"page_id":"209825435542158","name":"Shop Bé Đan","token":"TOKEN_BEDAN"}]
     ```
     Cách này giúp token page sống sót qua mỗi lần deploy code mới. Nếu không
     muốn dùng, bạn có thể bỏ qua và dán token ở trang **Cài đặt** của app
     sau khi deploy (nhưng mỗi lần deploy code mới sẽ phải nhập lại).
5. Bấm **Create Web Service** → Render tự build, khoảng 2–5 phút.
6. Xong: app chạy ở địa chỉ dạng `https://shopdesk-xxxx.onrender.com`
   (xem trong dashboard). Mở lên, vào **Cài đặt** kiểm tra 2 page đã nhận.

## Bước 3 — Giữ app không "ngủ" (khuyên dùng)

Gói Free của Render cho app **ngủ sau 15 phút không ai truy cập** — lần mở
đầu tiên sau đó mất khoảng 30–60 giây để app "dậy". Để tránh:

1. Đăng ký miễn phí https://uptimerobot.com
2. Add New Monitor → loại **HTTP(s)**, dán URL app của bạn,
   Monitoring Interval: **5 minutes**
3. UptimeRobot sẽ "gõ cửa" app mỗi 5 phút → app luôn thức.

## ⚠️ Lưu ý quan trọng về dữ liệu (đọc kỹ)

- **Database nằm trên ổ đĩa tạm của Render (gói Free).** Mỗi lần bạn deploy
  code mới hoặc Render restart máy chủ, dữ liệu đơn hàng / sản phẩm / khách
  hàng trong SQLite sẽ **MẤT**. Cách xử lý:
  - Ít deploy thì ít mất — chỉ deploy khi thật sự cần.
  - Sao lưu định kỳ: vào dashboard Render → **Shell** → tải file
    `data/shopdesk.db` về máy.
  - Muốn ổn định lâu dài: nâng plan trả phí của Render kèm ổ đĩa bền
    (persistent disk), hoặc thuê mình chuyển sang database Postgres ngoài.
- **Token/key hãng vận chuyển** nhập ở trang Cài đặt cũng mất khi redeploy —
  nhập lại sau mỗi lần deploy, hoặc báo mình để mình thêm biến môi trường
  tương tự như `SHOPDESK_PAGES_JSON`.
- Gói Free vẫn gắn được **tên miền riêng** (Render → Settings → Custom Domain)
  và có sẵn HTTPS miễn phí.

## Cập nhật code sau này

Sửa code trên máy → `git add .` → `git commit` → `git push` — Render tự
deploy lại trong vài phút. Nhớ sao lưu database trước khi push (xem lưu ý trên).
