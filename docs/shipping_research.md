# Nghiên cứu API 5 hãng vận chuyển Việt Nam
**Mục đích:** Tài liệu kỹ thuật phục vụ tích hợp vào app Python (ShopDesk).
**Ngày nghiên cứu:** 31/10/2026. Tài liệu của hãng có thể thay đổi — luôn kiểm tra lại tài liệu gốc trước khi tích hợp.
**Quy ước trạng thái kiểm chứng:** ✅ Đã xác minh từ tài liệu chính thức · 🟡 Xác minh qua blog kỹ thuật trích tài liệu chính thức / cross-check nhiều nguồn · 🔴 CHƯA XÁC MINH (cần kiểm tra lại với hãng).

---

## 1. GHN — Giao Hàng Nhanh ✅

### 1.1. Base URL
- **Production:** `https://online-gateway.ghn.vn` — mọi endpoint API nằm dưới prefix `/shiip/public-api/`
- **Staging (sandbox):** `https://dev-online-gateway.ghn.vn` — cùng prefix `/shiip/public-api/`
- Cổng tài liệu chính thức: `https://developer.ghn.vn` (production), `https://developer.ghn.dev` (staging). Đường dẫn tài liệu cũ `api.ghn.vn` **không còn dùng** (GHN đã chuyển hẳn sang developer portal mới).

### 1.2. Xác thực
- Mọi request gửi header `Token: <API_TOKEN>`.
- Đa số API làm việc trên một cửa hàng cụ thể cần thêm header `ShopId: <SHOP_ID>` (số nguyên).
- `Content-Type: application/json`; tiền tính bằng VND (đồng), khối lượng bằng gram, kích thước bằng cm.

### 1.3. Endpoint tạo đơn
- **Method + path:** `POST /shiip/public-api/v2/shipping-order/create` 🟡 (trích tài liệu chính thức qua blog kỹ thuật, khớp với mã nguồn tích hợp thực tế)
- Full URL: `https://online-gateway.ghn.vn/shiip/public-api/v2/shipping-order/create`
- **Field bắt buộc tối thiểu (🟡):** `to_name`, `to_phone`, `to_address`, `to_ward_code`, `to_district_id` (mã địa chỉ theo danh mục GHN), `weight` (gram), `service_type_id` (2 = hàng nhẹ, 5 = hàng nặng), `payment_type_id` (1 = shop trả, 2 = người nhận trả), `required_note` (ghi chú bắt buộc: `CHOTHUHANG` cho xem hàng, `KHONGCHOXEMHANG`, `CHOXEMKHONGTHU`).
- **Nên gửi thêm:** `client_order_code` (mã đơn phía shop — gọi lại cùng mã thì GHN **trả về đơn đã tạo thay vì tạo trùng**, chống trùng đơn khi retry), `cod_amount` (tiền thu hộ COD), `insurance_value`, `content` (nội dung hàng).
- **Response:** trả về `order_code` — chính là **mã vận đơn / mã tracking** của GHN. Lưu lại.

### 1.4. Endpoint tra cứu trạng thái
- Tài liệu chính thức có nhóm API "Order Info" (xem chi tiết đơn theo `order_code`, và xem theo `client_order_code`) 🟡.
- Khuyến nghị thực tế: **webhook** — khai callback URL trên Developer Portal → mục *Cấu hình webhook → tab Order* (có hiệu lực sau ~15 phút). Webhook đẩy JSON trạng thái đơn + đối soát COD, cần phản hồi 2xx trong 5 giây; GHN tự gửi lại theo lịch giãn dần (30 giây → 12 giờ), số lần gửi lại do shop chọn 1–5 lần.

### 1.5. Cách lấy API key (từng bước)
1. Đăng ký tài khoản GHN tại `khachhang.ghn.vn` (đăng nhập bằng SĐT, hoặc Google/Apple), **xác thực tài khoản** (tài khoản chưa xác thực chỉ tạo được vài đơn thử).
2. Lấy **Token**: bấm tên tài khoản (góc trên bên trái) → *Thông tin tài khoản* → tab **Bảo mật** → **Token API & IP tin cậy** → **Quản lý** → bấm biểu tượng con mắt, nhập **OTP** gửi qua SMS để hiện token → sao chép. (Cách khác: đăng nhập Developer Portal `developer.ghn.vn` → menu tài khoản → **Manage token**, xác thực OTP.)
3. Lấy **ShopId**: trên `khachhang.ghn.vn` vào *Quản lý cửa hàng* — mỗi cửa hàng là một ShopId. Hoặc gọi `GET /shiip/public-api/v2/shop/all` (chỉ cần header Token), trường `_id` của mỗi shop chính là ShopId.
4. **Không cần đăng ký đối tác / ký hợp đồng** — shop tự lấy token và dùng ngay.

