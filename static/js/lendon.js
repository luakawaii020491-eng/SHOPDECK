/* ShopDesk — Trang "Lên đơn": tạo đơn hàng nhanh kiểu Sapo.
 * Cột trái: thông tin khách hàng + sản phẩm. Cột phải: thanh toán + vận chuyển. */
"use strict";

const $ = (id) => document.getElementById(id);
const fmtVnd = (n) => (Number(n) || 0).toLocaleString("vi-VN") + "đ";

const SHOP_VI = { hana: "Dép Hana", bedan: "Shop Bé Đan", xinh: "Dép Xinh" };
const CARRIER_VI = { ghn: "GHN", ghtk: "GHTK", viettelpost: "Viettel Post", jt: "J&T", best: "Best Express" };
const REQUIRE_VI = { view: "Cho xem hàng, không cho thử", cod_check: "Được đồng kiểm hàng", noview: "Không cho xem hàng" };

const state = {
  lines: [],            // {sku, name, price, qty, weight_grams}
  products: [],         // cache kết quả tìm kiếm
  suggestTotal: 0,      // tổng gợi ý từ /api/price_suggest
  suggestNote: "",
  searchTimer: null,
  creating: false,
  createdOrderId: null,
};

/* ---------------- Tìm kiếm sản phẩm ---------------- */

function bindSearch() {
  const input = $("pSearch"), box = $("pResults");
  input.addEventListener("input", () => {
    clearTimeout(state.searchTimer);
    const q = input.value.trim();
    if (q.length < 2) { box.classList.remove("show"); return; }
    state.searchTimer = setTimeout(() => searchProducts(q), 300);
  });
  input.addEventListener("blur", () => setTimeout(() => box.classList.remove("show"), 200));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); searchProducts(input.value.trim()); }
  });
}

async function searchProducts(q) {
  const shop = $("payShop").value;
  const box = $("pResults");
  box.innerHTML = `<div class="prod-item">⏳ Đang tìm…</div>`;
  box.classList.add("show");
  try {
    const j = await api(`/api/products?q=${encodeURIComponent(q)}&shop=${shop}`);
    state.products = j.products || [];
    if (!state.products.length) {
      box.innerHTML = `<div class="prod-item">Không tìm thấy sản phẩm nào.</div>`;
      return;
    }
    box.innerHTML = state.products.slice(0, 20).map((p, i) => `
      <div class="prod-item" data-i="${i}">
        <span class="price">${fmtVnd(p.price)}</span>
        <div><b>${esc(p.name || "")}</b></div>
        <div class="sku">${esc(p.sku || "")} · tồn: ${p.stock == null ? "?" : p.stock}</div>
      </div>`).join("");
    box.querySelectorAll(".prod-item[data-i]").forEach((el) => {
      el.addEventListener("mousedown", (e) => { e.preventDefault(); addLine(state.products[Number(el.dataset.i)]); });
    });
  } catch (e) {
    box.innerHTML = `<div class="prod-item">⚠️ ${esc(e.message)}</div>`;
  }
}

/* ---------------- Dòng hàng ---------------- */

function addLine(p) {
  const found = state.lines.find((l) => l.sku === p.sku);
  if (found) found.qty += 1;
  else state.lines.push({ sku: p.sku, name: p.name, price: Number(p.price) || 0, qty: 1, weight_grams: p.weight_grams });
  $("pSearch").value = "";
  $("pResults").classList.remove("show");
  renderLines();
}

function renderLines() {
  const tb = $("lineRows");
  if (!state.lines.length) {
    tb.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:18px">Chưa có sản phẩm nào — tìm và thêm ở ô phía trên.</td></tr>`;
  } else {
    tb.innerHTML = state.lines.map((l, i) => `
      <tr>
        <td><b>${esc(l.name)}</b></td>
        <td style="color:var(--muted);font-size:12px">${esc(l.sku)}</td>
        <td>${fmtVnd(l.price)}</td>
        <td><span class="qty-ctl">
          <button data-act="dec" data-i="${i}">−</button>
          <input type="number" min="1" value="${l.qty}" data-qty="${i}">
          <button data-act="inc" data-i="${i}">+</button>
        </span></td>
        <td><b>${fmtVnd(l.price * l.qty)}</b></td>
        <td><button class="btn btn-sm btn-danger" data-act="del" data-i="${i}">✕</button></td>
      </tr>`).join("");
    tb.querySelectorAll("[data-act]").forEach((b) => {
      b.addEventListener("click", () => {
        const i = Number(b.dataset.i), act = b.dataset.act;
        if (act === "inc") state.lines[i].qty += 1;
        if (act === "dec") state.lines[i].qty = Math.max(1, state.lines[i].qty - 1);
        if (act === "del") state.lines.splice(i, 1);
        renderLines();
      });
    });
    tb.querySelectorAll("input[data-qty]").forEach((inp) => {
      inp.addEventListener("change", () => {
        const i = Number(inp.dataset.qty);
        state.lines[i].qty = Math.max(1, Number(inp.value) || 1);
        renderLines();
      });
    });
  }
  recalc();
}

