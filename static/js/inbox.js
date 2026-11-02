/* ShopDesk — Inbox 3 khung kiểu Sapo: danh sách hội thoại | khung chat | thông tin khách.
 * Poll danh sách mỗi 5s (background); thread đang mở poll tin nhắn mỗi 5s. */
"use strict";

const POLL_MS = 5000;
const AVATAR_GRADS = [
  "linear-gradient(135deg,#8b5cf6,#6366f1)",
  "linear-gradient(135deg,#1877f2,#0d5cc0)",
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#10b981,#0d9488)",
  "linear-gradient(135deg,#ec4899,#8b5cf6)",
  "linear-gradient(135deg,#06b6d4,#3b82f6)",
];
const STATUS_VI = { new: "Mới", pending: "Chờ xử lý", shipped: "Đã gửi hàng", done: "Hoàn tất", cancelled: "Đã hủy" };

const state = {
  pages: [],
  page_id: "",
  convs: [],
  open: null,          // {page_id, page_name, conv_id, name, psid, phone}
  lastMsgId: null,
  assets: null,
  tags: {},            // "page_id/conv_id" -> [tags]
  tagDefs: {},
  filter: "",          // "" | "unreplied" | "closed"
  search: "",
  cust: null,          // customer record
  custOrders: [],
  listLoading: false,
  msgLoading: false,
  msgTimer: null,
};

const $ = (id) => document.getElementById(id);

function avatarGrad(name) {
  let h = 0;
  for (const ch of String(name || "?")) h = (h * 31 + ch.codePointAt(0)) % 997;
  return AVATAR_GRADS[h % AVATAR_GRADS.length];
}
function initialOf(name) {
  return ((name || "?").trim().charAt(0) || "?").toUpperCase();
}
function normPhone(s) {
  return String(s || "").replace(/\D/g, "").replace(/^84/, "0");
}
function findPhoneInMsgs(msgs) {
  for (const m of [...msgs].reverse()) {
    const t = String(m.text || "");
    const mt = t.replace(/[\s.\-]/g, "").match(/0\d{9}/);
    if (mt) return normPhone(mt[0]);
  }
  return "";
}

/* ---------------- Pages ---------------- */