### 1.6. Giới hạn / quota / phí
- GHN không công bố quota công khai; API dùng token của shop, cước tính theo bảng giá của shop.
- **Sandbox miễn phí, không phát sinh đơn thật.** Tài khoản + token staging và production **hoàn toàn tách biệt**, không dùng lẫn được.
- Giới hạn nghiệp vụ: khối lượng tối đa 50 kg/đơn; COD tối đa 50.000.000đ/đơn; giá trị bảo hiểm tối đa 5.000.000đ.

### 1.7. Lưu ý đặc biệt
- Token có thể giới hạn theo **IP tin cậy** — nếu bật danh sách IP mà không thêm IP máy chủ app, mọi request sẽ lỗi 401.
- Từ 01/07/2025 GHN chạy song song địa chỉ cũ 3 cấp và mới 2 cấp; khi tạo đơn trường `is_new_to_address` báo kiểu địa chỉ đang gửi; API tính phí `fee` vẫn dùng mã quận/huyện + phường/xã theo bộ cũ, còn API **Preview** nhận cùng dữ liệu như tạo đơn, trả phí + ngày giao dự kiến **mà không tạo đơn**.
- Tính phí: `POST /shiip/public-api/v2/shipping-order/fee` 🟡. Hủy đơn: `v2/switch-status/cancel`. In đơn: gọi `v2/a5/gen-token` (token in sống ~30 phút) rồi mở trang in (A5, 80×80, 52×70).

---

## 2. GHTK — Giao Hàng Tiết Kiệm ✅

### 2.1. Base URL
- **Production:** `https://services.giaohangtietkiem.vn` ✅ (xác minh trực tiếp từ tài liệu chính thức `pro-docs.ghtk.vn`)
- **Staging (sandbox):** `https://services-staging.ghtklab.com` 🟡 (blog kỹ thuật trích tài liệu chính thức); trang quản trị thử: `khachhang-staging.ghtklab.com`.
- Tài liệu chính thức: `https://pro-docs.ghtk.vn` (tiếng Anh) và `https://docs.giaohangtietkiem.vn`.

### 2.2. Xác thực
- Mỗi request gửi 2 header: `Token: <API_TOKEN>` và `X-Client-Source: <PARTNER_CODE>` (mã shop) ✅.
- Token có **ngày hết hạn bắt buộc** — hết hạn thì API từ chối, phải tạo token mới.

### 2.3. Endpoint tạo đơn
- **Method + path:** `POST /services/shipment/order` ✅ (tài liệu chính thức)
- Full URL: `https://services.giaohangtietkiem.vn/services/shipment/order`
- **Field bắt buộc tối thiểu (✅, theo tài liệu chính thức):**
  - `products[]`: `name` (Y), `weight` (Y); `quantity`, `price`, `product_code`, `barcode`, `cod_money` (N).
  - `order.id` (Y) — mã tham chiếu phía đối tác (dùng để chống trùng + tra cứu theo mã shop).
  - Lấy hàng: `pick_name` (Y), `pick_money` (Y — **tiền thu hộ COD**), `pick_address` (Y), `pick_province` (Y), `pick_district` (Y), `pick_tel` (Y).
  - Giao hàng: `name` (Y), `address` (Y), `province` (Y), `district` (Y), `hamlet` (Y — không có thì điền `"Khác"`), `tel` (Y), `value` (Y — giá trị khai báo để tính bảo hiểm).
- **Response:** `order.label` — **mã vận đơn GHTK** (dạng `S1.A1.xxxxxxxx`).
- Lưu ý: API tính phí của GHTK nhận **tên tỉnh/phường-xã**, quận/huyện không bắt buộc — hợp với địa chỉ 2 cấp mới.

