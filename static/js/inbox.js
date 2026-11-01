/* ShopDesk — Inbox gộp 2 page.
 * Poll danh sách hội thoại mỗi 5s (background); thread đang mở poll tin nhắn mỗi 5s. */
"use strict";

const POLL_MS = 5000;

const state = {
  pages: [],          // [{page_id, name, status, status_msg}]
  convs: [],          // [{id, name, snippet, updated_time, unread, needs_reply, page_id, page_name}]
  open: null,         // {page_id, page_name, conv_id, name, psid}
  lastMsgId: null,
  assets: null,       // {hana:[...], bedan:[...]}
  tags: {},           // "page_id/thread_id" -> [{tag, label, color, source}]
  listLoading: false,
  msgLoading: false,
  msgTimer: null,
};

const $ = (id) => document.getElementById(id);

/* ---------------- Load hội thoại ---------------- */

async function loadConvs(background = false) {
  if (state.listLoading) return;
  state.listLoading = true;
  if (!background) {
    $("convList").innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải hội thoại…</div>`;
  }
  try {
    const pj = await api("/api/pages");
    state.pages = pj.pages || [];
    renderPageStatus();

    const all = [];
    for (const pg of state.pages) {
      try {
        const cj = await api(`/api/pages/${encodeURIComponent(pg.page_id)}/conversations?limit=25`);
        for (const c of (cj.conversations || [])) {
          all.push({ ...c, page_id: pg.page_id, page_name: pg.name });
        }
      } catch (e) {
        // Lỗi 1 page không chặn các page còn lại
        console.warn("load convs", pg.page_id, e);
      }
    }
    all.sort((a, b) => String(b.updated_time || "").localeCompare(String(a.updated_time || "")));
    state.convs = all;
    // Tag hội thoại (cache trong state, refresh mỗi lần loadConvs). API chưa có -> bỏ qua, vẫn hiển thị bình thường.
    const tagMap = {};
    const tagResults = await Promise.all(state.pages.map((pg) =>
      api(`/api/inbox/tags/by-page/${encodeURIComponent(pg.page_id)}`)
        .then((tj) => ({ pg, threads: (tj && tj.threads) || {} }))
        .catch(() => ({ pg, threads: {} }))));
    for (const { pg, threads } of tagResults) {
      for (const [tid, tags] of Object.entries(threads)) {
        tagMap[pg.page_id + "/" + tid] = tags || [];
      }
    }
    state.tags = tagMap;
    renderConvList();
  } catch (e) {
    if (!background || state.convs.length === 0) {
      $("convList").innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}<br>
        <button class="btn btn-sm" style="margin-top:8px" onclick="loadConvs(false)">Thử lại</button></div>`;
    }
  } finally {
    state.listLoading = false;
  }
}

function renderPageStatus() {
  const el = $("pageStatus");
  if (!state.pages.length) { el.innerHTML = "Chưa cấu hình page nào. Vào Cài đặt để thêm."; return; }
  el.innerHTML = state.pages.map((p) => {
    const ok = p.status === "ok";
    return `<div>${ok ? "🟢" : "🔴"} <b>${esc(p.name)}</b>${ok ? "" : ` <span class="err">— ${esc(p.status_msg || "lỗi kết nối")}</span>`}</div>`;
  }).join("");
}

/** Hội thoại hiển thị sau khi áp bộ lọc tag + trạng thái trả lời (client-side). */
function visibleConvs() {
  const tag = $("tagFilter") ? $("tagFilter").value : "";
  const reply = $("replyFilter") ? $("replyFilter").value : "";
  return state.convs.filter((c) => {
    if (tag) {
      const tags = state.tags[c.page_id + "/" + c.id] || [];
      if (!tags.some((t) => t.tag === tag)) return false;
    }
    if (reply === "unreplied" && !c.needs_reply) return false;
    if (reply === "replied" && c.needs_reply) return false;
    return true;
  });
}

