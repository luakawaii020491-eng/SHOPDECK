/* ShopDesk — Cài đặt: quản lý page Facebook + API key 4 hãng vận chuyển.
 * Hướng dẫn lấy key trích từ docs/shipping_research.md (31/10/2026). */
"use strict";

const $ = (id) => document.getElementById(id);

/* ---------------- Fanpage ---------------- */

async function loadPages() {
  const box = $("pageList");
  box.innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải danh sách page…</div>`;
  try {
    const j = await api("/api/pages");
    const pages = j.pages || [];
    if (!pages.length) {
      box.innerHTML = `<div class="state-empty">Chưa có page nào. Thêm page đầu tiên ở form bên dưới.</div>`;
      return;
    }
    box.innerHTML = pages.map((p) => `
      <div class="page-card">
        <div class="info">
          <div class="pname">${esc(p.name)} ${p.status === "ok"
            ? `<span class="status st-ok">Kết nối OK</span>`
            : `<span class="status st-err">Lỗi kết nối</span>`}</div>
          <div class="pid">${esc(p.page_id)}</div>
          ${p.status !== "ok" && p.status_msg ? `<div class="pmsg" style="color:var(--danger)">⚠️ ${esc(p.status_msg)}</div>` : ""}
          <div class="test-result" id="test-page-${esc(p.page_id)}"></div>
        </div>
        <div class="btns">
          <button class="btn btn-sm" data-act="test" data-id="${esc(p.page_id)}">🔍 Kiểm tra</button>
          <button class="btn btn-sm btn-danger" data-act="del" data-id="${esc(p.page_id)}">🗑️ Xóa</button>
        </div>
      </div>`).join("");
    box.querySelectorAll("button[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.dataset.act === "test") testPage(btn.dataset.id);
        else deletePage(btn.dataset.id);
      });
    });
  } catch (e) {
    box.innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}
      <br><button class="btn btn-sm" style="margin-top:8px" onclick="loadPages()">Thử lại</button></div>`;
  }
}

async function testPage(page_id) {
  const el = $(`test-page-${page_id}`);
  el.className = "test-result";
  el.textContent = "⏳ Đang kiểm tra…";
  try {
    const j = await api("/api/settings/test", {
      method: "POST", body: JSON.stringify({ type: "page", page_id }),
    });
    el.className = "test-result " + (j.ok ? "ok" : "fail");
    el.textContent = (j.ok ? "✅ " : "❌ ") + (j.msg || "");
    if (j.ok) loadPages();
  } catch (e) {
    el.className = "test-result fail";
    el.textContent = "❌ " + e.message;
  }
}

