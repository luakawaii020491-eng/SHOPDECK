/* ShopDesk — Bảng đơn hàng: lọc, thêm/sửa/xóa, đổi trạng thái nhanh,
 * tạo vận đơn + tra cứu 4 hãng VC. */
"use strict";

const state = { orders: [], page: 0, filter: { status: "", shop: "", q: "" }, view: "orders", attempts: [] };
const PER_PAGE = 20;
const $ = (id) => document.getElementById(id);

function filters() {
  const f = {
    status: $("fStatus").value,
    shop: $("fShop").value,
    q: $("fSearch").value.trim(),
    has_phone: $("fPhone").value,
    tag: $("fTag").value,
    date_from: $("fDateFrom").value,
    date_to: $("fDateTo").value,
    sku: $("fSku").value.trim(),
  };
  return f;
}

async function loadOrders() {
  const f = filters();
  const qs = new URLSearchParams();
  if (f.status) qs.set("status", f.status);
  if (f.shop) qs.set("shop", f.shop);
  if (f.q) qs.set("q", f.q);
  if (f.has_phone) qs.set("has_phone", f.has_phone);
  if (f.tag) qs.set("tag", f.tag);
  if (f.date_from) qs.set("date_from", f.date_from);
  if (f.date_to) qs.set("date_to", f.date_to);
  if (f.sku) qs.set("sku", f.sku);
  state.page = 0; // mỗi lần lọc mới -> về trang đầu
  const tbody = $("orderRows");
  tbody.innerHTML = `<tr><td colspan="12"><div class="state-loading"><span class="spinner"></span>Đang tải đơn hàng…</div></td></tr>`;
  try {
    const j = await api("/api/orders?" + qs.toString());
    state.orders = j.orders || [];
    renderOrders();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="12"><div class="state-error">⚠️ ${esc(e.message)}
      <br><button class="btn btn-sm" style="margin-top:8px" onclick="loadOrders()">Thử lại</button></div></td></tr>`;
  }
}

/** Đổ dropdown hashtag từ tag-defs + option "Không có tag". */
async function loadTagOptions() {
  const sel = $("fTag");
  try {
    const j = await api("/api/inbox/tag-defs");
    const defs = j.defs || {};
    sel.innerHTML = `<option value="">Tất cả</option>` +
      Object.entries(defs).map(([k, v]) => `<option value="${esc(k)}">#️⃣ ${esc(v.label)}</option>`).join("") +
      `<option value="__none__">Không có tag</option>`;
  } catch (e) {
    sel.innerHTML = `<option value="">Tất cả</option><option value="__none__">Không có tag</option>`;
  }
}

function fmtItems(items) {
  if (!items) return "";
  try {
    const arr = JSON.parse(items);
    if (Array.isArray(arr)) return arr.map((x) => `${x.name || ""}${x.qty ? " ×" + x.qty : ""}`).join("; ");
    return String(items);
  } catch (e) {
    return String(items);
  }
}