/* ---------------- Tính tiền ---------------- */

// Công thức phí ship theo shop (đồng bộ với server: _quick_ship_fee trong orders.py)
function formulaShipFee(shop, qty) {
  if (qty <= 0) return 0;
  if (shop === "hana") return qty === 1 ? 25000 : 0;
  return qty === 1 ? 30000 : 0; // bedan + xinh
}

async function recalc() {
  const shop = $("payShop").value;
  const goods = state.lines.reduce((s, l) => s + l.price * l.qty, 0);
  const qty = state.lines.reduce((s, l) => s + l.qty, 0);

  // Tổng gợi ý theo công thức shop (kể cả COD làm tròn của Dép Xinh)
  let suggest = goods, note = "";
  if (qty > 0) {
    try {
      const j = await api(`/api/price_suggest?shop=${shop}&qty=${qty}`);
      if (j.ok) { suggest = j.total; note = j.note || ""; }
    } catch (e) { /* giữ nguyên công thức client */ }
  }
  state.suggestTotal = suggest;
  state.suggestNote = note;

  const shipAuto = formulaShipFee(shop, qty);
  // Chỉ tự điền phí ship khi user chưa sửa tay trong phiên này
  if (!$("payShip").dataset.touched) $("payShip").value = shipAuto;

  const ship = Number($("payShip").value) || 0;
  const discount = Number($("payDiscount").value) || 0;
  const total = Math.max(0, suggest - discount);

  $("payGoods").textContent = fmtVnd(goods);
  $("priceNote").textContent = note ? ("💡 " + note) : "";
  $("payTotal").textContent = fmtVnd(total);

  const method = $("payMethod").value;
  const cod = method === "paid" ? 0 : total;
  $("payCod").textContent = fmtVnd(cod);

  // Khối lượng ước tính từ SKU; SKU chưa nhập cân nặng → mặc định 250g/đôi
  let w = state.lines.reduce((s, l) => s + (Number(l.weight_grams) || 250) * l.qty, 0);
  if (!$("shipWeight").dataset.touched) $("shipWeight").value = qty ? w : 0;
  if (!$("shipValue").dataset.touched) $("shipValue").value = goods;
  $("weightHint").textContent = qty
    ? `⚖️ Ước tính khối lượng: ${w}g (${qty} đôi) — SKU chưa nhập cân nặng tính mặc định 250g/đôi. Nhập cân nặng thật ở trang Sản phẩm để chính xác hơn.`
    : "";
}

function markTouched() {
  ["payShip", "payDiscount", "shipWeight", "shipValue"].forEach((id) => {
    $(id).addEventListener("input", () => { $(id).dataset.touched = "1"; recalc(); });
  });
  $("payShop").addEventListener("change", () => { delete $("payShip").dataset.touched; renderLines(); });
  $("payMethod").addEventListener("change", recalc);
}

/* ---------------- Tra khách cũ theo SĐT ---------------- */

async function lookupPhone() {
  const phone = $("cPhone").value.replace(/\D/g, "");
  if (phone.length < 9) { toast("Nhập SĐT hợp lệ (ít nhất 9 số) trước khi tra.", "warning"); return; }
  try {
    const j = await api(`/api/customers/by-phone?phone=${encodeURIComponent(phone)}`);
    const c = j.customer;
    if (c) {
      if (!$("cName").value.trim()) $("cName").value = c.name || "";
      if (!$("cAddress").value.trim()) $("cAddress").value = c.address || "";
      toast(`✅ Tìm thấy khách cũ: ${c.name || "(chưa có tên)"} — đã tự điền thông tin.`, "success");
    } else {
      toast("Chưa có khách hàng nào với SĐT này — đây là khách mới.", "info");
    }
  } catch (e) {
    toast("⚠️ " + e.message, "error");
  }
}