async function loadPages() {
  try {
    const j = await api("/api/pages");
    state.pages = j.pages || [];
  } catch (e) {
    state.pages = [];
    $("convList").innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}</div>`;
    return;
  }
  const sel = $("pageSel");
  sel.innerHTML = state.pages.length
    ? state.pages.map((p) => `<option value="${esc(p.page_id)}">${esc(p.name)}${p.status === "ok" ? "" : " ⚠️"}</option>`).join("")
    : `<option value="">Chưa có page nào</option>`;
  if (state.pages.length) {
    state.page_id = state.pages[0].page_id;
    sel.value = state.page_id;
  }
  sel.onchange = () => {
    state.page_id = sel.value;
    state.open = null;
    resetChatPane();
    resetCustPane();
    loadConvs(false);
  };
}

/* ---------------- Danh sách hội thoại ---------------- */

async function loadConvs(background = false) {
  if (state.listLoading || !state.page_id) return;
  state.listLoading = true;
  if (!background) $("convList").innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải hội thoại…</div>`;
  try {
    const cj = await api(`/api/pages/${encodeURIComponent(state.page_id)}/conversations?limit=25`);
    state.convs = (cj.conversations || []).map((c) => ({ ...c, page_id: state.page_id }));
    state.convs.sort((a, b) => String(b.updated_time || "").localeCompare(String(a.updated_time || "")));
    try {
      const tj = await api(`/api/inbox/tags/by-page/${encodeURIComponent(state.page_id)}`);
      const threads = (tj && tj.threads) || {};
      state.tags = {};
      for (const [tid, tags] of Object.entries(threads)) state.tags[state.page_id + "/" + tid] = tags || [];
    } catch (e) { /* tag chưa có: bỏ qua */ }
    renderConvList();
  } catch (e) {
    if (!background || !state.convs.length) {
      $("convList").innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}<br>
        <button class="btn btn-sm" style="margin-top:8px" onclick="loadConvs(false)">Thử lại</button></div>`;
    }
  } finally {
    state.listLoading = false;
  }
}

function isClosedConv(c) {
  const tags = state.tags[c.page_id + "/" + c.id] || [];
  return tags.some((t) => ["chot_don", "da_chot_don"].includes(t.tag));
}

function visibleConvs() {
  const q = state.search.trim().toLowerCase();
  return state.convs.filter((c) => {
    if (state.filter === "unreplied" && !c.needs_reply) return false;
    if (state.filter === "closed" && !isClosedConv(c)) return false;
    if (q && !(String(c.name || "").toLowerCase().includes(q) || String(c.snippet || "").toLowerCase().includes(q))) return false;
    return true;
  });
}

function renderConvList() {
  const list = $("convList");
  const visible = visibleConvs();
  if (!visible.length) {
    list.innerHTML = state.convs.length
      ? `<div class="state-empty">🔎 Không có hội thoại nào khớp bộ lọc.</div>`
      : `<div class="state-empty">📭 Chưa có hội thoại nào.</div>`;
    return;
  }
  const scrollTop = list.scrollTop;
  list.innerHTML = visible.map((c) => {
    const active = state.open && state.open.conv_id === c.id;
    const closed = isClosedConv(c);
    const tags = (state.tags[c.page_id + "/" + c.id] || []).slice(0, 2);
    return `
    <div class="conv-item ${active ? "active" : ""} ${c.needs_reply ? "unread" : ""}" data-conv="${esc(c.id)}">
      <div class="avatar" style="background:${avatarGrad(c.name)}">${esc(initialOf(c.name))}</div>
      <div class="cinfo">
        <div class="cname">${c.needs_reply ? '<span class="dot"></span>' : ""}<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.name || "(không tên)")}</span></div>
        <div class="snippet">${esc(c.snippet || "")}</div>
        <div class="tags">${closed ? '<span class="badge-closed">ĐÃ CHỐT ĐƠN</span>' : ""}${tags.map((t) => `<span class="tagchip">${esc(t.label || t.tag)}</span>`).join("")}</div>
      </div>
      <div class="ctime">${esc(fmtRel(c.updated_time))}</div>
    </div>`;
  }).join("");
  list.scrollTop = scrollTop;
  list.querySelectorAll(".conv-item").forEach((el) => {
    el.addEventListener("click", () => openThread(el.dataset.conv));
  });
}

/* ---------------- Mở thread ---------------- */

function resetChatPane() {
  $("chatHead").innerHTML = `<div class="empty-pane" style="padding:8px">👈 Chọn một hội thoại ở cột bên trái để bắt đầu</div>`;
  $("chatMsgs").innerHTML = `<div class="state-empty">Chưa có tin nhắn nào.</div>`;
  setComposer(false);
}
function resetCustPane() {
  $("custBody").innerHTML = `<div class="empty-pane">Chọn hội thoại để xem<br>thông tin khách hàng</div>`;
}

async function openThread(conv_id) {
  const c = state.convs.find((x) => x.id === conv_id);
  if (!c) return;
  const page = state.pages.find((p) => p.page_id === state.page_id) || {};
  state.open = { page_id: state.page_id, page_name: page.name || "", conv_id, name: c.name || "", psid: null, phone: "" };
  state.cust = null; state.custOrders = [];
  state.lastMsgId = null;
  if (state.msgTimer) { clearInterval(state.msgTimer); state.msgTimer = null; }

  const tags = state.tags[state.page_id + "/" + conv_id] || [];
  $("chatHead").innerHTML = `
    <div class="avatar" style="background:${avatarGrad(c.name)}">${esc(initialOf(c.name))}</div>
    <div class="who">
      <div class="nm">${esc(c.name || "(không tên)")}</div>
      <div class="sub">${esc(page.name || "")} · ${tags.map((t) => `<span class="tagchip">${esc(t.label || t.tag)}</span>`).join(" ")}</div>
    </div>`;
  $("chatMsgs").innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải tin nhắn…</div>`;
  setComposer(false);
  renderConvList();
  resetCustPane();
  await loadMessages(false);
  state.msgTimer = setInterval(() => loadMessages(true), POLL_MS);
}

function setComposer(on) {
  ["msgInput", "btnSend", "btnImg", "btnTag", "btnQuickOrder"].forEach((id) => { $(id).disabled = !on; });
}