function renderConvList() {
  const list = $("convList");
  const visible = visibleConvs();
  $("convCount").textContent = visible.length === state.convs.length
    ? state.convs.length : `${visible.length}/${state.convs.length}`;
  if (!visible.length) {
    list.innerHTML = state.convs.length
      ? `<div class="state-empty">🔎 Không có hội thoại nào khớp bộ lọc.</div>`
      : `<div class="state-empty">📭 Chưa có hội thoại nào.<br>Kiểm tra page đã kết nối ở mục Cài đặt.</div>`;
    return;
  }
  const scrollTop = list.scrollTop;
  list.innerHTML = visible.map((c) => {
    const active = state.open && state.open.conv_id === c.id && state.open.page_id === c.page_id;
    const initial = (c.name || "?").trim().charAt(0).toUpperCase() || "?";
    const tags = state.tags[c.page_id + "/" + c.id] || [];
    const unread = c.needs_reply ? "unreplied" : "";
    return `
    <div class="conv-item ${active ? "active" : ""}" data-page="${esc(c.page_id)}" data-conv="${esc(c.id)}"${c.needs_reply ? ' title="Chưa trả lời"' : ""}>
      <div class="conv-avatar">${esc(initial)}</div>
      <div class="conv-main">
        <div class="conv-top">
          <span class="conv-name ${unread}">${esc(c.name || "(không tên)")}</span>
          <span class="conv-time">${esc(fmtRel(c.updated_time))}</span>
        </div>
        <div class="conv-snippet ${unread}">${esc(c.snippet || "")}</div>
        <div class="conv-meta">
          ${shopBadge(c.page_name)}
          ${tags.map((t) => tagBadgeHTML(t)).join("")}
          ${c.unread ? `<span class="unread-dot" title="Có tin chưa đọc"></span>` : ""}
        </div>
      </div>
    </div>`;
  }).join("");
  list.scrollTop = scrollTop;
  list.querySelectorAll(".conv-item").forEach((el) => {
    el.addEventListener("click", () => {
      openThread(el.dataset.page, el.dataset.conv);
    });
  });
}

/* ---------------- Mở thread + poll tin nhắn ---------------- */

async function openThread(page_id, conv_id) {
  const c = state.convs.find((x) => x.page_id === page_id && x.id === conv_id);
  const page = state.pages.find((p) => p.page_id === page_id);
  state.open = {
    page_id, conv_id,
    name: c ? c.name : "",
    page_name: page ? page.name : (c ? c.page_name : ""),
    psid: null,
  };
  state.lastMsgId = null;
  if (state.msgTimer) { clearInterval(state.msgTimer); state.msgTimer = null; }

  $("chatHeader").innerHTML = `
    <div class="chat-top-row">
      <div class="conv-avatar">${esc((state.open.name || "?").charAt(0).toUpperCase())}</div>
      <div><div class="who">${esc(state.open.name || "(không tên)")}</div>
      <div class="sub">${shopBadge(state.open.page_name)} · ${esc(fmtTime(c && c.updated_time))}</div></div>
      <div class="actions"><button id="btnOrderTop" class="btn btn-sm">🧾 Tạo đơn</button></div>
    </div>
    <div class="tag-bar" id="tagBar">
      <span class="spinner"></span><span style="font-size:12px;color:var(--muted)">Đang tải tag…</span>
    </div>`;
  $("btnOrderTop").addEventListener("click", openOrderModal);
  $("chatMessages").innerHTML = `<div class="state-loading"><span class="spinner"></span>Đang tải tin nhắn…</div>`;

  setComposerEnabled(false);
  renderConvList();
  refreshThreadTags();
  await loadMessages();
  state.msgTimer = setInterval(() => loadMessages(true), POLL_MS);
}

function setComposerEnabled(on) {
  $("msgInput").disabled = !on;
  $("btnSend").disabled = !on;
  $("btnImg").disabled = !on;
  $("btnOrder").disabled = !on;
  if (on) $("msgInput").placeholder = "Nhập tin nhắn…";
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
    }
    const lastId = msgs.length ? msgs[msgs.length - 1].id : null;
    const changed = lastId !== state.lastMsgId;
    state.lastMsgId = lastId;
    if (changed || !background) {
      renderMessages(msgs);
      setComposerEnabled(true);
    }
  } catch (e) {
    if (!background) {
      $("chatMessages").innerHTML = `<div class="state-error">⚠️ ${esc(e.message)}</div>`;
    }
  } finally {
    state.msgLoading = false;
  }
}

function renderMessages(msgs) {
  const box = $("chatMessages");
  if (!msgs.length) { box.innerHTML = `<div class="state-empty">Chưa có tin nhắn nào.</div>`; return; }
  const nearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 90;
  box.innerHTML = msgs.map((m) => {
    const cls = m.mine ? "me" : "them";
    const atts = (m.attachments || []).map((a) => {
      if (a.type === "image" && a.url) {
        return `<a href="${esc(a.url)}" target="_blank" rel="noopener"><img class="att" src="${esc(a.url)}" alt="Ảnh đính kèm" loading="lazy"></a>`;
      }
      return `<div class="att-file">📎 Tệp đính kèm</div>`;
    }).join("");
    return `
    <div class="msg ${cls}">
      ${m.mine ? "" : `<div class="who">${esc(m.from_name || state.open.name || "")}</div>`}
      <div class="bubble">${esc(m.text || "")}${atts}</div>
      <div class="time">${esc(fmtTime(m.created_time))}</div>
    </div>`;
  }).join("");
  if (nearBottom || state.lastMsgId === null) box.scrollTop = box.scrollHeight;
}