/* ---------------- Tạo đơn ---------------- */

function validate() {
  const phone = $("cPhone").value.replace(/\D/g, "");
  if (phone.length < 9) { toast("Thiếu số điện thoại khách hàng (ít nhất 9 số).", "warning"); $("cPhone").focus(); return null; }
  const address = $("cAddress").value.trim();
  if (!address) { toast("Thiếu địa chỉ nhận hàng.", "warning"); $("cAddress").focus(); return null; }
  if (!state.lines.length) { toast("Chưa chọn sản phẩm nào.", "warning"); $("pSearch").focus(); return null; }
  return { phone, address };
}

function buildNotes() {
  const parts = [];
  const cn = $("cNote").value.trim();
  const sn = $("shipNote").value.trim();
  const req = REQUIRE_VI[$("shipRequire").value];
  const method = $("payMethod").value;
  if (cn) parts.push("Ghi chú KH: " + cn);
  parts.push("Yêu cầu giao: " + req);
  if (sn) parts.push("Ghi chú shipper: " + sn);
  parts.push("TT: " + (method === "cod" ? "COD" : method === "paid" ? "Đã thanh toán" : "Chuyển khoản"));
  const svc = $("shipService").selectedOptions[0].textContent.trim();
  parts.push("Gói VC: " + svc);
  return parts.join(" | ");
}

async function createOrder(action) {
  if (state.creating) return;
  const v = validate();
  if (!v) return;
  state.creating = true;
  const btns = ["btnCreate", "btnCreatePrint", "btnCreatePush"];
  btns.forEach((id) => $(id).disabled = true);
  // Mở tab in trước khi gọi API để trình duyệt không chặn popup
  let printWin = null;
  if (action === "print") printWin = window.open("about:blank", "_blank");
  try {
    const shop = $("payShop").value;
    const carrier = $("shipCarrier").value;
    const body = {
      shop,
      customer_name: $("cName").value.trim(),
      phone: v.phone,
      address: v.address,
      items: state.lines.map((l) => ({ sku: l.sku, qty: l.qty })),
      notes: buildNotes(),
      create_shipment: action === "push" ? { carrier } : null,
    };
    const j = await api("/api/orders/quick", { method: "POST", body: JSON.stringify(body) });
    if (!j.ok) throw new Error(j.error_vi || "Không tạo được đơn hàng.");

    // Lưu tổng tiền cuối (sau giảm giá / phí ship sửa tay) + hãng VC đã chọn
    const ship = Number($("payShip").value) || 0;
    const discount = Number($("payDiscount").value) || 0;
    const finalTotal = Math.max(0, state.suggestTotal - discount);
    if (finalTotal !== j.total || action !== "push") {
      try {
        await api(`/api/orders/${j.order_id}`, {
          method: "PUT",
          body: JSON.stringify({ total: finalTotal, shipping_carrier: carrier }),
        });
      } catch (e) { /* không chặn luồng chính */ }
    }
    state.createdOrderId = j.order_id;
    showSuccess(j, finalTotal, carrier, action, v);
    toast(`✅ Đã tạo đơn #${j.order_id} — ${fmtVnd(finalTotal)}`, "success");
    if (printWin) printWin.location.href = `/print/label/${j.order_id}?carrier=${carrier}&print=1`;
  } catch (e) {
    toast("⚠️ " + e.message, "error");
  } finally {
    state.creating = false;
    btns.forEach((id) => $(id).disabled = false);
  }
}

