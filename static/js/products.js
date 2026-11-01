/* ShopDesk — Quản lý sản phẩm theo SKU: tìm kiếm, lọc shop,
 * thêm/sửa/xóa qua modal, phân trang client 20 dòng/trang. */
"use strict";

const state = { products: [], page: 0 };
const PAGE_SIZE = 20;
const $ = (id) => document.getElementById(id);

function filters() {
  return {
    shop: $("fShop").value,
    q: $("fSearch").value.trim(),
  };
}

async function loadProducts() {
  const f = filters();
  const qs = new URLSearchParams();
  if (f.shop) qs.set("shop", f.shop);
  if (f.q) qs.set("q", f.q);
  const tbody = $("prodRows");
  tbody.innerHTML = `<tr><td colspan="10"><div class="state-loading"><span class="spinner"></span>Đang tải sản phẩm…</div></td></tr>`;
  try {
    const j = await api("/api/products?" + qs.toString());
    state.products = j.products || [];
    state.page = 0;
    renderProducts();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="10"><div class="state-error">⚠️ ${esc(e.message)}
      <br><button class="btn btn-sm" style="margin-top:8px" onclick="loadProducts()">Thử lại</button></div></td></tr>`;
  }
}

function stockBadge(stock) {
  if (stock === null || stock === undefined) {
    return `<span class="badge" style="background:#e5e7eb;color:#4b5563">Không giới hạn</span>`;
  }
  const n = Number(stock);
  if (n <= 0) {
    return `<span class="badge" style="background:#fecaca;color:#991b1b">Hết hàng</span>`;
  }
  if (n <= 5) {
    return `<span class="badge" style="background:#fef3c7;color:#92400e">Còn ${n}</span>`;
  }
  return `<span class="badge" style="background:#d1fae5;color:#065f46">${n}</span>`;
}

function imgCell(image) {
  if (!image) return `<span style="color:var(--muted)">—</span>`;
  const src = "/static/" + encodeURIComponent(image);
  return `<img src="${src}" alt="" style="width:48px;height:48px;object-fit:cover;border-radius:6px"
    onerror="this.outerHTML='<span style=&quot;color:var(--muted);font-size:12px&quot;>Lỗi ảnh</span>'">`;
}

function weightCell(w) {
  if (w === null || w === undefined || w === "") {
    return `<span style="color:var(--muted)">—</span>`;
  }
  return `<span style="white-space:nowrap">${Number(w)} g</span>`;
}

function renderProducts() {
  const tbody = $("prodRows");
  const total = state.products.length;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (state.page >= pages) state.page = pages - 1;
  const start = state.page * PAGE_SIZE;
  const rows = state.products.slice(start, start + PAGE_SIZE);

  $("prodCount").textContent = `Tổng ${total} sản phẩm`;
  $("pgInfo").textContent = `Trang ${state.page + 1}/${pages}`;
  $("pgPrev").disabled = state.page === 0;
  $("pgNext").disabled = state.page >= pages - 1;

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="10"><div class="state-empty">📭 Chưa có sản phẩm nào phù hợp.</div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((p) => `
    <tr data-id="${p.id}">
      <td class="cell-code" style="white-space:nowrap"><b>${esc(p.sku || "")}</b></td>
      <td>${esc(p.name || "")}</td>
      <td>${shopBadge(SHOP_LABEL[p.shop] || p.shop)}</td>
      <td>${esc(p.color || "—")}</td>
      <td>${esc(p.size || "—")}</td>
      <td class="cell-money">${fmtMoney(p.price)}</td>
      <td>${stockBadge(p.stock)}</td>
      <td>${weightCell(p.weight_grams)}</td>
      <td>${imgCell(p.image)}</td>
      <td>
        <div class="row-actions">
          <button class="btn btn-sm" data-act="edit" data-id="${p.id}">✏️ Sửa</button>
          <button class="btn btn-sm btn-danger" data-act="del" data-id="${p.id}">🗑️ Xóa</button>
        </div>
      </td>
    </tr>`).join("");

  tbody.querySelectorAll("button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      if (btn.dataset.act === "edit") openProductModal(id);
      else if (btn.dataset.act === "del") deleteProduct(id);
    });
  });
}

async function deleteProduct(id) {
  const p = state.products.find((x) => x.id === id);
  const sku = p ? p.sku : "#" + id;
  if (!confirm(`Xóa sản phẩm "${sku}"? Hành động này không thể hoàn tác.`)) return;
  try {
    const j = await api(`/api/products/${id}`, { method: "DELETE" });
    if (j.ok) { toast(`Đã xóa sản phẩm ${sku}`, "success", 2000); loadProducts(); }
    else toast("Xóa sản phẩm thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

/* ---------------- Modal thêm / sửa sản phẩm ---------------- */

function productFormHtml(p = {}) {
  const stockVal = p.stock === null || p.stock === undefined ? "" : p.stock;
  const weightVal = p.weight_grams === null || p.weight_grams === undefined ? "" : p.weight_grams;
  return `
    <div class="form-row">
      <div><label>Mã SKU *</label><input type="text" id="p_sku" value="${esc(p.sku || "")}"
        placeholder="VD: HANA-SUC-DEN-37"></div>
      <div><label>Shop *</label>
        <select id="p_shop">
          <option value="hana" ${(p.shop || "hana") === "hana" ? "selected" : ""}>Dép Hana</option>
          <option value="bedan" ${p.shop === "bedan" ? "selected" : ""}>Bé Đan</option>
          <option value="xinh" ${p.shop === "xinh" ? "selected" : ""}>Dép Xinh</option>
        </select></div>
    </div>
    <label>Tên sản phẩm *</label>
    <input type="text" id="p_name" value="${esc(p.name || "")}" placeholder="VD: Dép sục khoét lỗ">
    <div class="form-row">
      <div><label>Màu</label><input type="text" id="p_color" value="${esc(p.color || "")}"
        placeholder="VD: Đen, Nâu, Kem"></div>
      <div><label>Size</label><input type="text" id="p_size" value="${esc(p.size || "")}"
        placeholder="VD: 36–40"></div>
    </div>
    <div class="form-row">
      <div><label>Giá bán (đ) *</label><input type="number" id="p_price" value="${esc(String(p.price ?? ""))}"
        min="0" placeholder="VD: 65000"></div>
      <div><label>Tồn kho (bỏ trống = không giới hạn)</label><input type="number" id="p_stock"
        value="${esc(String(stockVal))}" min="0" placeholder="Không giới hạn"></div>
      <div><label>Trọng lượng (g/đôi, bỏ trống nếu chưa biết)</label><input type="number" id="p_weight"
        value="${esc(String(weightVal))}" min="0" placeholder="VD: 450"></div>
    </div>
    <label>Tên file ảnh (trong thư mục static/)</label>
    <input type="text" id="p_image" value="${esc(p.image || "")}" placeholder="VD: dep_suc_den.jpg">
    <label>Ghi chú</label>
    <input type="text" id="p_note" value="${esc(p.note || "")}">
  `;
}

function openProductModal(id = null) {
  const p = id == null ? {} : (state.products.find((x) => x.id === id) || {});
  const title = id == null ? "➕ Thêm sản phẩm" : `✏️ Sửa sản phẩm ${p.sku || "#" + id}`;
  openModal(title, productFormHtml(p),
    `<button class="btn" onclick="closeModal()">Hủy</button>
     <button class="btn btn-primary" id="p_save">Lưu</button>`);

  $("p_save").addEventListener("click", async () => {
    const sku = $("p_sku").value.trim();
    const name = $("p_name").value.trim();
    const stockRaw = $("p_stock").value.trim();
    const weightRaw = $("p_weight").value.trim();
    const payload = {
      sku,
      shop: $("p_shop").value,
      name,
      color: $("p_color").value.trim(),
      size: $("p_size").value.trim(),
      price: Number($("p_price").value) || 0,
      stock: stockRaw === "" ? null : Number(stockRaw),
      weight_grams: weightRaw === "" ? null : Number(weightRaw),
      image: $("p_image").value.trim(),
      note: $("p_note").value.trim(),
    };
    if (!sku || !name) {
      toast("Vui lòng nhập đủ: mã SKU và tên sản phẩm.", "warning");
      return;
    }
    try {
      const j = id == null
        ? await api("/api/products", { method: "POST", body: JSON.stringify(payload) })
        : await api(`/api/products/${id}`, { method: "PUT", body: JSON.stringify(payload) });
      if (j.ok) { closeModal(); toast(id == null ? `Đã thêm ${sku} ✓` : `Đã lưu ${sku} ✓`, "success"); loadProducts(); }
      else toast("Lưu sản phẩm thất bại.", "error");
    } catch (e) { toast(e.message, "error"); }
  });
}

/* ---------------- Phân trang + bộ lọc ---------------- */

$("pgPrev").addEventListener("click", () => {
  if (state.page > 0) { state.page--; renderProducts(); }
});
$("pgNext").addEventListener("click", () => {
  const pages = Math.ceil(state.products.length / PAGE_SIZE);
  if (state.page < pages - 1) { state.page++; renderProducts(); }
});

let searchT = null;
$("fSearch").addEventListener("input", () => {
  clearTimeout(searchT);
  searchT = setTimeout(loadProducts, 400);
});
$("fShop").addEventListener("change", loadProducts);
$("btnAdd").addEventListener("click", () => openProductModal(null));

loadProducts();