async function loadMessages(background = false) {
  if (!state.open || state.msgLoading) return;
  const { page_id, conv_id } = state.open;
  state.msgLoading = true;
  try {
    const j = await api(`/api/pages/${encodeURIComponent(page_id)}/conversations/${encodeURIComponent(conv_id)}/messages?limit=30`);
    const msgs = j.messages || [];
    if (msgs.length) {
      const cust = [...msgs].reverse().find((m) => !m.mine && m.from_id);
      if (cust) state.open.psid = cust.from_id;
      const phone = findPhoneInMsgs(msgs);
      if (phone && phone !== state.open.phone) {
        state.open.phone = phone;
        loadCustomerPanel(phone);
      }
    }
    const lastId = msgs.length ? msgs[msgs.length - 1].id : null;
    const changed = lastId !== state.lastMsgId;
    state.lastMsgId = lastId;
    if (changed || !background) {
      renderMessages(msgs);
      setComposer(true);
    }
  } catch (e) {
    if (!background) $("chatMsgs").innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}</div>`;
  } finally {
    state.msgLoading = false;
  }
}

function renderMessages(msgs) {
  const box = $("chatMsgs");
  if (!msgs.length) { box.innerHTML = `<div class="state-empty">Chưa có tin nhắn nào.</div>`; return; }
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 90;
  let lastDay = "";
  box.innerHTML = msgs.map((m) => {
    const day = String(m.created_time || "").slice(0, 10);
    const sep = day && day !== lastDay ? `<div class="day-sep">${esc(day.split("-").reverse().join("/"))}</div>` : "";
    lastDay = day || lastDay;
    const atts = (m.attachments || []).map((a) => {
      if (a.type === "image" && a.url) return `<a href="${esc(a.url)}" target="_blank" rel="noopener"><img class="att" src="${esc(a.url)}" loading="lazy"></a>`;
      return `<div style="font-size:12px;margin-top:4px">📎 Tệp đính kèm</div>`;
    }).join("");
    return `${sep}<div class="msg ${m.mine ? "me" : "them"}">${m.text ? esc(m.text) : ""}${atts}<span class="ts">${esc(fmtTime(m.created_time))}</span></div>`;
  }).join("");
  if (nearBottom) box.scrollTop = box.scrollHeight;
}

/* ---------------- Gửi tin nhắn / ảnh ---------------- */

async function sendText() {
  const input = $("msgInput");
  const text = input.value.trim();
  if (!text || !state.open) return;
  if (!state.open.psid) { toast("Chưa xác định được người nhận (thread chưa có tin nhắn từ khách).", "warning"); return; }
  $("btnSend").disabled = true;
  try {
    const j = await api(`/api/pages/${encodeURIComponent(state.open.page_id)}/send`, {
      method: "POST", body: JSON.stringify({ psid: state.open.psid, text }),
    });
    if (j.ok) { input.value = ""; await loadMessages(false); }
    else toast(j.error_vi || "Gửi tin nhắn thất bại.", "error", 7000);
  } catch (e) { toast(e.message, "error", 7000); }
  finally { $("btnSend").disabled = false; input.focus(); }
}

async function ensureAssets() {
  if (state.assets) return state.assets;
  state.assets = await api("/api/assets");
  return state.assets;
}

async function toggleImgDropdown() {
  const dd = $("imgDropdown");
  if (!dd.classList.contains("hidden")) { dd.classList.add("hidden"); return; }
  if (!state.open) return;
  const shop = shopKeyFromPageName(state.open.page_name) || "hana";
  try {
    const assets = await ensureAssets();
    const files = assets[shop] || [];
    dd.innerHTML = files.length
      ? files.map((f) => `<img src="/static/${esc(f)}" data-file="${esc(f)}" loading="lazy" title="${esc(f)}">`).join("")
      : `<div class="state-empty" style="grid-column:1/-1">Không có ảnh cho shop này.</div>`;
    dd.querySelectorAll("img[data-file]").forEach((im) => {
      im.addEventListener("click", () => sendImage(im.dataset.file));
    });
  } catch (e) { dd.innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}</div>`; }
  dd.classList.remove("hidden");
}

async function sendImage(file) {
  $("imgDropdown").classList.add("hidden");
  if (!state.open || !state.open.psid) { toast("Chưa xác định được người nhận.", "warning"); return; }
  toast("Đang gửi ảnh…", "info", 2500);
  try {
    const j = await api(`/api/pages/${encodeURIComponent(state.open.page_id)}/send_image`, {
      method: "POST", body: JSON.stringify({ psid: state.open.psid, image: file }),
    });
    if (j.ok) { toast("Đã gửi ảnh ✓", "success", 2000); await loadMessages(false); }
    else toast(j.error_vi || "Gửi ảnh thất bại.", "error", 7000);
  } catch (e) { toast(e.message, "error", 7000); }
}

/* ---------------- Tag ---------------- */