function renderOrders() {
  const tbody = $("orderRows");
  const total = state.orders.length;
  const pages = Math.max(1, Math.ceil(total / PER_PAGE));
  state.page = Math.min(state.page, pages - 1);
  const slice = state.orders.slice(state.page * PER_PAGE, (state.page + 1) * PER_PAGE);
  $("orderCount").textContent = total
    ? `Tổng ${total} đơn${pages > 1 ? ` — trang ${state.page + 1}/${pages}` : ""}`
    : "Chưa có đơn hàng nào phù hợp.";
  renderPager(pages);
  if (!slice.length) {
    tbody.innerHTML = `<tr><td colspan="12"><div class="state-empty">📭 Chưa có đơn hàng nào phù hợp.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = slice.map((o) => `
    <tr data-id="${o.id}">
      <td class="cell-id">#${o.id}</td>
      <td>${shopBadge(SHOP_LABEL[o.shop] || o.shop)}</td>
      <td style="white-space:nowrap">${esc(fmtTime(o.created_at))}</td>
      <td><b>${esc(o.customer_name || "")}</b></td>
      <td style="white-space:nowrap">${esc(o.phone || "")}</td>
      <td class="cell-addr">${esc(o.address || "")}</td>
      <td class="cell-items">${esc(fmtItems(o.items))}</td>
      <td class="cell-money">${fmtMoney(o.total)}</td>
      <td>
        <select class="status-select" data-id="${o.id}" title="Đổi trạng thái nhanh">
          ${Object.keys(STATUS_LABEL).map((s) =>
            `<option value="${s}" ${o.status === s ? "selected" : ""}>${STATUS_LABEL[s]}</option>`).join("")}
        </select>
      </td>
      <td>${esc(CARRIER_LABEL[o.shipping_carrier] || "—")}</td>
      <td class="cell-code">${esc(o.shipping_code || "—")}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-sm" data-act="ship" data-id="${o.id}" title="Tạo/tra cứu vận đơn">🚚 VC</button>
          <button class="btn btn-sm" data-act="edit" data-id="${o.id}">✏️ Sửa</button>
          <button class="btn btn-sm btn-danger" data-act="del" data-id="${o.id}">🗑️ Xóa</button>
        </div>
      </td>
    </tr>`).join("");

  tbody.querySelectorAll(".status-select").forEach((sel) => {
    sel.addEventListener("change", () => quickStatus(Number(sel.dataset.id), sel.value));
  });
  tbody.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      const act = btn.dataset.act;
      if (act === "edit") openOrderModal(id);
      else if (act === "del") deleteOrder(id);
      else if (act === "ship") openShipModal(id);
    });
  });
}

/** Phân trang client 20 đơn/trang. */
function renderPager(pages) {
  const el = $("pager");
  if (!el) return;
  if (pages <= 1) { el.innerHTML = ""; return; }
  const p = state.page;
  const nums = [...new Set([0, pages - 1, p - 1, p, p + 1])]
    .filter((n) => n >= 0 && n < pages).sort((a, b) => a - b);
  let html = `<button class="btn btn-sm" data-pg="prev"${p === 0 ? " disabled" : ""}>← Trước</button>`;
  let last = -1;
  for (const n of nums) {
    if (n - last > 1) html += `<span class="pager-dots">…</span>`;
    html += `<button class="btn btn-sm${n === p ? " btn-primary" : ""}" data-pg="${n}">${n + 1}</button>`;
    last = n;
  }
  html += `<button class="btn btn-sm" data-pg="next"${p === pages - 1 ? " disabled" : ""}>Sau →</button>`;
  el.innerHTML = html;
  el.querySelectorAll("button[data-pg]").forEach((b) => {
    b.addEventListener("click", () => {
      const d = b.dataset.pg;
      if (d === "prev") state.page--;
      else if (d === "next") state.page++;
      else state.page = Number(d);
      renderOrders();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  });
}

async function quickStatus(id, status) {
  try {
    const j = await api(`/api/orders/${id}`, { method: "PUT", body: JSON.stringify({ status }) });
    if (j.ok) { toast(`Đã chuyển đơn #${id} → ${STATUS_LABEL[status]}`, "success", 2000); loadOrders(); }
    else { toast("Đổi trạng thái thất bại.", "error"); loadOrders(); }
  } catch (e) { toast(e.message, "error"); loadOrders(); }
}