async function deletePage(page_id) {
  if (!confirm(`Xóa page ${page_id}? Inbox của page này sẽ không còn hoạt động.`)) return;
  try {
    const j = await api(`/api/pages/${encodeURIComponent(page_id)}`, { method: "DELETE" });
    if (j.ok) { toast("Đã xóa page.", "success", 2000); loadPages(); }
    else toast("Xóa page thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

$("btnAddPage").addEventListener("click", async () => {
  const page_id = $("p_id").value.trim();
  const name = $("p_name").value.trim();
  const token = $("p_token").value.trim();
  if (!page_id || !name || !token) { toast("Vui lòng nhập đủ Page ID, tên page và token.", "warning"); return; }
  try {
    const j = await api("/api/pages", { method: "POST", body: JSON.stringify({ page_id, name, token }) });
    if (j.ok) {
      toast("Đã thêm page ✓", "success");
      $("p_id").value = ""; $("p_name").value = ""; $("p_token").value = "";
      loadPages();
    } else toast(j.error_vi || j.msg || "Thêm page thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
});

/* ---------------- Vận chuyển ---------------- */

const CARRIERS = [
  {
    key: "ghn", label: "GHN — Giao Hàng Nhanh",
    fields: [
      { key: "token", label: "API Token", type: "password", ph: "Token lấy từ khachhang.ghn.vn" },
      { key: "shop_id", label: "ShopId", type: "text", ph: "Mã cửa hàng (số)" },
    ],
    guide: `
      <ol>
        <li>Đăng ký / đăng nhập tại <code>khachhang.ghn.vn</code> (xác thực tài khoản để dùng đủ tính năng).</li>
        <li>Bấm <b>tên tài khoản</b> (góc trên bên trái) → <b>Thông tin tài khoản</b> → tab <b>Bảo mật</b> → <b>Token API &amp; IP tin cậy</b> → <b>Quản lý</b> → bấm biểu tượng 👁, nhập <b>OTP qua SMS</b> để hiện token → sao chép.</li>
        <li>Lấy <b>ShopId</b>: mục <b>Quản lý cửa hàng</b> trên khachhang.ghn.vn (mỗi cửa hàng là một ShopId).</li>
        <li>Không cần ký hợp đồng — shop tự lấy token và dùng ngay.</li>
      </ol>`,
  },
  {
    key: "ghtk", label: "GHTK — Giao Hàng Tiết Kiệm",
    fields: [
      { key: "token", label: "API Token", type: "password", ph: "Token tạo từ trang khách hàng GHTK" },
      { key: "partner_code", label: "Mã shop (X-Client-Source)", type: "text", ph: "Mã shop của bạn" },
    ],
    guide: `
      <ol>
        <li>Đăng nhập trang khách hàng <code>khachhang.giaohangtietkiem.vn</code>.</li>
        <li>Vào <b>Thông tin shop → Cấu hình API</b> → bấm <b>+ Tạo token</b>.</li>
        <li>Đặt tên token (VD: "ShopDesk"), chọn <b>ngày hết hạn</b>, tick đủ quyền: <b>Tính phí, Tạo đơn hàng, Trạng thái đơn hàng, Huỷ đơn hàng, In nhãn đơn hàng</b>.</li>
        <li>Lưu <b>token</b> + <b>mã shop</b> (dùng làm X-Client-Source). Lưu ý: token có ngày hết hạn bắt buộc — hết hạn phải tạo token mới.</li>
      </ol>`,
  },
  {
    key: "viettelpost", label: "Viettel Post",
    fields: [
      { key: "username", label: "Tài khoản Viettel Post", type: "text", ph: "SĐT / username đăng nhập" },
      { key: "password", label: "Mật khẩu", type: "password", ph: "Mật khẩu tài khoản" },
    ],
    guide: `
      <ol>
        <li>Đăng ký tài khoản tại <code>viettelpost.vn</code> (cá nhân/shop đều được).</li>
        <li><b>Đăng nhập 1 lần</b> tại <code>partner.viettelpost.vn</code> bằng đúng tài khoản trên → tài khoản được tự động kích hoạt kết nối API.</li>
        <li>Nhập username + mật khẩu tài khoản vào đây — ShopDesk sẽ tự đăng nhập để lấy token (token dài hạn 1 năm).</li>
        <li>Bổ sung địa chỉ kho lấy hàng: <i>Cài đặt tài khoản → Cài đặt thông tin người gửi</i> trên trang Viettel Post.</li>
      </ol>`,
  },
  {
    key: "jt", label: "J&T Express",
    fields: [
      { key: "customer_code", label: "Mã khách hàng (customer code)", type: "text", ph: "Do bưu cục J&T cấp" },
      { key: "api_account", label: "API account", type: "text", ph: "Tài khoản trên open.jtexpress.vn" },
      { key: "api_key", label: "API key", type: "password", ph: "Key sau khi chứng thực developer" },
    ],
    guide: `
      <ol>
        <li><b>Bắt buộc ký hợp đồng</b> với J&amp;T Express Việt Nam trước (liên hệ bưu cục/kinh doanh J&amp;T) — không có đường tự đăng ký.</li>
        <li>Nhận <b>mã khách hàng (customer code)</b> do bưu cục đối tác cấp.</li>
        <li>Đăng ký tài khoản tại <code>open.jtexpress.vn</code>, hoàn thành <b>chứng thực developer</b> để mở toàn bộ quyền API.</li>
        <li>Nếu chưa ký hợp đồng, có thể để trống — ShopDesk sẽ báo "chưa cấu hình" khi tạo vận đơn J&amp;T.</li>
      </ol>`,
  },
  {
    key: "best", label: "Best Express",
    fields: [
      { key: "username", label: "Tên đăng nhập", type: "text", ph: "V9Cus… hoặc cus…" },
      { key: "password", label: "Mật khẩu", type: "password", ph: "Mật khẩu tài khoản BEST" },
    ],
    guide: `
      <ol>
        <li><b>Không có đường tự đăng ký API.</b> Liên hệ bộ phận kinh doanh Best Express — hotline <b>1900 1031</b> (hoặc (028) 730 86998) — để ký hợp đồng / kích hoạt tài khoản và xin tài liệu API đối tác.</li>
        <li>Tài khoản BEST của bạn phải <b>được kích hoạt</b> trước khi kết nối. Tên đăng nhập có dạng <code>V9Cus…</code> hoặc <code>cus...</code> (không phải email/SĐT).</li>
        <li>Nhập tên đăng nhập + mật khẩu vào đây. ⚠️ Endpoint API gốc của Best Express <b>chưa được hãng công bố công khai</b> — ShopDesk mới ở trạng thái chuẩn bị, tạo đơn API sẽ báo "chưa khả dụng" cho đến khi có tài liệu chính thức.</li>
      </ol>`,
  },
];

async function loadShipping() {
  const box = $("carrierList");
  box.innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải trạng thái hãng vận chuyển…</div>`;
  let settings = { shipping: {} };
  try {
    settings = await api("/api/settings");
  } catch (e) {
    box.innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}
      <br><button class="btn btn-sm" style="margin-top:8px" onclick="loadShipping()">Thử lại</button></div>`;
    return;
  }
  const shipping = settings.shipping || {};
  box.innerHTML = CARRIERS.map((c) => {
    const info = shipping[c.key] || {};
    const hasKey = !!info.api_key_set;
    return `
    <div class="carrier-card">
      <div class="carrier-head">
        <h3>${esc(c.label)}</h3>
        ${hasKey ? `<span class="status st-ok">Đã nhập key</span>` : `<span class="status st-warn">Chưa nhập key</span>`}
      </div>
      <div class="carrier-guide">📖 <b>Cách lấy key:</b>${c.guide}</div>
      ${c.fields.map((f) => `
        <label>${esc(f.label)}${f.type === "password" ? " (để trống = giữ key cũ)" : ""}</label>
        <input type="${f.type}" id="key-${c.key}-${f.key}" placeholder="${esc(f.ph || "")}" autocomplete="off">
      `).join("")}
      <div style="margin-top:10px;display:flex;gap:8px">
        <button class="btn btn-primary btn-sm" data-act="save" data-carrier="${c.key}">💾 Lưu</button>
        <button class="btn btn-sm" data-act="test" data-carrier="${c.key}">🔍 Kiểm tra kết nối</button>
      </div>
      <div class="test-result" id="test-${c.key}"></div>
    </div>`;
  }).join("");

  box.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const carrier = btn.dataset.carrier;
      if (btn.dataset.act === "save") saveCarrier(carrier);
      else testCarrier(carrier);
    });
  });
}

