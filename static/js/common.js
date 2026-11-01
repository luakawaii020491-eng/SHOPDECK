/* ShopDesk — hàm dùng chung cho cả 3 trang */
"use strict";

const SHOP_LABEL = { hana: "Dép Hana", bedan: "Bé Đan" };
const STATUS_LABEL = {
  new: "Mới", pending: "Chờ xác nhận", shipped: "Đã gửi",
  done: "Hoàn thành", cancelled: "Hủy"
};
const CARRIER_LABEL = {
  ghn: "GHN", ghtk: "GHTK", viettelpost: "Viettel Post", jt: "J&T Express", best: "Best Express", "": "—"
};

/* Tag hội thoại inbox — dùng chung inbox + mọi nơi cần hiển thị tag. */
const TAG_ORDER = ["chot_don", "chua_chot", "thieu_dia_chi", "thieu_sdt", "da_chot_don", "da_day_dvvc"];
const TAG_LABEL = {
  chot_don: "Chốt đơn", chua_chot: "Chưa chốt",
  thieu_dia_chi: "Thiếu địa chỉ", thieu_sdt: "Thiếu SĐT",
  da_chot_don: "Đã chốt đơn", da_day_dvvc: "Đã đẩy sang ĐVVC"
};
const TAG_COLOR = {
  chot_don: "#16a34a", chua_chot: "#d97706",
  thieu_dia_chi: "#dc2626", thieu_sdt: "#dc2626",
  da_chot_don: "#2563eb", da_day_dvvc: "#7c3aed"
};

/** Gọi API backend (cùng origin). Ném lỗi với message tiếng Việt nếu mất kết nối. */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  }).catch(() => { throw new Error("Không kết nối được máy chủ ShopDesk. Kiểm tra backend có đang chạy không."); });
  let data = null;
  try { data = await res.json(); } catch (e) { /* không phải JSON */ }
  if (!res.ok) {
    const msg = (data && (data.error_vi || data.msg || data.error)) || `Lỗi HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

/** Escape HTML để tránh XSS từ tin nhắn khách. */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function fmtMoney(n) {
  const v = Number(n || 0);
  return v.toLocaleString("vi-VN") + "đ";
}

/** Định dạng thời gian Meta / SQLite về giờ VN, dạng "22:05 31/10". */
function fmtTime(t) {
  if (!t) return "";
  let s = String(t).trim().replace(" ", "T");
  if (!/([+-]\d{2}:?\d{2}|Z)$/.test(s) && s.length === 19) s += "+07:00";
  const d = new Date(s);
  if (isNaN(d.getTime())) return String(t);
  const p = (x) => String(x).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())} ${p(d.getDate())}/${p(d.getMonth() + 1)}`;
}

/** Thời gian tương đối ngắn cho list hội thoại: "5p", "2g", "31/10". */
function fmtRel(t) {
  if (!t) return "";
  let s = String(t).trim().replace(" ", "T");
  if (!/([+-]\d{2}:?\d{2}|Z)$/.test(s) && s.length === 19) s += "+07:00";
  const d = new Date(s);
  if (isNaN(d.getTime())) return "";
  const diff = Date.now() - d.getTime();
  if (diff < 0) return "vừa xong";
  const m = Math.floor(diff / 60000);
  if (m < 1) return "vừa xong";
  if (m < 60) return m + "p";
  const h = Math.floor(m / 60);
  if (h < 24) return h + "g";
  const p = (x) => String(x).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}`;
}

function toast(msg, type = "info", ms = 4500) {
  const root = document.getElementById("toastRoot");
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; }, ms - 300);
  setTimeout(() => el.remove(), ms);
}

/** Mở modal. Trả về hàm close(). */
function openModal(title, bodyHtml, footerHtml = "") {
  closeModal();
  const root = document.getElementById("modalRoot");
  const ov = document.createElement("div");
  ov.className = "modal-overlay";
  ov.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true">
      <div class="modal-header"><h3>${esc(title)}</h3>
        <button class="modal-close" aria-label="Đóng">✕</button></div>
      <div class="modal-body">${bodyHtml}</div>
      ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ""}
    </div>`;
  ov.addEventListener("click", (e) => { if (e.target === ov) closeModal(); });
  ov.querySelector(".modal-close").addEventListener("click", closeModal);
  root.appendChild(ov);
  document.addEventListener("keydown", escClose);
  return closeModal;
}
function escClose(e) { if (e.key === "Escape") closeModal(); }
function closeModal() {
  document.getElementById("modalRoot").innerHTML = "";
  document.removeEventListener("keydown", escClose);
}