### 2.4. Endpoint tra cứu trạng thái
- **Method + path:** `GET /services/shipment/v2/{label_id}` ✅ (tài liệu chính thức) — `{label_id}` là mã vận đơn GHTK, hoặc dùng mã đối tác theo định dạng tài liệu.
- Response trả `status` (mã số), `status_text` (mô tả tiếng Việt, VD "Chưa tiếp nhận"), `ship_money`, `pick_money`, `weight`, v.v.
- Webhook: shop tự cấu hình trên trang khách hàng (*Thông tin tài khoản → Cấu hình API → Cấu hình webhook*); lưu ý nếu endpoint không trả HTTP 200 thì GHTK **chỉ gửi lại thêm một lần** 🟡.
- Hủy đơn: `POST /services/shipment/cancel/{TRACKING_ORDER}` ✅ (chỉ hủy được khi shipper chưa lấy hàng).
- In nhãn: `GET /services/label/{label_ID}` ✅ — trả **file PDF** (khổ A5/A6, dọc/ngang).

### 2.5. Cách lấy API key (từng bước)
1. Đăng ký tài khoản shop tại `ghtk.vn` (hoặc `giaohangtietkiem.vn`).
2. Đăng nhập trang khách hàng `khachhang.giaohangtietkiem.vn` bằng tài khoản shop.
3. Vào **Thông tin shop → Cấu hình API** (đường dẫn thẳng: `khachhang.giaohangtietkiem.vn/web/thong-tin-shop/cau-hinh-api`).
4. Bấm **+ Tạo token**, điền **Tên token** (đặt theo nơi dùng, VD "ShopDesk"), chọn **Ngày hết hạn**, tick các **quyền** cần: **Tính phí, Tạo đơn hàng, Trạng thái đơn hàng, Huỷ đơn hàng, In nhãn đơn hàng** (quyền Tính phí dễ bị bỏ sót).
5. Lưu token + **mã shop** (dùng làm `X-Client-Source`).
6. Kiểm tra nhanh: gọi `GET /services/authenticated` với 2 header trên 🟡.
7. **Không cần ký hợp đồng** — shop tự tạo token và dùng ngay.

### 2.6. Giới hạn / quota / phí
- Tài liệu không công bố quota gọi API; token bắt buộc có ngày hết hạn.
- **Sandbox miễn phí** (tài khoản + token thử tách hẳn tài khoản thật). Muốn test mà không tạo vận đơn thật thì làm y hệt các bước trên ở `khachhang-staging.ghtklab.com` 🟡.

### 2.7. Lưu ý đặc biệt
- Quyền token là **per-token, per-scope**: tick thiếu quyền nào thì API nhóm đó bị từ chối — kiểm tra đầu tiên khi gặp lỗi 401/quyền.
- Có dịch vụ hàng nặng **BBS** (API riêng `.../shipment/3pl/...`) và dịch vụ giao nhanh **XFAST** (`transport: "fly"`, `deliver_option: "xteam"`).
- Tags đặc biệt khi tạo đơn: `[1]` dễ vỡ (+1.000đ), `[10]` cho xem hàng, `[11]` đồng kiểm (+2.000đ).

---

## 3. Viettel Post 🟡

> ⚠️ Viettel Post **không công bố tài liệu API công khai** — tài liệu kỹ thuật chi tiết chỉ cấp cho đối tác qua hệ thống Partner. Các endpoint dưới đây được tổng hợp từ blog kỹ thuật (trích tài liệu chính thức, kiểm tra 08/10/2026) và sandbox mô phỏng luồng thật của Viettel Post; **cần đối chiếu lại với tài liệu trong tài khoản Partner trước khi code production**.

### 3.1. Base URL
- **Production:** API v2 chạy dưới hệ thống Partner — `https://partner.viettelpost.vn` 🟡 (đường dẫn API `/v2/...`; chi tiết path do tài liệu Partner cung cấp).
- **Staging (sandbox):** `https://partnerdev.viettelpost.vn` 🟡.
- Không có developer portal công khai như GHN/GHTK.

### 3.2. Xác thực
- Đăng nhập bằng **chính tài khoản Viettel Post của shop** (username/password, hoặc SĐT) 🟡:
  - `POST /user/login` → nhận **token tạm**;
  - `POST /user/ownerconnect` (gửi kèm token tạm) → nhận **token dài hạn, hiệu lực 1 năm**.