function showSuccess(j, finalTotal, carrier, action, v) {
  const p = $("successPanel");
  const shipMsg = action === "push"
    ? (j.shipping_code
      ? `✅ Đã đẩy đơn sang <b>${esc(CARRIER_VI[carrier])}</b> — mã vận đơn: <b>${esc(j.shipping_code)}</b>`
      : `⚠️ Đẩy đơn thất bại: ${esc(j.shipment_error_vi || "lỗi không xác định")} — nhập API key ở <a href="/settings">⚙️ Cài đặt</a> rồi đẩy lại ở trang Đơn hàng.`)
    : `Chưa đẩy đơn — có thể đẩy sau ở trang <a href="/orders">🧾 Đơn hàng</a>.`;
  p.innerHTML = `
    <div class="success-box">
      <div style="font-size:16px;font-weight:800;margin-bottom:6px">🎉 Tạo đơn thành công — Đơn hàng #${j.order_id}</div>
      <div style="font-size:13.5px;line-height:1.7">
        🏪 ${esc(SHOP_VI[$("payShop").value])} · 👤 ${esc($("cName").value.trim() || "(chưa có tên)")} · 📞 ${esc(v.phone)}<br>
        💰 Tổng cộng: <b>${fmtVnd(finalTotal)}</b> · ${shipMsg}
      </div>
      <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
        <a class="btn" target="_blank" href="/print/label/${j.order_id}?carrier=${carrier}">🖨️ In tem ${esc(CARRIER_VI[carrier])}</a>
        ${action !== "push" ? `<button class="btn" id="btnPushNow">🚚 Đẩy đơn sang ${esc(CARRIER_VI[carrier])}</button>` : ""}
        <a class="btn" href="/orders">🧾 Xem đơn hàng</a>
        <button class="btn btn-primary" id="btnNewOrder">➕ Lên đơn mới</button>
      </div>
      <div id="pushResult" style="margin-top:8px;font-size:13px"></div>
    </div>`;
  p.classList.add("show");
  p.scrollIntoView({ behavior: "smooth", block: "start" });
  $("btnNewOrder").addEventListener("click", resetForm);
  const pn = $("btnPushNow");
  if (pn) pn.addEventListener("click", () => pushNow(j.order_id, carrier));
}

async function pushNow(orderId, carrier) {
  const el = $("pushResult");
  el.textContent = "⏳ Đang đẩy đơn…";
  try {
    const j = await api(`/api/shipping/${carrier}/create`, {
      method: "POST", body: JSON.stringify({ order_id: orderId }),
    });
    const code = j.shipping_code || j.code;
    if (j.ok && code) {
      el.innerHTML = `✅ Đã đẩy đơn — mã vận đơn: <b>${esc(code)}</b>`;
      toast("✅ Đẩy đơn thành công.", "success");
    } else {
      el.innerHTML = `⚠️ ${esc(j.error_vi || j.message || "Đẩy đơn thất bại.")}`;
      toast("⚠️ " + (j.error_vi || "Đẩy đơn thất bại."), "error");
    }
  } catch (e) {
    el.textContent = "⚠️ " + e.message;
  }
}

function resetForm() {
  state.lines = [];
  state.createdOrderId = null;
  ["cName", "cPhone", "cAddress", "cNote", "pSearch", "shipNote", "dimL", "dimW", "dimH"].forEach((id) => $(id).value = "");
  $("payDiscount").value = 0;
  ["payShip", "shipWeight", "shipValue"].forEach((id) => delete $(id).dataset.touched);
  $("successPanel").classList.remove("show");
  $("successPanel").innerHTML = "";
  renderLines();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

/* ---------------- Khởi động ---------------- */

document.addEventListener("DOMContentLoaded", () => {
  bindSearch();
  markTouched();
  $("btnLookupPhone").addEventListener("click", lookupPhone);
  $("cPhone").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); lookupPhone(); } });
  $("btnCreate").addEventListener("click", () => createOrder("create"));
  $("btnCreatePrint").addEventListener("click", () => createOrder("print"));
  $("btnCreatePush").addEventListener("click", () => createOrder("push"));
  $("btnReset").addEventListener("click", resetForm);
  // Prefill từ inbox (?phone=&name=&address=) — kiểu Sapo bấm "Tạo đơn" từ hội thoại
  try {
    const qs = new URLSearchParams(location.search);
    const ph = (qs.get("phone") || "").trim();
    const nm = (qs.get("name") || "").trim();
    const ad = (qs.get("address") || "").trim();
    if (ph) $("cPhone").value = ph;
    if (nm) $("cName").value = nm;
    if (ad) $("cAddress").value = ad;
    if (ph) setTimeout(lookupPhone, 600); // tự tra khách cũ để điền nốt
  } catch (e) { /* bỏ qua */ }
  renderLines();
});