function carrierDef(key) { return CARRIERS.find((c) => c.key === key); }

async function saveCarrier(carrier) {
  const def = carrierDef(carrier);
  const body = {};
  for (const f of def.fields) {
    const v = $(`key-${carrier}-${f.key}`).value.trim();
    if (v) body[f.key] = v; // để trống password = giữ key cũ
  }
  if (!Object.keys(body).length) { toast("Chưa nhập gì để lưu.", "warning"); return; }
  try {
    const j = await api(`/api/settings/shipping/${encodeURIComponent(carrier)}`, {
      method: "POST", body: JSON.stringify(body),
    });
    if (j.ok) {
      toast(`Đã lưu key ${def.label} ✓`, "success");
      def.fields.forEach((f) => { $(`key-${carrier}-${f.key}`).value = ""; });
      loadShipping();
    } else toast(j.error_vi || j.msg || "Lưu thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

async function testCarrier(carrier) {
  const el = $(`test-${carrier}`);
  el.className = "test-result";
  el.textContent = "⏳ Đang kiểm tra…";
  try {
    const j = await api("/api/settings/test", {
      method: "POST", body: JSON.stringify({ type: "carrier", carrier }),
    });
    el.className = "test-result " + (j.ok ? "ok" : "fail");
    el.textContent = (j.ok ? "✅ " : "❌ ") + (j.msg || "");
  } catch (e) {
    el.className = "test-result fail";
    el.textContent = "❌ " + e.message;
  }
}

/* ---------------- Khởi động ---------------- */

loadPages();
loadShipping();

/* ---------------- Thông tin người gửi (in tem) ---------------- */

async function loadSender() {
  try {
    const j = await api("/api/settings/sender");
    const s = (j && j.sender) || {};
    $("s_shop").value = s.shop_name || "";
    $("s_phone").value = s.sender_phone || "";
    $("s_addr").value = s.sender_address || "";
  } catch (e) { /* bỏ qua */ }
}

async function saveSender() {
  const msg = $("senderMsg");
  msg.textContent = "⏳ Đang lưu…";
  msg.style.color = "var(--muted)";
  try {
    const j = await api("/api/settings/sender", {
      method: "POST",
      body: JSON.stringify({
        shop_name: $("s_shop").value.trim(),
        sender_phone: $("s_phone").value.trim(),
        sender_address: $("s_addr").value.trim(),
      }),
    });
    if (j.ok) {
      msg.textContent = "✅ Đã lưu.";
      msg.style.color = "var(--success)";
      toast("Đã lưu thông tin người gửi ✓", "success");
    } else {
      msg.textContent = "❌ " + (j.error_vi || "Lưu thất bại.");
      msg.style.color = "var(--danger)";
    }
  } catch (e) {
    msg.textContent = "❌ " + e.message;
    msg.style.color = "var(--danger)";
  }
}

$("btnSaveSender").addEventListener("click", saveSender);
loadSender();

/* ---------------- Kết nối Facebook (kiểu Sapo) ---------------- */

async function loadFbApp() {
  try {
    const j = await api("/api/connect/facebook/app");
    $("fb_app_id").value = j.app_id || "";
    $("fb_redirect").value = j.redirect_uri || "";
    if (j.app_secret_set) $("fb_app_secret").value = "••••••";
  } catch (e) { $("fb_redirect").value = "Không tải được."; }
}

async function saveFbApp() {
  const msg = $("fbMsg");
  msg.textContent = "⏳ Đang lưu…"; msg.style.color = "var(--muted)";
  try {
    const j = await api("/api/connect/facebook/app", {
      method: "POST",
      body: JSON.stringify({ app_id: $("fb_app_id").value.trim(), app_secret: $("fb_app_secret").value }),
    });
    if (j.ok) {
      msg.textContent = "✅ Đã lưu.";
      msg.style.color = "var(--success)";
      toast("Đã lưu Facebook App ✓", "success");
      loadFbApp();
    } else { msg.textContent = "❌ " + (j.error_vi || "Lưu thất bại."); msg.style.color = "var(--danger)"; }
  } catch (e) { msg.textContent = "❌ " + e.message; msg.style.color = "var(--danger)"; }
}

async function fbConnect() {
  const msg = $("fbMsg");
  msg.textContent = "⏳ Đang mở Facebook…"; msg.style.color = "var(--muted)";
  try {
    const j = await api("/api/connect/facebook/start");
    if (j.ok && j.url) { location.href = j.url; return; }
    msg.textContent = "❌ " + (j.error_vi || "Không tạo được link kết nối.");
    msg.style.color = "var(--danger)";
  } catch (e) { msg.textContent = "❌ " + e.message; msg.style.color = "var(--danger)"; }
}

$("btnSaveFbApp").addEventListener("click", saveFbApp);
$("btnFbConnect").addEventListener("click", fbConnect);
$("btnCopyRedirect").addEventListener("click", () => {
  const el = $("fb_redirect");
  el.select();
  try { document.execCommand("copy"); } catch (e) {}
  if (navigator.clipboard) navigator.clipboard.writeText(el.value).catch(() => {});
  toast("Đã copy redirect URI ✓", "success");
});
loadFbApp();