- Các API nghiệp vụ gửi token trong header `Token` 🟡.
- Token hết hạn → phải login lại để lấy token mới (app cần cơ chế tự refresh).

### 3.3. Endpoint tạo đơn
- **Method + path:** `POST /order/createOrder` 🔴 (path theo sandbox mô phỏng luồng thật; **chưa xác minh từ tài liệu chính thức**).
- **Field bắt buộc tối thiểu (🔴 — cần kiểm tra lại):** `GROUPADDRESS_ID` và `CUS_ID` (lấy từ API `user/listInventory` — danh sách kho/địa chỉ lấy hàng của shop), thông tin người nhận (tên, SĐT, địa chỉ), `PRODUCT_NAME`, `PRODUCT_WEIGHT` (gram), mã dịch vụ (lấy từ `order/getPriceAllNlp`), `MONEY_COLLECTION` (tiền thu hộ COD).
- **Luồng chuẩn:** login → `order/getPriceAllNlp` (liệt kê dịch vụ khả dụng + cước cho tuyến, nhận địa chỉ dạng mã hoặc chữ tự do) → `user/listInventory` (lấy GROUPADDRESS_ID, CUS_ID) → `order/createOrder`.
- **Response:** mã vận đơn Viettel Post (mã tracking).

### 3.4. Endpoint tra cứu trạng thái
- 🔴 **Chưa xác minh path chính xác** từ tài liệu công khai. Viettel Post có API xem chi tiết/hành trình đơn trong bộ API Partner (đối chiếu tài liệu trong tài khoản).
- Webhook: cấu hình trong hệ thống Partner (*Account configuration*): điền webhook URL + secret; endpoint phải trả **200 trong dưới 1 giây**, nếu không Viettel Post gửi lại tối đa **5 lần** (có thể nhận trùng bản tin — app cần idempotency) 🟡.

### 3.5. Cách lấy quyền API (từng bước)
1. Đăng ký tài khoản tại `viettelpost.vn` (cá nhân/shop đều được) — **tự đăng ký, không phải chờ hãng mở**.
2. Đăng nhập **một lần** tại `https://partner.viettelpost.vn` bằng đúng tài khoản trên → tài khoản được **tự động kích hoạt kết nối API** 🟡.
3. ⚠️ Điều kiện quan trọng: tài khoản phải **đăng nhập được cả `viettelpost.vn` lẫn hệ thống Partner** thì API mới nhận 🟡.
4. Trong Partner portal vào tab **Developers** để lấy **API Key / API Secret** hoặc dùng luồng login lấy token dài hạn (1 năm) như mục 3.2 🟡.
5. Bổ sung địa chỉ kho lấy hàng: *Cài đặt tài khoản → Cài đặt thông tin người gửi*.

### 3.6. Giới hạn / quota / phí
- Không có thông tin quota/phí API công khai. Cước vận chuyển theo bảng giá hợp đồng của shop.
- Sandbox `partnerdev.viettelpost.vn` để chạy thử 🟡.

### 3.7. Lưu ý đặc biệt
- Token có hạn (loại dài hạn 1 năm) — app **bắt buộc** có job tự refresh token, nếu không đơn sẽ rớt hàng loạt khi token hết hạn.
- Tính phí có 2 kiểu: theo mã tỉnh/huyện/xã, hoặc theo địa chỉ dạng chữ tự do; có API liệt kê dịch vụ khả dụng cho một tuyến trước khi tính phí.
- In đơn: lấy mã in cho tối đa 100 đơn rồi mở trang in (khổ A5, A6, A7) 🟡.
- Cập nhật trạng thái đơn về hệ thống: cấu hình webhook trong Partner, **phải liên hệ bộ phận kỹ thuật Viettel Post** để được hỗ trợ kích hoạt trong một số trường hợp 🟡.

---

## 4. J&T Express 🟡/🔴

### 4.1. Base URL
- Cổng nền tảng mở: `https://open.jtexpress.vn` ✅ (xác minh mở được trang "J&T OPEN PLATFORM").
- Base URL + path API cụ thể **chỉ công bố sau khi đăng ký developer và ký hợp đồng** — tài liệu chi tiết nằm sau đăng nhập, 🔴 **chưa xác minh endpoint cụ thể cho thị trường VN**.