/** Active nav theo body[data-page]. */
(function markNav() {
  const page = document.body.dataset.page;
  document.querySelectorAll(".nav-links a").forEach((a) => {
    if (a.dataset.nav === page) a.classList.add("active");
  });
})();

/** Badge shop theo tên page (fallback: tên page). */
function shopBadge(pageName) {
  const n = String(pageName || "").toLowerCase();
  if (n.includes("hana")) return `<span class="badge badge-hana">Dép Hana</span>`;
  if (n.includes("đan") || n.includes("dan")) return `<span class="badge badge-bedan">Bé Đan</span>`;
  return `<span class="badge badge-page">${esc(pageName || "")}</span>`;
}

/** Suy shop key ("hana"|"bedan") từ tên page; null nếu không nhận ra. */
function shopKeyFromPageName(pageName) {
  const n = String(pageName || "").toLowerCase();
  if (n.includes("hana")) return "hana";
  if (n.includes("đan") || n.includes("dan")) return "bedan";
  return null;
}

function statusBadge(st) {
  return `<span class="status st-${esc(st || "new")}">${esc(STATUS_LABEL[st] || st || "")}</span>`;
}

/* ---------- Tag badge (dùng màu inline từ API, fallback theo TAG_COLOR) ---------- */

/** Badge tag hội thoại. t = {tag, label?, color?, source? ('auto'|'manual')}.
 *  Tag tự động (source=auto) hiển thị icon 🤖 + tooltip phân biệt với tag gắn tay. */
function tagBadgeHTML(t, removable = false) {
  const raw = String(t.color || "");
  const c = /^#[0-9a-fA-F]{3,8}$/.test(raw) ? raw : (TAG_COLOR[t.tag] || "#64748b");
  const auto = t.source === "auto";
  const style = `background:${c}1a;color:${c};border-color:${c}66`;
  const title = auto ? ' title="Tự động từ hệ thống chốt đơn"' : "";
  const x = removable
    ? `<button class="tag-x" data-tag="${esc(t.tag)}" title="Gỡ tag">×</button>` : "";
  return `<span class="tag-badge" style="${style}"${title}>${auto ? "🤖 " : ""}${esc(t.label || TAG_LABEL[t.tag] || t.tag)}${x}</span>`;
}

/* ---------- Picker SKU dùng chung (modal tạo đơn inbox + form thêm đơn) ---------- */

const _productCache = {}; // shop -> [products]

/** Prefetch danh sách sản phẩm 1 lần theo shop (cache trong phiên). Lỗi -> ném ra, caller tự fallback. */
async function fetchProducts(shop) {
  const key = shop || "";
  if (_productCache[key]) return _productCache[key];
  const j = await api(`/api/products?shop=${encodeURIComponent(key)}`);
  const list = (j && j.products) || [];
  _productCache[key] = list;
  return list;
}

function productBySku(sku, shop) {
  const list = _productCache[shop || ""] || [];
  const s = String(sku || "").trim().toLowerCase();
  return list.find((p) => String(p.sku || "").trim().toLowerCase() === s) || null;
}

/** HTML khung picker: datalist autocomplete + vùng dòng hàng + nút thêm dòng. */
function skuPickerHTML(prefix) {
  return `<div class="sku-picker" id="${esc(prefix)}_picker">
    <datalist id="${esc(prefix)}_datalist"></datalist>
    <div class="sku-rows" id="${esc(prefix)}_rows"></div>
    <button type="button" class="btn btn-sm" id="${esc(prefix)}_add">➕ Thêm dòng</button>
  </div>`;
}

