# Triển khai ShopDesk lên VPS Ubuntu — hướng dẫn từng bước

ShopDesk có 2 cách chạy:

| Cách | Khi nào dùng | Lệnh |
|---|---|---|
| **Chạy local** (mặc định, đơn giản) | Dùng trên máy tính của bạn | `./start.sh` (Linux/Mac) hoặc `start.bat` (Windows) → mở `http://localhost:8000` |
| **Chạy trên VPS** (24/7) | Muốn truy cập từ điện thoại/mọi nơi, không cần mở máy tính | Làm theo 6 bước dưới đây |

> Cách local KHÔNG thay đổi — VPS chỉ là lựa chọn thêm.

---

## Chuẩn bị

1. Thuê 1 VPS Ubuntu 22.04 (RAM 1GB là đủ), ví dụ tại Viettel IDC, FPT Cloud, Vultr, DigitalOcean...
2. Có địa chỉ IP của VPS. (Tùy chọn: trỏ domain, VD `shop.cuaban.com`, về IP này.)

## Bước 1 — Copy code lên VPS

Trên máy tính của bạn (thư mục chứa `shopdesk_v2`):

```bash
# Nén lại nếu cần, rồi copy lên VPS (thay IP và user cho đúng)
scp shopdesk_v2.zip ubuntu@IP_VPS:/tmp/
```

Trên VPS:

```bash
sudo apt update && sudo apt install -y unzip python3 python3-pip python3-venv nginx
sudo mkdir -p /opt/shopdesk && sudo unzip -o /tmp/shopdesk_v2.zip -d /opt/shopdesk
```

## Bước 2 — Cài đặt (3 lệnh)

```bash
cd /opt/shopdesk
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Bước 3 — Chạy thử

```bash
./venv/bin/waitress-serve --listen=127.0.0.1:8000 app:app
```

Mở trình duyệt trên máy tính, vào `http://IP_VPS:8000` — nếu thấy trang Inbox là OK.
Nhấn `Ctrl+C` để dừng, rồi làm tiếp bước 4 để app tự chạy nền 24/7.

> Lần đầu chạy, app tự tạo `data/shopdesk.db` và seed sẵn 30 mã sản phẩm.
> Nhập token 2 fanpage + API key hãng vận chuyển ở mục **Cài đặt** trong app.

## Bước 4 — Tự chạy 24/7 bằng systemd

```bash
# Tạo user riêng (không chạy bằng root)
sudo useradd -r -s /bin/false shopdesk
sudo chown -R shopdesk:shopdesk /opt/shopdesk

# Cài service mẫu (sửa WorkingDirectory/ExecStart nếu bạn đặt code chỗ khác)
sudo cp /opt/shopdesk/deploy/shopdesk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now shopdesk

# Kiểm tra
systemctl status shopdesk
journalctl -u shopdesk -f   # xem log trực tiếp
```

## Bước 5 — Mở cổng web qua nginx (khuyên dùng)

```bash
sudo cp /opt/shopdesk/deploy/nginx-shopdesk.conf /etc/nginx/sites-available/shopdesk
# Sửa server_name thành domain của bạn (hoặc xóa dòng đó nếu dùng IP)
sudo nano /etc/nginx/sites-available/shopdesk
sudo ln -s /etc/nginx/sites-available/shopdesk /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Mở firewall nếu có:

```bash
sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
```

Truy cập: `http://IP_VPS` (hoặc domain của bạn).

## Bước 6 — Bật HTTPS miễn phí (nên làm)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d shop.cuaban.com   # thay domain của bạn
```

## Bảo trì nhanh

```bash
# Cập nhật code mới: copy đè file, rồi restart
sudo systemctl restart shopdesk

# Sao lưu dữ liệu (rất quan trọng — làm định kỳ)
cp /opt/shopdesk/data/shopdesk.db ~/shopdesk_backup_$(date +%F).db
cp /opt/shopdesk/config.json ~/config_backup_$(date +%F).json
```

## Khắc phục sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `systemctl status shopdesk` báo lỗi | `journalctl -u shopdesk -n 50` để xem log lỗi chi tiết |
| Vào web báo 502 Bad Gateway | App chưa chạy — kiểm tra bước 4; thử chạy tay bước 3 để xem lỗi |
| Quên sao lưu mà mất DB | DB nằm ở `/opt/shopdesk/data/shopdesk.db` — luôn backup trước khi cập nhật code |