### 4.2. Xác thực
- Không có cơ chế "tự lấy token" như GHN/GHTK. Cần: **ký hợp đồng với J&T** → được cấp **mã khách hàng (customer code)** do bưu cục đối tác cấp → đăng ký tài khoản trên `open.jtexpress.vn` → hoàn thành **chứng thực developer** mới có đầy đủ quyền gọi API 🟡.
- Mô hình xác thực: API account + customer code (+ chữ ký request theo chuẩn của J&T Open Platform) 🔴 — chi tiết trong tài liệu sau đăng nhập.

### 4.3. Endpoint tạo đơn
- 🔴 **CHƯA XÁC MINH** — API tạo đơn chỉ dành cho khách hàng đã ký hợp đồng; path/field cụ thể lấy từ tài liệu trong tài khoản Open Platform sau khi được cấp quyền.
- Theo chuẩn chung của J&T Open Platform (tham khảo tích hợp các nước): tạo đơn gồm mã đơn phía đối tác, thông tin người gửi/người nhận (tên, SĐT, địa chỉ), khối lượng, loại hình vận chuyển, tiền thu hộ COD; response trả mã vận đơn J&T. **Không dùng làm căn cứ code** khi chưa có tài liệu VN chính thức.

### 4.4. Endpoint tra cứu trạng thái
- 🔴 **CHƯA XÁC MINH** path API tracking cho VN. J&T **đẩy trạng thái vận chuyển về URL do shop cung cấp** (webhook) 🟡.
- Tra cứu thủ công: trang tracking `jtexpress.vn`; mã vận đơn J&T VN thường bắt đầu bằng các đầu số của hãng.

### 4.5. Cách lấy quyền API (từng bước)
1. **Ký hợp đồng** với J&T Express Việt Nam (liên hệ bưu cục/kinh doanh J&T) — **bắt buộc, không có đường tự đăng ký**.
2. Nhận **mã khách hàng (customer code)** do bưu cục đối tác cấp.
3. Đăng ký tài khoản tại `https://open.jtexpress.vn` (nền tảng mở, giao diện tiếng Trung/Anh).
4. Hoàn thành **chứng thực developer** (điền thông tin developer) để mở toàn bộ quyền API.
5. Thực hiện **liên điều (联调)** — test API trên môi trường thử, rồi **phát hành上线** (go-live).

### 4.6. Giới hạn / quota / phí
- Theo hợp đồng ký với J&T; không có thông tin công khai.
- Có **domain thử riêng + tài khoản API thử được công bố trong tài liệu** 🟡 (chi tiết sau đăng nhập).

### 4.7. Lưu ý đặc biệt
- **J&T là hãng duy nhất trong 4 hãng yêu cầu ký hợp đồng trước khi dùng API** — không thể "đăng ký là chạy" như GHN/GHTK/Viettel Post. Đây là rào cản lớn nhất cho ShopDesk.
- Nhãn vận đơn trả về dạng **base64**, nhiều khổ từ A4 đến in nhiệt 80mm 🟡.
- API tính phí có sẵn; với địa chỉ hành chính mới, trường cấp huyện không cần điền 🟡.
- Nếu cần tracking đơn giản mà chưa có hợp đồng API: dùng các aggregator tracking bên thứ ba (AfterShip, TrackingMore) — chỉ tra cứu, không tạo đơn.

---

## 5. Best Express (BEST Inc Việt Nam) 🟡/🔴

> ⚠️ Best Express **không công bố tài liệu API gốc công khai**. Tài liệu kỹ thuật chi tiết chỉ cấp cho đối tác sau khi ký hợp đồng / kích hoạt tài khoản với bộ phận kinh doanh. Các mục dưới đây tổng hợp từ tài liệu tích hợp chính thức của Sapo (đối tác Best Express) và kiểm tra web công khai — **cần đối chiếu lại với tài liệu hãng cấp trước khi code production** (nghiên cứu 01/11/2026).

### 5.1. Base URL
- 🔴 **CHƯA XÁC MINH** — hãng không công bố base URL API gốc công khai. Web tra cứu công khai: `bestexpress.vn`.
- AfterShip hỗ trợ tracking Best Express qua aggregator (slug `800bestex`) — chỉ tra cứu, không tạo đơn 🟡.