function openTagModal() {
  if (!state.open) return;
  const tags = state.tags[state.open.page_id + "/" + state.open.conv_id] || [];
  const current = new Set(tags.map((t) => t.tag));
  openModal("🏷️ Tag hội thoại",
    `<div style="display:flex;flex-wrap:wrap;gap:8px">` +
    TAG_ORDER.map((t) => `
      <button class="btn btn-sm ${current.has(t) ? "btn-primary" : ""}" data-tag="${t}">
        ${current.has(t) ? "✓ " : ""}${esc(TAG_LABEL[t] || t)}
      </button>`).join("") + `</div>
      <p class="hint">Bấm để gắn / gỡ tag. Tag "Đã chốt đơn" dùng để lọc ở cột trái.</p>`,
    `<button class="btn" onclick="closeModal()">Đóng</button>`);
  document.querySelectorAll("#modalRoot [data-tag]").forEach((b) => {
    b.addEventListener("click", async () => {
      const tag = b.dataset.tag;
      const has = current.has(tag);
      const url = `/api/inbox/${encodeURIComponent(state.open.page_id)}/${encodeURIComponent(state.open.conv_id)}/tags`;
      try {
        const j = await api(url, { method: has ? "DELETE" : "POST", body: JSON.stringify({ tag }) });
        if (j && j.ok) {
          const tj = await api(url);
          state.tags[state.open.page_id + "/" + state.open.conv_id] = (tj && tj.tags) || [];
          closeModal(); openTagModal(); renderConvList();
          openThreadHeaderTags();
        } else toast((j && j.error_vi) || "Lỗi tag.", "error");
      } catch (e) { toast(e.message, "error"); }
    });
  });
}

function openThreadHeaderTags() {
  if (!state.open) return;
  const tags = state.tags[state.open.page_id + "/" + state.open.conv_id] || [];
  const sub = document.querySelector("#chatHead .sub");
  if (sub) sub.innerHTML = `${esc(state.open.page_name)} · ${tags.map((t) => `<span class="tagchip">${esc(t.label || t.tag)}</span>`).join(" ")}`;
}

/* ---------------- Panel thông tin khách (cột phải) ---------------- */

