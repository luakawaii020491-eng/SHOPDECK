/* ShopDesk — Quản lý khách hàng: tìm kiếm, thêm/sửa/xóa, phân trang. */
"use strict";

const state = { customers: [], page: 1, q: "" };
const PER_PAGE = 20;
const $ = (id) => document.getElementById(id);

async function loadCustomers() {
  const q = $("fSearch").value.trim();
  state.q = q;
  state.page = 1;
  const tbody = $("custRows");
  tbody.innerHTML = `<tr><td colspan="7"><div class="state-loading"><span class="spinner"></span>Đang tải danh sách khách hàng…</div></td></tr>`;
  try {
    const qs = q ? "?q=" + encodeURIComponent(q) : "";
    const j = await api("/api/customers" + qs);
    state.customers = j.customers || [];
    renderPage();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="state-error">⚠️ ${esc(e.message)}
      <br><button class="btn btn-sm" style="margin-top:8px" onclick="loadCustomers()">Thử lại</button></div></td></tr>`;
  }
}

function totalPages() {
  return Math.max(1, Math.ceil(state.customers.length / PER_PAGE));
}

function renderPage() {
  const tbody = $("custRows");
  const total = state.customers.length;
  const pages = totalPages();
  if (state.page > pages) state.page = pages;
  const start = (state.page - 1) * PER_PAGE;
  const slice = state.customers.slice(start, start + PER_PAGE);

  $("custCount").textContent =
    `Tổng ${total} khách hàng` + (total > PER_PAGE ? ` — trang ${state.page}/${pages}` : "");

  if (!total) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="state-empty">📭 Chưa có khách hàng nào phù hợp.</div></td></tr>`;
  } else {
    tbody.innerHTML = slice.map((c) => `
      <tr data-id="${c.id}">
        <td><b>${esc(c.name || "—")}</b></td>
        <td style="white-space:nowrap">${esc(c.phone || "—")}</td>
        <td class="cell-addr">${esc(c.address || "—")}</td>
        <td>${c.shop ? shopBadge(SHOP_LABEL[c.shop] || c.shop) : "—"}</td>
        <td class="cell-addr">${esc(c.notes || "—")}</td>
        <td style="white-space:nowrap">${esc(fmtTime(c.created_at))}</td>
        <td>
          <div class="row-actions">
            <a class="btn btn-sm" href="/orders?q=${encodeURIComponent(c.phone || "")}" title="Xem đơn của khách này">📋 Xem đơn</a>
            <button class="btn btn-sm" data-act="edit" data-id="${c.id}">✏️ Sửa</button>
            <button class="btn btn-sm btn-danger" data-act="del" data-id="${c.id}">🗑️ Xóa</button>
          </div>
        </td>
      </tr>`).join("");
  }

  tbody.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      if (btn.dataset.act === "edit") openCustomerModal(id);
      else if (btn.dataset.act === "del") deleteCustomer(id);
    });
  });

  const pg = $("pagination");
  if (pages > 1) {
    pg.innerHTML = `
      <button class="btn btn-sm" id="pgPrev" ${state.page <= 1 ? "disabled" : ""}>← Trước</button>
      <span style="font-size:13px;color:var(--muted)">Trang ${state.page}/${pages}</span>
      <button class="btn btn-sm" id="pgNext" ${state.page >= pages ? "disabled" : ""}>Sau →</button>`;
    $("pgPrev").addEventListener("click", () => { state.page -= 1; renderPage(); });
    $("pgNext").addEventListener("click", () => { state.page += 1; renderPage(); });
  } else {
    pg.innerHTML = "";
  }
}

/* ---------------- Thêm / sửa khách hàng ---------------- */

function customerFormHtml(c = {}) {
  return `
    <div class="form-row">
      <div><label>Tên khách hàng</label><input type="text" id="c_name" value="${esc(c.name || "")}"></div>
      <div><label>Số điện thoại</label><input type="tel" id="c_phone" value="${esc(c.phone || "")}"
        placeholder="0901 234 567"></div>
    </div>
    <label>Địa chỉ</label>
    <textarea id="c_addr" rows="2">${esc(c.address || "")}</textarea>
    <div class="form-row">
      <div><label>Shop</label>
        <select id="c_shop">
          <option value="">—</option>
          <option value="hana" ${(c.shop || "") === "hana" ? "selected" : ""}>Dép Hana</option>
          <option value="bedan" ${(c.shop || "") === "bedan" ? "selected" : ""}>Bé Đan</option>
        </select></div>
    </div>
    <label>Ghi chú</label>
    <input type="text" id="c_notes" value="${esc(c.notes || "")}">
    <p style="font-size:12.5px;color:var(--muted)">💡 Khách có SĐT trùng sẽ được cập nhật thông tin mới nhất thay vì tạo mới.</p>
  `;
}

function openCustomerModal(id = null) {
  const c = id == null ? {} : (state.customers.find((x) => x.id === id) || {});
  const title = id == null ? "➕ Thêm khách hàng" : `✏️ Sửa khách hàng #${id}`;
  openModal(title, customerFormHtml(c),
    `<button class="btn" onclick="closeModal()">Hủy</button>
     <button class="btn btn-primary" id="c_save">Lưu</button>`);

  $("c_save").addEventListener("click", async () => {
    const payload = {
      name: $("c_name").value.trim(),
      phone: $("c_phone").value.trim(),
      address: $("c_addr").value.trim(),
      shop: $("c_shop").value,
      notes: $("c_notes").value.trim(),
    };
    if (!payload.name && !payload.phone) {
      toast("Vui lòng nhập ít nhất tên hoặc số điện thoại.", "warning");
      return;
    }
    try {
      const j = id == null
        ? await api("/api/customers", { method: "POST", body: JSON.stringify(payload) })
        : await api(`/api/customers/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      if (j.ok) {
        closeModal();
        toast(j.updated ? "SĐT đã tồn tại — đã cập nhật thông tin mới ✓"
                        : (id == null ? `Đã thêm khách hàng #${j.id} ✓` : "Đã lưu thông tin khách hàng ✓"),
              "success");
        loadCustomers();
      } else {
        toast("Lưu thất bại.", "error");
      }
    } catch (e) { toast(e.message, "error"); }
  });
}

async function deleteCustomer(id) {
  const c = state.customers.find((x) => x.id === id);
  const label = c ? (c.name || c.phone || ("#" + id)) : ("#" + id);
  if (!confirm(`Xóa khách hàng "${label}"? Hành động này không thể hoàn tác.`)) return;
  try {
    const j = await api(`/api/customers/${id}`, { method: "DELETE" });
    if (j.ok) { toast("Đã xóa khách hàng ✓", "success", 2000); loadCustomers(); }
    else toast("Xóa thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

/* ---------------- Khởi động ---------------- */

$("btnFilter").addEventListener("click", loadCustomers);
let searchT = null;
$("fSearch").addEventListener("input", () => {
  clearTimeout(searchT);
  searchT = setTimeout(loadCustomers, 400);
});
$("fSearch").addEventListener("keydown", (e) => { if (e.key === "Enter") loadCustomers(); });
$("btnAdd").addEventListener("click", () => openCustomerModal(null));

loadCustomers();