### 5.2. Xác thực
- Theo tài liệu tích hợp Sapo (support.sapo.vn/best-express) 🟡: kết nối bằng **Tên đăng nhập + Mật khẩu** tài khoản BEST (định dạng `V9Cus…` hoặc `cus...` — **không phải email/SĐT**), **tài khoản phải được kích hoạt** trước khi kết nối (liên hệ hotline **1900 1031** hoặc **(028) 730 86998** gặp bộ phận kinh doanh).
- 🔴 Chi tiết auth của API gốc (header/token/endpoint login) chưa được công bố — nằm trong tài liệu đối tác sau ký hợp đồng.

### 5.3. Endpoint tạo đơn
- 🔴 **CHƯA XÁC MINH** — endpoint tạo đơn API gốc không được công bố công khai. Sapo tích hợp tạo đơn qua tài khoản BEST đã kích hoạt (cơ chế gia hạn kết nối 30 ngày là đặc thù của Sapo, không phải của API gốc) 🟡.
- Tạm thời: tạo đơn tay trên website/app Best Express cho đến khi có tài liệu hãng.

### 5.4. Endpoint tra cứu trạng thái
- 🔴 **CHƯA XÁC MINH** path API tracking gốc. Tra cứu công khai 🟡: website `bestexpress.vn` (nhập tới **20 mã vận đơn/lần**, cách nhau bằng dấu phẩy/khoảng cách), Zalo OA "BEST Express Vietnam", tổng đài **1900 1031**.

### 5.5. Cách lấy quyền API (từng bước)
1. Liên hệ **bộ phận kinh doanh Best Express**: hotline **1900 1031** hoặc **(028) 730 86998** — ký hợp đồng / đăng ký tài khoản đối tác (không có đường tự đăng ký) 🟡.
2. Nhận **tên đăng nhập** định dạng `V9Cus…` / `cus...`; tài khoản cần được **kích hoạt** trước khi kết nối 🟡.
3. Xin **tài liệu API đối tác** từ bộ phận kinh doanh / người phụ trách hợp đồng; đối chiếu endpoint, auth, field tạo đơn rồi mới code production 🔴 (chưa có tài liệu).

### 5.6. Giới hạn / quota / phí
- Không có thông tin quota/phí API công khai. Cước theo bảng giá hợp đồng của shop.

### 5.7. Lưu ý đặc biệt
- **Best Express là hãng thứ hai (sau J&T) yêu cầu hợp đồng/kích hoạt trước khi dùng API** — không thể "đăng ký là chạy" như GHN/GHTK/Viettel Post.
- ShopDesk hiện ở trạng thái **khung chuẩn bị**: lưu được username/password trong Cài đặt, nhưng `create_shipment`/`track` chủ động báo "CHƯA KHẢ DỤNG" thay vì bắn request đoán mò (tránh tạo sai đơn thật / lộ thông tin khách hàng).

---

## 6. Bảng so sánh nhanh

| Hãng | Base URL (production) | Xác thực | Endpoint tạo đơn | Endpoint tracking | Sandbox | Trạng thái kiểm chứng |
|---|---|---|---|---|---|
| **GHN** | `https://online-gateway.ghn.vn` (+`/shiip/public-api/`) | Header `Token` + `ShopId` | `POST /shiip/public-api/v2/shipping-order/create` | API "Order Info" theo `order_code` + webhook | `dev-online-gateway.ghn.vn`, portal `developer.ghn.dev`, tài khoản thử `5sao.ghn.dev` — miễn phí | ✅ Portal + tài liệu chính thức mở được; endpoint cross-check blog KT + code thực tế |
| **GHTK** | `https://services.giaohangtietkiem.vn` | Header `Token` + `X-Client-Source` (mã shop) | `POST /services/shipment/order` | `GET /services/shipment/v2/{label_id}` | `services-staging.ghtklab.com` (+`khachhang-staging.ghtklab.com`) — miễn phí | ✅ Đã đọc trực tiếp tài liệu chính thức `pro-docs.ghtk.vn` |
| **Viettel Post** | `https://partner.viettelpost.vn` (API v2) | Login tài khoản Partner → token (`/user/login` → `/user/ownerconnect`, token dài hạn 1 năm) | `POST /order/createOrder` | API chi tiết đơn trong bộ Partner + webhook | `partnerdev.viettelpost.vn` | 🟡 Không có tài liệu công khai; endpoint theo blog KT + sandbox mô phỏng — **cần đối chiếu tài liệu Partner** |
| **J&T Express** | `https://open.jtexpress.vn` (cổng đăng ký) | Hợp đồng + **customer code** do bưu cục cấp + chứng thực developer | CHƯA XÁC MINH | Webhook đẩy trạng thái; tra cứu tay tại `jtexpress.vn` | Có môi trường thử (chi tiết sau đăng nhập) | 🔴 Tài liệu chi tiết sau đăng nhập; **bắt buộc ký hợp đồng trước** |
| **Best Express** | CHƯA XÁC MINH (web công khai: `bestexpress.vn`) | Tên đăng nhập + Mật khẩu tài khoản BEST (`V9Cus…`/`cus...`), tài khoản phải **kích hoạt** trước | CHƯA XÁC MINH | Tra cứu công khai tại `bestexpress.vn` (20 mã/lần), Zalo OA, hotline 1900 1031 | Chưa rõ | 🟡 Xác thực + tra cứu công khai theo tài liệu Sapo; 🔴 **endpoint API gốc chưa công bố — bắt buộc liên hệ kinh doanh trước** |