async function loadCustomerPanel(phone) {
  const body = $("custBody");
  body.innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải thông tin khách…</div>`;
  let cust = null, orders = [];
  try {
    const j = await api(`/api/customers/by-phone?phone=${encodeURIComponent(phone)}`);
    cust = (j && j.customer) || null;
  } catch (e) { /* khách mới */ }
  try {
    const oj = await api(`/api/orders?q=${encodeURIComponent(phone)}`);
    orders = (oj && oj.orders) || [];
  } catch (e) { /* bỏ qua */ }
  state.cust = cust; state.custOrders = orders;
  renderCustomerPanel(phone);
}

function renderCustomerPanel(phone) {
  const body = $("custBody");
  const cust = state.cust || {};
  const name = cust.name || (state.open && state.open.name) || "(chưa có tên)";
  const addr = cust.address || "";
  const notes = cust.notes || "";
  const orders = state.custOrders || [];
  body.innerHTML = `
    <div class="cust-hero">
      <div class="avatar" style="background:${avatarGrad(name)}">${esc(initialOf(name))}</div>
      <div class="nm">${esc(name)}</div>
      <div class="ph"><a href="tel:${esc(phone)}">📞 ${esc(phone)}</a></div>
      <div style="margin-top:6px"><span class="tagchip">Bán lẻ</span> ${orders.length ? `<span class="tagchip">${orders.length} đơn</span>` : ""}</div>
    </div>
    <div class="cust-sec">
      <h4>📍 Địa chỉ <button class="btn btn-sm" id="btnEditAddr">Sửa</button></h4>
      <div class="cust-addr" id="custAddr">${esc(addr) || '<span style="color:var(--muted)">Chưa có địa chỉ</span>'}</div>
    </div>
    <div class="cust-sec">
      <h4>🧾 Đơn hàng (${orders.length})</h4>
      <div id="custOrders">${orders.length ? orders.slice(0, 5).map((o) => `
        <div class="order-mini"><span class="st">${esc(STATUS_VI[o.status] || o.status || "")}</span>
          <div class="ot">#${o.id} · ${fmtMoney(o.total)}</div>
          <div style="color:var(--muted)">${esc((o.created_at || "").slice(0, 10))} · ${esc(o.shop || "")}</div>
        </div>`).join("") : '<div style="font-size:13px;color:var(--muted)">Chưa có đơn hàng nào.</div>'}</div>
    </div>
    <div class="cust-sec">
      <h4>📝 Ghi chú</h4>
      <textarea class="cust-note" id="custNote" placeholder="Ghi chú về khách hàng…">${esc(notes)}</textarea>
      <button class="btn btn-sm" id="btnSaveNote" style="margin-top:6px">💾 Lưu ghi chú</button>
    </div>
    <button class="btn-order-big" id="btnGoLendon">🛍️ Tạo đơn (F1)</button>`;
  $("btnGoLendon").addEventListener("click", goLendon);
  $("btnSaveNote").addEventListener("click", saveCustNote);
  $("btnEditAddr").addEventListener("click", editCustAddr);
}

function goLendon() {
  if (!state.open) return;
  const qs = new URLSearchParams();
  if (state.open.phone) qs.set("phone", state.open.phone);
  const nm = (state.cust && state.cust.name) || state.open.name || "";
  if (nm) qs.set("name", nm);
  const ad = (state.cust && state.cust.address) || "";
  if (ad) qs.set("address", ad);
  location.href = "/lendon?" + qs.toString();
}

async function saveCustNote() {
  if (!state.cust) { toast("Chưa có hồ sơ khách hàng để lưu (khách mới).", "warning"); return; }
  try {
    const j = await api(`/api/customers/${state.cust.id}`, {
      method: "PUT", body: JSON.stringify({ notes: $("custNote").value }),
    });
    if (j && j.ok !== false) { toast("Đã lưu ghi chú ✓", "success", 2000); state.cust.notes = $("custNote").value; }
    else toast((j && j.error_vi) || "Lưu thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

function editCustAddr() {
  const cur = (state.cust && state.cust.address) || "";
  openModal("📍 Sửa địa chỉ khách",
    `<textarea id="addrEdit" rows="3" style="width:100%">${esc(cur)}</textarea>`,
    `<button class="btn" onclick="closeModal()">Hủy</button>
     <button class="btn btn-primary" id="addrSave">Lưu</button>`);
  $("addrSave").addEventListener("click", async () => {
    const v = $("addrEdit").value.trim();
    if (!state.cust) {
      // Khách mới: tạo hồ sơ luôn để lưu địa chỉ
      try {
        const j = await api("/api/customers", {
          method: "POST",
          body: JSON.stringify({ name: (state.open && state.open.name) || "", phone: state.open.phone || "", address: v }),
        });
        if (j && j.ok !== false) { closeModal(); toast("Đã tạo hồ sơ khách ✓", "success"); loadCustomerPanel(state.open.phone); }
        else toast((j && j.error_vi) || "Lưu thất bại.", "error");
      } catch (e) { toast(e.message, "error"); }
      return;
    }
    try {
      const j = await api(`/api/customers/${state.cust.id}`, { method: "PUT", body: JSON.stringify({ address: v }) });
      if (j && j.ok !== false) { closeModal(); toast("Đã lưu địa chỉ ✓", "success"); state.cust.address = v; renderCustomerPanel(state.open.phone); }
      else toast((j && j.error_vi) || "Lưu thất bại.", "error");
    } catch (e) { toast(e.message, "error"); }
  });
}

/* ---------------- Bộ lọc / tìm kiếm / phím tắt ---------------- */

document.querySelectorAll(".filter-tabs button").forEach((b) => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".filter-tabs button").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    state.filter = b.dataset.f;
    renderConvList();
  });
});
let searchTimer = null;
$("convSearch").addEventListener("input", (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { state.search = e.target.value; renderConvList(); }, 250);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "F3") { e.preventDefault(); $("convSearch").focus(); }
  if (e.key === "F1") { e.preventDefault(); if (state.open) goLendon(); }
});

/* ---------------- Sự kiện composer ---------------- */

$("btnSend").addEventListener("click", sendText);
$("msgInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendText(); });
$("btnImg").addEventListener("click", (e) => { e.stopPropagation(); toggleImgDropdown(); });
document.addEventListener("click", (e) => {
  if (!e.target.closest("#imgDropdown") && !e.target.closest("#btnImg")) $("imgDropdown").classList.add("hidden");
});
$("btnTag").addEventListener("click", openTagModal);
$("btnQuickOrder").addEventListener("click", goLendon);

/* ---------------- Khởi động ---------------- */

(async function init() {
  await loadPages();
  await loadConvs(false);
  setInterval(() => loadConvs(true), POLL_MS);
})();