function skuRowHTML(prefix) {
  return `<div class="sku-row">
    <input type="text" class="sku-input" list="${esc(prefix)}_datalist" placeholder="Nhập SKU…" autocomplete="off">
    <input type="number" class="sku-qty" value="1" min="1" title="Số lượng">
    <span class="sku-price"></span>
    <button type="button" class="sku-del" title="Xóa dòng">🗑️</button>
  </div>`;
}

/** Gắn sự kiện cho picker: autocomplete datalist, thêm/xóa dòng, cập nhật giá từng dòng.
 *  onChange() được gọi mỗi khi dữ liệu dòng thay đổi (để preview tổng tiền). */
async function wireSkuPicker(prefix, shop, onChange) {
  const rowsEl = document.getElementById(prefix + "_rows");
  const addBtn = document.getElementById(prefix + "_add");
  rowsEl.innerHTML = "";
  const notify = () => { refreshSkuPrices(prefix, shop); if (onChange) onChange(); };
  const addRow = () => {
    rowsEl.insertAdjacentHTML("beforeend", skuRowHTML(prefix));
    const row = rowsEl.lastElementChild;
    row.querySelector(".sku-del").addEventListener("click", () => {
      if (rowsEl.querySelectorAll(".sku-row").length > 1) row.remove();
      else {
        row.querySelector(".sku-input").value = "";
        row.querySelector(".sku-qty").value = 1;
      }
      notify();
    });
    notify();
  };
  addBtn.onclick = addRow;
  rowsEl.oninput = notify;
  try {
    const products = await fetchProducts(shop);
    document.getElementById(prefix + "_datalist").innerHTML = products.map((p) =>
      `<option value="${esc(p.sku)}">${esc((p.name || p.sku) + " — " + fmtMoney(p.price))}</option>`).join("");
  } catch (e) {
    /* API sản phẩm chưa sẵn: vẫn cho nhập SKU tay, giá preview = 0 */
  }
  addRow();
}

/** Cập nhật cột giá/dòng (đơn giá × SL), cảnh báo SKU lạ / vượt tồn kho. */
function refreshSkuPrices(prefix, shop) {
  const rowsEl = document.getElementById(prefix + "_rows");
  if (!rowsEl) return;
  rowsEl.querySelectorAll(".sku-row").forEach((row) => {
    const sku = row.querySelector(".sku-input").value.trim();
    const qty = Number(row.querySelector(".sku-qty").value) || 0;
    const priceEl = row.querySelector(".sku-price");
    if (!sku) { priceEl.innerHTML = ""; return; }
    const p = productBySku(sku, shop);
    if (!p) { priceEl.innerHTML = `<span class="pv-warn">Chưa có SKU</span>`; return; }
    const unit = Number(p.price) || 0;
    let warn = "";
    if (p.stock != null && p.stock !== "" && qty > Number(p.stock)) {
      warn = ` <span class="pv-warn" title="Vượt tồn kho">⚠️ tồn ${esc(p.stock)}</span>`;
    }
    priceEl.innerHTML = `${fmtMoney(unit * qty)}${warn}`;
  });
}

/** Thu thập các dòng hàng đã nhập: [{sku, qty, price, name, known, stock}]. */
function skuPickerItems(prefix, shop) {
  const out = [];
  document.querySelectorAll(`#${prefix}_rows .sku-row`).forEach((row) => {
    const sku = row.querySelector(".sku-input").value.trim();
    const qty = Number(row.querySelector(".sku-qty").value) || 0;
    if (!sku || qty <= 0) return;
    const p = productBySku(sku, shop);
    out.push({
      sku, qty,
      price: p ? Number(p.price) || 0 : 0,
      name: p ? (p.name || sku) : sku,
      known: !!p,
      stock: p ? p.stock : null,
    });
  });
  return out;
}

/** Phí ship client-side (preview): hana 1 đôi +25k, bedan 1 đôi +30k, ≥2 đôi miễn ship. */
function shipFeeFor(shop, totalQty) {
  if (!totalQty || totalQty <= 0) return 0;
  if (shop === "bedan") return totalQty >= 2 ? 0 : 30000;
  return totalQty >= 2 ? 0 : 25000;
}