---

## 7. Khuyến nghị cho ShopDesk (tích hợp Python)

1. **Thứ tự triển khai:** GHTK → GHN → Viettel Post → J&T → Best Express. GHTK/GHN có tài liệu công khai đầy đủ nhất, tự lấy token được, có sandbox miễn phí — dev có thể bắt đầu ngay không cần chờ hãng.
2. **Viettel Post:** cần tài khoản Partner thật để lấy tài liệu API chính xác; trong code **bắt buộc** có cơ chế tự refresh token (token dài hạn 1 năm).
3. **J&T / Best Express:** không thể tích hợp "âm thầm" — phải ký hợp đồng / kích hoạt tài khoản và có tài liệu đối tác trước. Nếu user chưa ký, tạm để trạng thái "chờ hợp đồng" trong app (code Best Express hiện chủ động báo "CHƯA KHẢ DỤNG" thay vì bắn request đoán mò).
4. **Chống trùng đơn:** GHN dùng `client_order_code`, GHTK dùng `order.id` — luôn sinh và gửi mã tham chiếu phía shop.
5. **Nhận trạng thái:** cả 4 hãng đều hỗ trợ webhook — thiết kế một webhook receiver chung, chuẩn hóa trạng thái về enum nội bộ của ShopDesk; lưu ý GHTK chỉ retry 1 lần, GHN retry 1–5 lần (cấu hình được), Viettel Post retry 5 lần (có thể trùng bản tin → cần idempotency).

### Nguồn tham khảo chính
- GHN Developer Portal: https://developer.ghn.vn (kiểm tra 31/10/2026)
- GHN API catalog (chính thức): https://api.ghn.vn/home/docs
- GHTK Open API docs (chính thức): https://pro-docs.ghtk.vn/3-shipping_api/ (đọc trực tiếp 31/10/2026)
- GHTK OpenApi (chính thức): https://docs.giaohangtietkiem.vn
- J&T Open Platform: https://open.jtexpress.vn (mở được 31/10/2026)
- Blog kỹ thuật DevVN (Lê Văn Toản) — trích tài liệu chính thức 3 hãng, kiểm tra 08–11/10/2026: https://levantoan.com (các bài kết nối GHN, token GHN/GHTK, so sánh 4 hãng)
- GP247 GHN plugin docs (trích developer.ghn.vn, test staging 18/10/2026): https://gp247.net/en/product/shipping-plugin-giao-hang-nhanh.html
- EzyPlatform Viettel Post sandbox (mô phỏng luồng API thật): https://ezyplatform.com/market/items/viettel-post-sandbox/docs/cac-buoc-tao-don-viettel-post
- Sapo — Hướng dẫn thiết lập đối tác vận chuyển Best Express (chính thức, đọc 01/11/2026): https://support.sapo.vn/best-express
- TrackingMore — BEST Express (Vietnam) Tracking API: https://www.trackingmore.com/best-vn-tracking-api
- AfterShip — Best Express tracking API (aggregator): https://www.aftership.com/carriers/800bestex/api