/* ---------------- Gửi tin nhắn ---------------- */

async function sendText() {
  const input = $("msgInput");
  const text = input.value.trim();
  if (!text || !state.open) return;
  if (!state.open.psid) {
    toast("Chưa xác định được người nhận (thread chưa có tin nhắn từ khách).", "warning");
    return;
  }
  $("btnSend").disabled = true;
  try {
    const j = await api(`/api/pages/${encodeURIComponent(state.open.page_id)}/send`, {
      method: "POST",
      body: JSON.stringify({ psid: state.open.psid, text }),
    });
    if (j.ok) {
      input.value = "";
      toast("Đã gửi ✓", "success", 1800);
      await loadMessages();
    } else {
      toast(j.error_vi || "Gửi tin nhắn thất bại.", "error", 7000);
    }
  } catch (e) {
    toast(e.message, "error", 7000);
  } finally {
    $("btnSend").disabled = false;
    input.focus();
  }
}

/* ---------------- Ảnh nhanh ---------------- */

async function ensureAssets() {
  if (state.assets) return state.assets;
  state.assets = await api("/api/assets");
  return state.assets;
}

$("btnImg").addEventListener("click", async (e) => {
  e.stopPropagation();
  const dd = $("imgDropdown");
  if (!dd.classList.contains("hidden")) { dd.classList.add("hidden"); return; }
  if (!state.open) return;
  const shop = shopKeyFromPageName(state.open.page_name) || "hana";
  try {
    const assets = await ensureAssets();
    const files = assets[shop] || [];
    if (!files.length) {
      dd.innerHTML = `<div class="state-empty">Không có ảnh nào cho shop này.</div>`;
    } else {
      dd.innerHTML = files.map((f) => `
        <div class="img-opt" data-file="${esc(f)}">
          <img src="/static/${esc(f)}" alt="" loading="lazy">
          <span class="fname">${esc(f)}</span>
        </div>`).join("");
      dd.querySelectorAll(".img-opt").forEach((el) => {
        el.addEventListener("click", () => sendImage(el.dataset.file));
      });
    }
  } catch (err) {
    dd.innerHTML = `<div class="state-error">⚠️ ${esc(err.message)}</div>`;
  }
  dd.classList.remove("hidden");
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".img-dropdown-wrap")) $("imgDropdown").classList.add("hidden");
});

async function sendImage(file) {
  $("imgDropdown").classList.add("hidden");
  if (!state.open || !state.open.psid) {
    toast("Chưa xác định được người nhận.", "warning");
    return;
  }
  toast("Đang gửi ảnh…", "info", 2500);
  try {
    const j = await api(`/api/pages/${encodeURIComponent(state.open.page_id)}/send_image`, {
      method: "POST",
      body: JSON.stringify({ psid: state.open.psid, image: file }),
    });
    if (j.ok) { toast("Đã gửi ảnh ✓", "success", 2000); await loadMessages(); }
    else toast(j.error_vi || "Gửi ảnh thất bại.", "error", 7000);
  } catch (e) {
    toast(e.message, "error", 7000);
  }
}

/* ---------------- Tag hội thoại ---------------- */

async function refreshThreadTags() {
  if (!state.open) return;
  const { page_id, conv_id } = state.open;
  const bar = $("tagBar");
  try {
    const j = await api(`/api/inbox/${encodeURIComponent(page_id)}/${encodeURIComponent(conv_id)}/tags`);
    const tags = (j && j.tags) || [];
    state.tags[page_id + "/" + conv_id] = tags;
    renderTagBar(tags);
    renderConvList(); // đồng bộ badge trong danh sách
  } catch (e) {
    if (bar) {
      bar.innerHTML = `<span style="font-size:12px;color:var(--muted)">Không tải được tag (${esc(e.message)})</span>`;
    }
  }
}