async function deleteOrder(id) {
  if (!confirm(`Xóa đơn #${id}? Hành động này không thể hoàn tác.`)) return;
  try {
    const j = await api(`/api/orders/${id}`, { method: "DELETE" });
    if (j.ok) { toast(`Đã xóa đơn #${id}`, "success", 2000); loadOrders(); }
    else toast("Xóa đơn thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

/* ---------------- Modal thêm / sửa đơn ---------------- */

function orderFormHtml(o = {}) {
  return `
    <div class="form-row">
      <div><label>Shop *</label>
        <select id="e_shop">
          <option value="hana" ${(o.shop || "hana") === "hana" ? "selected" : ""}>Dép Hana</option>
          <option value="bedan" ${o.shop === "bedan" ? "selected" : ""}>Bé Đan</option>
          <option value="xinh" ${o.shop === "xinh" ? "selected" : ""}>Dép Xinh</option>
        </select></div>
      <div><label>Trạng thái</label>
        <select id="e_status">
          ${Object.keys(STATUS_LABEL).map((s) =>
            `<option value="${s}" ${(o.status || "new") === s ? "selected" : ""}>${STATUS_LABEL[s]}</option>`).join("")}
        </select></div>
    </div>
    <div class="form-row">
      <div><label>Tên khách *</label><input type="text" id="e_name" value="${esc(o.customer_name || "")}"></div>
      <div><label>Số điện thoại *</label><input type="tel" id="e_phone" value="${esc(o.phone || "")}"></div>
    </div>
    <label>Địa chỉ *</label>
    <textarea id="e_addr" rows="2">${esc(o.address || "")}</textarea>
    <div class="form-row">
      <div><label>Mặt hàng *</label><input type="text" id="e_items" value="${esc(o._itemsText || "")}"></div>
      <div><label>Số lượng</label><input type="number" id="e_qty" value="${o._qty || 1}" min="1"></div>
    </div>
    <div class="form-row">
      <div><label>Tổng tiền (đ) *</label><input type="number" id="e_total" value="${o.total || ""}" min="0"></div>
      <div style="display:flex;align-items:flex-end"><button class="btn" id="e_suggest" type="button">💡 Gợi ý giá</button></div>
    </div>
    <div id="e_suggest_note" style="font-size:12.5px;color:var(--muted);margin-top:4px"></div>
    <label>Ghi chú</label>
    <input type="text" id="e_notes" value="${esc(o.notes || "")}">
  `;
}

function parseItemsForForm(items) {
  try {
    const arr = JSON.parse(items);
    if (Array.isArray(arr) && arr.length) {
      const names = arr.map((x) => x.name).filter(Boolean).join("; ");
      const qty = arr.reduce((s, x) => s + (Number(x.qty) || 0), 0) || 1;
      return { text: names, qty };
    }
  } catch (e) { /* giữ nguyên */ }
  return { text: String(items || ""), qty: 1 };
}

/* ---------------- Form thêm đơn: picker SKU dùng chung ---------------- */

function orderAddFormHtml() {
  return `
    <div class="form-row">
      <div><label>Shop *</label>
        <select id="e_shop">
          <option value="hana">Dép Hana</option>
          <option value="bedan">Bé Đan</option>
          <option value="xinh">Dép Xinh</option>
        </select></div>
      <div><label>Trạng thái</label>
        <select id="e_status">
          ${Object.keys(STATUS_LABEL).map((s) => `<option value="${s}">${STATUS_LABEL[s]}</option>`).join("")}
        </select></div>
    </div>
    <div class="form-row">
      <div><label>Tên khách *</label><input type="text" id="e_name"></div>
      <div><label>Số điện thoại *</label><input type="tel" id="e_phone"></div>
    </div>
    <label>Địa chỉ *</label>
    <textarea id="e_addr" rows="2"></textarea>
    <label>Sản phẩm (chọn theo SKU) *</label>
    ${skuPickerHTML("e")}
    <div class="form-row">
      <div><label>Tổng tiền (đ) *</label><input type="number" id="e_total" min="0" placeholder="0"></div>
      <div style="display:flex;align-items:flex-end"><button class="btn" id="e_suggest" type="button">💡 Tự tính từ SKU</button></div>
    </div>
    <div id="e_suggest_note" style="font-size:12.5px;color:var(--muted);margin-top:4px"></div>
    <label>Ghi chú</label>
    <input type="text" id="e_notes">
  `;
}

/** Tổng tiền dự kiến từ picker (tạm tính SKU×SL + ship). */
function addFormPreview() {
  const shop = $("e_shop").value;
  const items = skuPickerItems("e", shop);
  const sub = items.reduce((s, x) => s + x.price * x.qty, 0);
  const qty = items.reduce((s, x) => s + x.qty, 0);
  const fee = shipFeeFor(shop, qty);
  const unknown = items.some((x) => !x.known);
  $("e_suggest_note").textContent = items.length
    ? `Tạm tính ${fmtMoney(sub)} + ship ${fee ? fmtMoney(fee) : "miễn phí"} = ${fmtMoney(sub + fee)}${unknown ? " (có SKU chưa có trong danh mục)" : ""}`
    : "";
  return { total: sub + fee, allKnown: items.length > 0 && !unknown };
}

function openAddOrderModal() {
  openModal("➕ Thêm đơn hàng", orderAddFormHtml(),
    `<button class="btn" onclick="closeModal()">Hủy</button>
     <button class="btn btn-primary" id="e_save">Lưu</button>`);
  const modal = document.querySelector("#modalRoot .modal");
  if (modal) modal.classList.add("wide");

  wireSkuPicker("e", $("e_shop").value, addFormPreview);
  $("e_shop").addEventListener("change", () => wireSkuPicker("e", $("e_shop").value, addFormPreview));
  $("e_suggest").addEventListener("click", () => {
    const pv = addFormPreview();
    if (pv.allKnown && pv.total > 0) { $("e_total").value = pv.total; toast("Đã tự tính tổng tiền ✓", "success", 2000); }
    else toast("Chưa tính được: kiểm tra lại SKU các dòng hàng.", "warning");
  });

  $("e_save").addEventListener("click", async () => {
    const shop = $("e_shop").value;
    const items = skuPickerItems("e", shop);
    const name = $("e_name").value.trim();
    const phone = $("e_phone").value.trim();
    const addr = $("e_addr").value.trim();
    let total = Number($("e_total").value) || 0;
    if (!name || !phone || !addr || !items.length) {
      toast("Vui lòng nhập đủ: tên, SĐT, địa chỉ, sản phẩm.", "warning");
      return;
    }
    const bad = items.find((x) => !x.known);
    if (bad) {
      toast(`SKU "${bad.sku}" chưa có trong danh mục sản phẩm.`, "warning");
      return;
    }
    if (!total) {
      const pv = addFormPreview();
      if (pv.total > 0) { total = pv.total; $("e_total").value = total; }
    }
    if (!total) {
      toast("Vui lòng nhập tổng tiền (hoặc bấm 💡 Tự tính từ SKU).", "warning");
      return;
    }
    const payload = {
      shop,
      customer_name: name,
      phone,
      address: addr,
      items: JSON.stringify(items.map((x) => ({ sku: x.sku, name: x.name, qty: x.qty }))),
      total,
      status: $("e_status").value,
      notes: $("e_notes").value.trim(),
    };
    try {
      const j = await api("/api/orders", { method: "POST", body: JSON.stringify(payload) });
      if (j.ok) { closeModal(); toast(`Đã tạo đơn #${j.id} ✓`, "success"); loadOrders(); }
      else toast("Lưu đơn thất bại.", "error");
    } catch (e) { toast(e.message, "error"); }
  });
}

/* ---------------- Form sửa đơn: giữ nguyên đơn giản ---------------- */

function openOrderModal(id = null) {
  if (id == null) return openAddOrderModal();
  let o = state.orders.find((x) => x.id === id) || {};
  const p = parseItemsForForm(o.items);
  o = { ...o, _itemsText: p.text, _qty: p.qty };
  const title = `✏️ Sửa đơn #${id}`;
  openModal(title, orderFormHtml(o || {}),
    `<button class="btn" onclick="closeModal()">Hủy</button>
     <button class="btn btn-primary" id="e_save">Lưu</button>`);

  $("e_suggest").addEventListener("click", async () => {
    const qty = Number($("e_qty").value) || 1;
    const shop = $("e_shop").value;
    try {
      const j = await api(`/api/price_suggest?shop=${encodeURIComponent(shop)}&qty=${qty}`);
      $("e_total").value = j.total;
      $("e_suggest_note").textContent = j.note || "";
    } catch (e) { toast(e.message, "error"); }
  });

  $("e_save").addEventListener("click", async () => {
    const itemsText = $("e_items").value.trim();
    const qty = Number($("e_qty").value) || 1;
    const payload = {
      shop: $("e_shop").value,
      customer_name: $("e_name").value.trim(),
      phone: $("e_phone").value.trim(),
      address: $("e_addr").value.trim(),
      items: JSON.stringify([{ name: itemsText, qty }]),
      total: Number($("e_total").value) || 0,
      status: $("e_status").value,
      notes: $("e_notes").value.trim(),
    };
    if (!payload.customer_name || !payload.phone || !payload.address || !itemsText || !payload.total) {
      toast("Vui lòng nhập đủ: tên, SĐT, địa chỉ, mặt hàng, tổng tiền.", "warning");
      return;
    }
    try {
      const j = await api(`/api/orders/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      if (j.ok) { closeModal(); toast(`Đã lưu đơn #${id} ✓`, "success"); loadOrders(); }
      else toast("Lưu đơn thất bại.", "error");
    } catch (e) { toast(e.message, "error"); }
  });
}

/* ---------------- Vận đơn ---------------- */

const CARRIERS = [
  { key: "ghn", label: "GHN" },
  { key: "ghtk", label: "GHTK" },
  { key: "viettelpost", label: "Viettel Post" },
  { key: "jt", label: "J&T Express" },
  { key: "best", label: "Best Express" },
];

function openShipModal(id) {
  return _openShipModal(id);
}

async function _openShipModal(id) {
  let o = state.orders.find((x) => x.id === id);
  if (!o) {
    // Đơn có thể không nằm trong danh sách đang lọc (VD: mở từ Lịch sử đẩy đơn)
    try {
      const j = await api(`/api/orders/${id}`);
      o = j.order;
    } catch (e) {
      toast("Không tải được đơn #" + id + ": " + e.message, "error");
      return;
    }
  }
  if (!o) return;
  const body = `
    <p style="margin-top:0">Đơn <b>#${o.id}</b> — ${esc(o.customer_name || "")} · ${fmtMoney(o.total)}</p>
    ${o.shipping_code
      ? `<p>Mã vận đơn hiện tại: <span class="cell-code">${esc(o.shipping_code)}</span> (${esc(CARRIER_LABEL[o.shipping_carrier] || "")})</p>`
      : `<p style="color:var(--muted)">Chưa có mã vận đơn.</p>`}
    <label>Hãng vận chuyển</label>
    <select id="s_carrier">
      ${CARRIERS.map((c) => `<option value="${c.key}" ${o.shipping_carrier === c.key ? "selected" : ""}>${c.label}</option>`).join("")}
    </select>
    <div id="s_result" style="margin-top:12px"></div>
  `;
  openModal("🚚 Vận chuyển — đơn #" + id, body,
    `<button class="btn" onclick="closeModal()">Đóng</button>
     <button class="btn" id="s_track">🔍 Tra cứu</button>
     <button class="btn btn-primary" id="s_create">📦 Tạo vận đơn</button>`);

  $("s_create").addEventListener("click", async () => {
    const carrier = $("s_carrier").value;
    const carrierLabel = (CARRIERS.find((c) => c.key === carrier) || {}).label || carrier;
    $("s_result").innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tạo vận đơn…</div>`;
    try {
      const j = await api(`/api/shipping/${encodeURIComponent(carrier)}/create`, {
        method: "POST", body: JSON.stringify({ order_id: id }),
      });
      if (j.ok) {
        // Báo thành công rõ ràng: tên hãng + mã vận đơn
        $("s_result").innerHTML = `<div class="test-result ok" style="font-size:15px;padding:12px">✅ Đã tạo vận đơn <b>${esc(carrierLabel)}</b>: <span class="cell-code">${esc(j.code)}</span></div>`;
        toast(`✅ Đã tạo vận đơn ${carrierLabel}: ${j.code}`, "success", 6000);
        loadOrders();
        if (state.view === "attempts") loadAttempts();
      } else {
        // Báo thất bại: hiển thị NGUYÊN VĂN lý do tiếng Việt từ hãng, không nuốt lỗi
        const reason = j.error_vi || "Tạo vận đơn thất bại.";
        $("s_result").innerHTML = `<div class="test-result fail" style="font-size:14px;padding:12px">❌ Đẩy đơn thất bại: ${esc(reason)}</div>
          <p style="font-size:12.5px;color:var(--muted)">Nếu thiếu API key, vào <a href="/settings">Cài đặt → Vận chuyển</a> để nhập. Lần đẩy này đã được ghi vào 📜 Lịch sử đẩy đơn.</p>`;
        toast(`❌ Đẩy đơn thất bại: ${reason}`, "error", 8000);
        if (state.view === "attempts") loadAttempts();
      }
    } catch (e) {
      $("s_result").innerHTML = `<div class="test-result fail">❌ Đẩy đơn thất bại: ${esc(e.message)}</div>`;
      toast(`❌ Đẩy đơn thất bại: ${e.message}`, "error", 8000);
    }
  });

  $("s_track").addEventListener("click", async () => {
    const carrier = $("s_carrier").value;
    const code = o.shipping_code;
    if (!code) { toast("Đơn này chưa có mã vận đơn để tra cứu.", "warning"); return; }
    $("s_result").innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tra cứu…</div>`;
    try {
      const j = await api(`/api/shipping/${encodeURIComponent(carrier)}/track?code=${encodeURIComponent(code)}`);
      if (j.ok) {
        const hist = (j.history || []).map((h) =>
          `<li><div class="t">${esc(h.time || "")}</div><div>${esc(h.desc || "")}</div></li>`).join("");
        $("s_result").innerHTML = `
          <div class="test-result ok">📍 ${esc(j.status_vi || "")}</div>
          ${hist ? `<ul class="track-history">${hist}</ul>` : `<p style="color:var(--muted);font-size:13px">Chưa có lịch sử hành trình.</p>`}`;
      } else {
        $("s_result").innerHTML = `<div class="test-result fail">⚠️ ${esc(j.error_vi || "Tra cứu thất bại.")}</div>`;
      }
    } catch (e) {
      $("s_result").innerHTML = `<div class="test-result fail">⚠️ ${esc(e.message)}</div>`;
    }
  });
}

/* ---------------- Lịch sử đẩy đơn ---------------- */

const HEAD_ORDERS = `
        <tr>
          <th>ID</th><th>Shop</th><th>Ngày</th><th>Khách</th><th>SĐT</th>
          <th>Địa chỉ</th><th>Mặt hàng</th><th>Tổng tiền</th>
          <th>Trạng thái</th><th>Hãng VC</th><th>Mã vận đơn</th><th>Thao tác</th>
        </tr>`;
const HEAD_ATTEMPTS = `
        <tr>
          <th>Đơn</th><th>Hãng VC</th><th>Kết quả</th>
          <th>Thông điệp</th><th>Thời gian</th><th>Thao tác</th>
        </tr>`;

function setView(view) {
  state.view = view;
  $("tabOrders").className = "btn btn-sm" + (view === "orders" ? " btn-primary" : "");
  $("tabAttempts").className = "btn btn-sm" + (view === "attempts" ? " btn-primary" : "");
  document.querySelector(".toolbar").style.display = view === "orders" ? "" : "none";
  $("orderHead").innerHTML = view === "orders" ? HEAD_ORDERS : HEAD_ATTEMPTS;
  if (view === "orders") loadOrders();
  else loadAttempts();
}

async function loadAttempts() {
  const tbody = $("orderRows");
  tbody.innerHTML = `<tr><td colspan="6"><div class="state-loading"><span class="spinner"></span>Đang tải lịch sử đẩy đơn…</div></td></tr>`;
  $("orderCount").textContent = "";
  $("pager").innerHTML = "";
  try {
    const j = await api("/api/shipping/attempts?limit=100");
    state.attempts = j.attempts || [];
    renderAttempts();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="state-error">⚠️ ${esc(e.message)}</div></td></tr>`;
  }
}

function renderAttempts() {
  const tbody = $("orderRows");
  const rows = state.attempts;
  $("orderCount").textContent = rows.length ? `Tổng ${rows.length} lần đẩy đơn` : "Chưa có lần đẩy đơn nào.";
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="state-empty">📭 Chưa có lần đẩy đơn nào.<br>Mỗi lần bấm "Tạo vận đơn" (thành công hay thất bại) đều được ghi lại ở đây.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((a) => `
    <tr>
      <td class="cell-id">#${a.order_id}</td>
      <td>${esc(CARRIER_LABEL[a.carrier] || a.carrier || "—")}</td>
      <td>${a.success ? `<span class="status st-ok">✅ Thành công</span>` : `<span class="status st-err">❌ Thất bại</span>`}</td>
      <td class="cell-addr">${esc(a.message || "")}</td>
      <td style="white-space:nowrap">${esc(fmtTime(a.created_at))}</td>
      <td>
        ${a.success ? "" : `<button class="btn btn-sm btn-primary" data-retry="${a.order_id}" data-carrier="${esc(a.carrier || "")}">🔁 Thử lại</button>`}
      </td>
    </tr>`).join("");
  tbody.querySelectorAll("button[data-retry]").forEach((btn) => {
    btn.addEventListener("click", () => openShipModal(Number(btn.dataset.retry)));
  });
}

/* ---------------- Khởi động ---------------- */

$("btnFilter").addEventListener("click", loadOrders);
let searchT = null;
$("fSearch").addEventListener("input", () => {
  clearTimeout(searchT);
  searchT = setTimeout(loadOrders, 400);
});
$("fSku").addEventListener("input", () => {
  clearTimeout(searchT);
  searchT = setTimeout(loadOrders, 400);
});
$("fStatus").addEventListener("change", loadOrders);
$("fShop").addEventListener("change", loadOrders);
$("fPhone").addEventListener("change", loadOrders);
$("fTag").addEventListener("change", loadOrders);
$("fDateFrom").addEventListener("change", loadOrders);
$("fDateTo").addEventListener("change", loadOrders);
$("btnAdd").addEventListener("click", () => openOrderModal(null));
$("tabOrders").addEventListener("click", () => setView("orders"));
$("tabAttempts").addEventListener("click", () => setView("attempts"));

/* Prefill ô tìm kiếm từ query param ?q= (phục vụ link "Xem đơn" từ trang khách hàng). */
(function prefillSearch() {
  const q = new URLSearchParams(location.search).get("q");
  if (q) $("fSearch").value = q;
})();

loadTagOptions();
loadOrders();