function renderTagBar(tags) {
  const bar = $("tagBar");
  if (!bar) return;
  const current = new Set(tags.map((t) => t.tag));
  const opts = TAG_ORDER.filter((t) => !current.has(t))
    .map((t) => `<option value="${t}">${esc(TAG_LABEL[t])}</option>`).join("");
  bar.innerHTML = `
    <span class="tag-bar-label" title="Tag hội thoại">🏷️</span>
    ${tags.map((t) => tagBadgeHTML(t, true)).join("") || `<span style="font-size:12px;color:var(--muted)">Chưa gắn tag</span>`}
    <select id="tagAdd" class="tag-add" title="Gắn tag cho hội thoại">
      <option value="">+ Gắn tag</option>${opts}
    </select>`;
  bar.querySelectorAll(".tag-x").forEach((b) => {
    b.addEventListener("click", (e) => { e.stopPropagation(); removeThreadTag(b.dataset.tag); });
  });
  bar.querySelector("#tagAdd").addEventListener("change", (e) => {
    if (e.target.value) addThreadTag(e.target.value);
  });
}

async function addThreadTag(tag) {
  if (!state.open) return;
  try {
    const j = await api(`/api/inbox/${encodeURIComponent(state.open.page_id)}/${encodeURIComponent(state.open.conv_id)}/tags`, {
      method: "POST", body: JSON.stringify({ tag }),
    });
    if (j && j.ok) { toast(`Đã gắn tag "${TAG_LABEL[tag] || tag}" ✓`, "success", 2000); refreshThreadTags(); }
    else toast((j && j.error_vi) || "Gắn tag thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

async function removeThreadTag(tag) {
  if (!state.open) return;
  try {
    const j = await api(`/api/inbox/${encodeURIComponent(state.open.page_id)}/${encodeURIComponent(state.open.conv_id)}/tags`, {
      method: "DELETE", body: JSON.stringify({ tag }),
    });
    if (j && j.ok) { toast("Đã gỡ tag ✓", "success", 1800); refreshThreadTags(); }
    else toast((j && j.error_vi) || "Gỡ tag thất bại.", "error");
  } catch (e) { toast(e.message, "error"); }
}

/* ---------------- Modal tạo đơn v2 ---------------- */

/* ---------------- Modal tạo đơn v2 (chọn SKU, lookup khách cũ, tạo vận đơn) ---------------- */

const _custCache = {}; // phone -> customer | null

function normPhone(s) {
  return String(s || "").replace(/\D/g, "").replace(/^84/, "0");
}

/** Blur SĐT -> tra khách cũ, tự điền tên/địa chỉ còn trống + toast. */
async function lookupCustomerByPhone() {
  const phoneEl = $("o_phone");
  if (!phoneEl) return;
  const phone = normPhone(phoneEl.value);
  if (!phone || _custCache[phone] !== undefined) return;
  try {
    const j = await api(`/api/customers/by-phone?phone=${encodeURIComponent(phone)}`);
    const c = (j && j.customer) || null;
    _custCache[phone] = c;
    if (c) {
      if ($("o_name") && !$("o_name").value.trim() && c.name) $("o_name").value = c.name;
      if ($("o_addr") && !$("o_addr").value.trim() && c.address) $("o_addr").value = c.address;
      toast("Đã tìm thấy thông tin khách cũ ✓", "success", 2500);
    }
  } catch (e) {
    /* API chưa sẵn / không có khách: im lặng, không chặn tạo đơn */
  }
}

/** Preview tổng tiền client-side: tổng SKU×SL + ship (server tính lại khi lưu). */
function updateQuickPreview(shop) {
  const pv = $("o_preview");
  if (!pv) return;
  const items = skuPickerItems("o", shop);
  const sub = items.reduce((s, x) => s + x.price * x.qty, 0);
  const qty = items.reduce((s, x) => s + x.qty, 0);
  const fee = shipFeeFor(shop, qty);
  if (!items.length) {
    pv.innerHTML = `<span style="color:var(--muted)">Chưa có dòng hàng nào.</span>`;
    return;
  }
  const lines = items.map((x) => `
    <div class="pv-row"><span>${esc(x.name || x.sku)} × ${x.qty}</span>
    <span>${x.known ? fmtMoney(x.price * x.qty) : '<span class="pv-warn">SKU chưa có trong danh mục</span>'}</span></div>`).join("");
  const feeNote = qty >= 2 ? "(miễn ship từ 2 đôi)" : qty === 1 ? "(phí ship 1 đôi)" : "";
  pv.innerHTML = `
    ${lines}
    <div class="pv-row"><span>Tạm tính</span><span>${fmtMoney(sub)}</span></div>
    <div class="pv-row"><span>Phí ship ${feeNote}</span><span>${fee ? fmtMoney(fee) : "Miễn phí"}</span></div>
    <div class="pv-row pv-total"><span>Tổng dự kiến</span><span>${fmtMoney(sub + fee)}</span></div>
    <div style="font-size:11.5px;color:var(--muted);margin-top:4px">Máy chủ sẽ tính lại tổng tiền chính xác khi lưu đơn.</div>`;
}

function openOrderModal() {
  if (!state.open) return;
  const shop = shopKeyFromPageName(state.open.page_name) || "hana";
  const shopName = SHOP_LABEL[shop] || state.open.page_name;
  const carrierOpts = Object.keys(CARRIER_LABEL).filter((k) => k)
    .map((k) => `<option value="${esc(k)}">${esc(CARRIER_LABEL[k])}</option>`).join("");
  const body = `
    <input type="hidden" id="o_shop" value="${esc(shop)}">
    <label>Tên khách</label>
    <input type="text" id="o_name" value="${esc(state.open.name || "")}">
    <div class="form-row">
      <div><label>Số điện thoại *</label><input type="tel" id="o_phone" placeholder="VD: 0901234567" autocomplete="off"></div>
      <div><label>Shop</label><input type="text" value="${esc(shopName)}" disabled></div>
    </div>
    <label>Địa chỉ *</label>
    <textarea id="o_addr" rows="2" placeholder="Ghi theo địa chỉ cũ trước sáp nhập…"></textarea>
    <label>Sản phẩm (chọn theo SKU) *</label>
    ${skuPickerHTML("o")}
    <label>Ghi chú</label>
    <input type="text" id="o_notes" placeholder="Màu, size…">
    <label>Hãng vận chuyển</label>
    <select id="o_carrier">
      <option value="">Không tạo vận đơn</option>
      ${carrierOpts}
    </select>
    <div id="o_preview" class="order-preview"></div>
  `;
  openModal("🧾 Tạo đơn hàng", body,
    `<button class="btn" onclick="closeModal()">Hủy</button>
     <button class="btn btn-primary" id="o_save">Lưu đơn</button>`);
  const modal = document.querySelector("#modalRoot .modal");
  if (modal) modal.classList.add("wide");

  $("o_phone").addEventListener("blur", lookupCustomerByPhone);
  wireSkuPicker("o", shop, () => updateQuickPreview(shop));

  $("o_save").addEventListener("click", async () => {
    const items = skuPickerItems("o", shop);
    const name = $("o_name").value.trim();
    const phone = normPhone($("o_phone").value);
    const addr = $("o_addr").value.trim();
    const bad = items.find((x) => !x.known);
    if (!phone || !addr) {
      toast("Vui lòng nhập đủ: SĐT, địa chỉ.", "warning");
      return;
    }
    if (!items.length) {
      toast("Vui lòng chọn ít nhất 1 sản phẩm (nhập SKU).", "warning");
      return;
    }
    if (bad) {
      toast(`SKU "${bad.sku}" chưa có trong danh mục sản phẩm.`, "warning");
      return;
    }
    const carrier = $("o_carrier").value;
    const payload = {
      shop,
      customer_name: name,
      phone,
      address: addr,
      items: items.map((x) => ({ sku: x.sku, qty: x.qty })),
      notes: $("o_notes").value.trim(),
      source_thread: `fb:${state.open.page_id}/${state.open.conv_id}`,
      create_shipment: carrier ? { carrier } : null,
    };
    $("o_save").disabled = true;
    try {
      const j = await api("/api/orders/quick", { method: "POST", body: JSON.stringify(payload) });
      if (j && j.ok) {
        closeModal();
        let msg = `Đã tạo đơn #${j.order_id} — ${fmtMoney(j.total)} ✓`;
        if (j.shipping_code) msg += ` · Mã VC: ${j.shipping_code}`;
        toast(msg, "success", 8000);
        if (j.shipment_error_vi) toast("⚠️ " + j.shipment_error_vi, "warning", 8000);
      } else {
        toast((j && j.error_vi) || "Tạo đơn thất bại.", "error");
      }
    } catch (e) { toast(e.message, "error"); }
    finally { const b = $("o_save"); if (b) b.disabled = false; }
  });
}

/* ---------------- Khởi động ---------------- */

/* Dựng option lọc tag từ TAG_LABEL dùng chung; gắn sự kiện lọc client-side. */
(function initFilters() {
  const tf = $("tagFilter");
  tf.innerHTML = `<option value="">🏷️ Tất cả tag</option>` + TAG_ORDER.map((t) =>
    `<option value="${t}">${esc(TAG_LABEL[t])}</option>`).join("");
  tf.addEventListener("change", renderConvList);
  $("replyFilter").addEventListener("change", renderConvList);
})();

$("btnSend").addEventListener("click", sendText);
$("msgInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendText();
});
$("btnOrder").addEventListener("click", openOrderModal);

loadConvs(false);
setInterval(() => loadConvs(true), POLL_MS);
