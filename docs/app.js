(() => {
  "use strict";

  const PRICE_BANDS = [
    { label: "Any price", test: () => true },
    { label: "₹1000–1250", test: (p) => p <= 1250 },
    { label: "₹1250–1500", test: (p) => p > 1250 && p <= 1500 },
    { label: "₹1500–1750", test: (p) => p > 1500 && p <= 1750 },
    { label: "₹1750–2000", test: (p) => p > 1750 },
  ];
  const PIECES = [
    { label: "Any", test: () => true },
    { label: "Single", test: (n) => n === 1 },
    { label: "Set of 2", test: (n) => n === 2 },
    { label: "Set of 3", test: (n) => n === 3 },
  ];
  const SIZES = ["M", "L", "XL", "XXL", "3XL"];
  const SIZE_RE = {
    M: /(^|[^X\d])M\b|\bmedium\b|\b38\b/i,
    L: /(^|[^X])L\b|\blarge\b|\b40\b/i,
    XL: /(^|[^X\d])XL\b|\b42\b/i,
    XXL: /\bXXL\b|\b2XL\b|\b44\b/i,
    "3XL": /\bXXXL\b|\b3XL\b|\b46\b/i,
  };
  const FABRICS = ["Georgette", "Cotton", "Rayon", "Silk", "Organza", "Chiffon", "Crepe", "Muslin",
    "Velvet", "Lawn", "Linen", "Satin", "Viscose", "Chinon", "Net", "Faux"];
  const FAV_KEY = "suitpicker:favs";

  const $ = (sel, root = document) => root.querySelector(sel);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const rupees = (n) => (n == null ? "" : "₹" + Number(n).toLocaleString("en-IN"));

  let suits = [];
  let byId = new Map();
  const state = { q: "", price: 0, pieces: 0, size: "", fabric: "", site: "", favsOnly: false, sort: "price-asc" };
  let favs = loadFavs();

  function loadFavs() {
    try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]")); } catch { return new Set(); }
  }
  function saveFavs() {
    try { localStorage.setItem(FAV_KEY, JSON.stringify([...favs])); } catch { /* private mode */ }
    $("#fav-count").textContent = favs.size;
  }
  function toggleFav(id) {
    favs.has(id) ? favs.delete(id) : favs.add(id);
    saveFavs();
    document.querySelectorAll(`.heart[data-id="${CSS.escape(id)}"]`).forEach((b) => {
      b.setAttribute("aria-pressed", favs.has(id));
      b.setAttribute("aria-label", favs.has(id) ? "Remove from my picks" : "Add to my picks");
    });
    if (state.favsOnly) render();
  }

  // ---------- data ----------
  function enrich(s) {
    const hay = [s.title, s.fabric, s.sizes, s.work, s.description, s.siteName,
      ...s.specs.map((r) => r.join(" ")), ...s.colors.map((c) => c.name)].join(" ");
    s._hay = hay.toLowerCase();
    const fabricText = [s.fabric, s.title, ...s.specs.filter(([k]) => /fabric|top|bottom|dupatta/i.test(k)).map(([, v]) => v)].join(" ");
    s._fabrics = FABRICS.filter((f) => new RegExp(`\\b${f}`, "i").test(fabricText));
    s._sizes = SIZES.filter((z) => SIZE_RE[z].test(s.sizes || ""));
    return s;
  }

  async function load() {
    try {
      const res = await fetch("data/suits.json", { cache: "no-cache" });
      const data = await res.json();
      suits = data.suits.map(enrich);
      byId = new Map(suits.map((s) => [s.id, s]));
      $("#foot-note").innerHTML =
        `Prices and stock were checked on <b>${esc(new Date(data.generatedAt).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" }))}</b>. ` +
        `They can change — always confirm on the seller's page. Photos belong to the sellers and load from their websites.`;
      buildFilters();
      render();
      route();
    } catch (e) {
      $("#status").textContent = "Couldn't load the suits. Please refresh the page.";
      console.error(e);
    }
  }

  // ---------- filters ----------
  function chipRow(label, items, key) {
    const row = document.createElement("div");
    row.className = "chip-row";
    row.innerHTML = `<span class="label">${esc(label)}</span>` + items.map(([value, text]) =>
      `<button class="pill" data-key="${key}" data-value="${esc(value)}" aria-pressed="${state[key] === value}">${esc(text)}</button>`).join("");
    return row;
  }

  function buildFilters() {
    const box = $("#filters");
    box.innerHTML = "";
    box.append(chipRow("Price", PRICE_BANDS.map((b, i) => [i, b.label]), "price"));
    box.append(chipRow("Pieces", PIECES.map((b, i) => [i, b.label]), "pieces"));
    const fabricCounts = FABRICS.map((f) => [f, suits.filter((s) => s._fabrics.includes(f)).length])
      .filter(([, n]) => n >= 3).sort((a, b) => b[1] - a[1]);
    const sites = [...new Set(suits.map((s) => s.siteName))].sort();
    const extras = [
      chipRow("Size", [["", "Any"], ...SIZES.map((z) => [z, z])], "size"),
      chipRow("Fabric", [["", "Any"], ...fabricCounts.map(([f]) => [f, f])], "fabric"),
      chipRow("Website", [["", "All"], ...sites.map((n) => [n, n])], "site"),
    ];
    extras.forEach((row) => { row.classList.add("extra"); box.append(row); });
    const more = Object.assign(document.createElement("button"), { className: "more-btn", type: "button" });
    box.append(more);
    updateMoreButton();

    box.addEventListener("click", (e) => {
      if (e.target.closest(".more-btn")) {
        box.classList.toggle("open");
        updateMoreButton();
        return;
      }
      const btn = e.target.closest(".pill[data-key]");
      if (!btn) return;
      const key = btn.dataset.key;
      const raw = btn.dataset.value;
      state[key] = key === "price" || key === "pieces" ? Number(raw) : raw;
      box.querySelectorAll(`.pill[data-key="${key}"]`).forEach((b) =>
        b.setAttribute("aria-pressed", b === btn));
      updateMoreButton();
      render();
    });
  }

  function updateMoreButton() {
    const open = $("#filters").classList.contains("open");
    const active = ["size", "fabric", "site"].filter((k) => state[k]).length;
    const btn = $(".more-btn");
    btn.textContent = open ? "Fewer filters ▴" : `More filters (size, fabric, website)${active ? ` · ${active} on` : ""} ▾`;
    btn.setAttribute("aria-expanded", open);
  }

  function matches(s) {
    if (state.favsOnly && !favs.has(s.id)) return false;
    if (!PRICE_BANDS[state.price].test(s.pricePerPiece)) return false;
    if (!PIECES[state.pieces].test(s.pieces)) return false;
    if (state.size && !s._sizes.includes(state.size)) return false;
    if (state.fabric && !s._fabrics.includes(state.fabric)) return false;
    if (state.site && s.siteName !== state.site) return false;
    if (state.q) {
      return state.q.toLowerCase().split(/\s+/).filter(Boolean).every((w) => s._hay.includes(w));
    }
    return true;
  }

  function sorted(list) {
    const out = [...list];
    if (state.sort === "price-asc") out.sort((a, b) => a.pricePerPiece - b.pricePerPiece);
    if (state.sort === "price-desc") out.sort((a, b) => b.pricePerPiece - a.pricePerPiece);
    if (state.sort === "photos") out.sort((a, b) => b.images.length - a.images.length);
    if (state.sort === "mix") {
      const bySite = {};
      out.forEach((s) => (bySite[s.site] ||= []).push(s));
      const queues = Object.values(bySite);
      out.length = 0;
      while (queues.some((q) => q.length)) queues.forEach((q) => q.length && out.push(q.shift()));
    }
    return out;
  }

  // ---------- grid ----------
  function imgTag(src, alt, cls = "") {
    return `<img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" decoding="async" referrerpolicy="no-referrer"${cls ? ` class="${cls}"` : ""}>`;
  }

  function cardHTML(s) {
    const extra = s.images.length - 1 - 4;
    const thumbs = s.images.slice(1, 5).map((u) => imgTag(u, "")).join("") + (extra > 0 ? `<span>+${extra}</span>` : "");
    const setText = s.pieces === 1 ? "Single piece" : `Set of ${s.pieces}`;
    const dots = s.colors.length ? `<div class="dots">${s.colors.slice(0, 6).map((c) =>
      `<i class="dot" style="background:${esc(c.css)}" title="${esc(c.name)}"></i>`).join("")}</div>` : "";
    const metaBits = [s._fabrics.slice(0, 2).join(", ") || s.fabric, s.sizes].filter(Boolean);
    return `<article class="card">
      <button class="heart" data-id="${esc(s.id)}" aria-pressed="${favs.has(s.id)}" aria-label="${favs.has(s.id) ? "Remove from my picks" : "Add to my picks"}">♥</button>
      <button class="card-open" data-open="${esc(s.id)}" aria-label="${esc(s.title)}">
        <div class="card-img">
          ${imgTag(s.images[0], s.title, "main")}
          <span class="badge">${setText}</span>
          <span class="photos">${s.images.length} photos</span>
        </div>
        <div class="card-body">
          <div class="price">${rupees(s.pricePerPiece)} <small>/ piece</small></div>
          <div class="gst">${esc(s.gstNote || "")}${s.pieces > 1 ? `${s.gstNote ? " · " : ""}set ${rupees(s.setPrice)}` : ""}</div>
          <div class="title">${esc(s.title)}</div>
          <div class="meta">${esc(metaBits.join(" · "))}</div>
          ${dots}
          <div class="thumbs" aria-hidden="true">${thumbs}</div>
          <div class="site">${esc(s.siteName)}</div>
        </div>
      </button>
    </article>`;
  }

  function render() {
    const list = sorted(suits.filter(matches));
    $("#grid").innerHTML = list.map(cardHTML).join("");
    $("#status").textContent = `${list.length} of ${suits.length} suits`;
    $("#empty").hidden = list.length > 0;
    $("#fav-count").textContent = favs.size;
  }

  // a dead photo falls back to the next one on cards, and is hidden elsewhere
  document.addEventListener("error", (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    if (img.classList.contains("main")) {
      const card = img.closest(".card");
      const s = byId.get(card?.querySelector("[data-open]")?.dataset.open);
      const tried = Number(img.dataset.tried || 0) + 1;
      img.dataset.tried = tried;
      if (s && tried < s.images.length) { img.src = s.images[tried]; return; }
      img.replaceWith(Object.assign(document.createElement("div"), { className: "noimg", textContent: "Photo unavailable" }));
    } else if (img.closest(".slide")) {
      img.replaceWith(Object.assign(document.createElement("div"), { className: "noimg", textContent: "Photo unavailable" }));
    } else {
      img.remove();
    }
  }, true);

  // ---------- detail ----------
  const WA_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.9 11.9 0 0 0 4.6 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.1-1.2l-.5-.2Z"/></svg>';

  function detailHTML(s) {
    const n = s.images.length;
    const slides = s.images.map((u, i) => {
      const note = s.imageAlts?.[i] && s.site === "textilezone" ? ` · ${s.imageAlts[i]}` : "";
      return `<div class="slide"><span class="cap">Photo ${i + 1} of ${n}${esc(note)}</span>${imgTag(u, `${s.title} — photo ${i + 1}`)}</div>`;
    }).join("");
    const strip = s.images.map((u, i) =>
      `<button data-go="${i}" aria-label="Show photo ${i + 1}" aria-current="${i === 0}">${imgTag(u, "")}</button>`).join("");
    const setText = s.pieces === 1 ? "Sold as a single piece" : `Sold as a set of ${s.pieces} pieces (one of each design)`;
    const checked = s.scrapedAt
      ? ` <span class="checked">(checked ${esc(new Date(s.scrapedAt).toLocaleDateString("en-IN", { day: "numeric", month: "short" }))})</span>` : "";
    const stock = s.stockReliable
      ? `<div class="stock ok">● In stock when last checked${checked}</div>`
      : `<div class="stock check">● Check availability on the seller's page${checked}</div>`;
    const colours = s.colors.length
      ? `<div><h3 class="section-h">Colours mentioned by seller</h3><div class="colours">${s.colors.map((c) =>
        `<span class="colour"><i style="background:${esc(c.css)}"></i>${esc(c.name)}</span>`).join("")}</div></div>` : "";
    const specs = s.specs.length
      ? `<div><h3 class="section-h">Details</h3><table class="specs"><tbody>${s.specs.map(([k, v]) =>
        `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`).join("")}</tbody></table></div>` : "";
    const desc = s.description ? `<div><h3 class="section-h">Description from seller</h3><p class="desc">${esc(s.description)}</p></div>` : "";
    const also = s.alsoOn?.length
      ? `<div class="also"><h3 class="section-h">Also sold on</h3><ul>${s.alsoOn.map((a) =>
        `<li><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.siteName)}</a> — ${rupees(a.pricePerPiece)} / piece ${esc(a.gstNote || "")}</li>`).join("")}</ul></div>` : "";
    const waText = encodeURIComponent(`I like this suit: ${s.title} — ${rupees(s.pricePerPiece)} per piece (${s.pieces === 1 ? "single" : "set of " + s.pieces}). ${s.url}`);

    return `<div class="d-bar">
        <button class="back" data-close>← Back</button>
        <button class="heart" data-id="${esc(s.id)}" aria-pressed="${favs.has(s.id)}" aria-label="${favs.has(s.id) ? "Remove from my picks" : "Add to my picks"}">♥</button>
      </div>
      <div class="d-wrap">
        <div class="gallery">
          <div class="slides" tabindex="0" aria-label="Photos">${slides}</div>
          ${n > 1 ? `<button class="nav-btn prev" data-step="-1" aria-label="Previous photo">‹</button><button class="nav-btn next" data-step="1" aria-label="Next photo">›</button>` : ""}
          ${n > 1 ? `<div class="strip">${strip}</div>` : ""}
        </div>
        <div class="info">
          <div>
            <div class="d-site">${esc(s.siteName)}</div>
            <h2 id="d-title">${esc(s.title)}</h2>
          </div>
          <div class="price-box">
            <div class="big">${rupees(s.pricePerPiece)} <small>per piece ${esc(s.gstNote || "")}</small></div>
            <div class="row">${setText}${s.pieces > 1 ? ` — full set <b>${rupees(s.setPrice)}</b>` : ""}</div>
            ${s.sizes ? `<div class="row">Sizes: <b>${esc(s.sizes)}</b></div>` : ""}
            ${stock}
          </div>
          ${colours}
          ${specs}
          ${desc}
          ${also}
          <div class="actions">
            <a class="btn primary" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">View on ${esc(s.siteName)} ↗</a>
            <a class="btn wa" href="https://wa.me/?text=${waText}" target="_blank" rel="noopener noreferrer" aria-label="Send on WhatsApp">${WA_ICON}<span>Send</span></a>
          </div>
        </div>
      </div>`;
  }

  let openedFromList = false;

  function openDetail(id) {
    const s = byId.get(id);
    const box = $("#detail");
    if (!s) { closeDetailView(); return; }
    box.innerHTML = detailHTML(s);
    box.hidden = false;
    box.scrollTop = 0;
    document.body.classList.add("locked");
    document.title = `${s.title} · Suit Picker`;
    const slides = $(".slides", box);
    slides.addEventListener("scroll", () => {
      const i = Math.round(slides.scrollLeft / slides.clientWidth);
      box.querySelectorAll(".strip button").forEach((b, j) => b.setAttribute("aria-current", j === i));
    }, { passive: true });
    $(".back", box).focus({ preventScroll: true });
  }

  function closeDetailView() {
    const box = $("#detail");
    box.hidden = true;
    box.innerHTML = "";
    document.body.classList.remove("locked");
    document.title = "Suit Picker";
  }

  function route() {
    const m = location.hash.match(/^#suit\/(.+)$/);
    if (m) openDetail(decodeURIComponent(m[1]));
    else closeDetailView();
  }

  function closeDetail() {
    if (openedFromList) { openedFromList = false; history.back(); }
    else { history.replaceState(null, "", location.pathname + location.search); route(); }
  }

  // ---------- events ----------
  document.addEventListener("click", (e) => {
    const heart = e.target.closest(".heart[data-id]");
    if (heart) { e.preventDefault(); toggleFav(heart.dataset.id); return; }
    const open = e.target.closest("[data-open]");
    if (open) { openedFromList = true; location.hash = "suit/" + encodeURIComponent(open.dataset.open); return; }
    if (e.target.closest("[data-close]")) { closeDetail(); return; }
    const go = e.target.closest("[data-go]");
    const step = e.target.closest("[data-step]");
    if (go || step) {
      const slides = $("#detail .slides");
      const cur = Math.round(slides.scrollLeft / slides.clientWidth);
      const target = go ? Number(go.dataset.go) : cur + Number(step.dataset.step);
      slides.scrollTo({ left: Math.max(0, target) * slides.clientWidth, behavior: "smooth" });
    }
  });
  document.addEventListener("keydown", (e) => {
    if ($("#detail").hidden) return;
    if (e.key === "Escape") closeDetail();
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      $(`#detail [data-step="${e.key === "ArrowRight" ? 1 : -1}"]`)?.click();
    }
  });
  window.addEventListener("hashchange", route);

  let qTimer;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => { state.q = e.target.value.trim(); render(); }, 150);
  });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });
  $("#favs-toggle").addEventListener("click", (e) => {
    state.favsOnly = !state.favsOnly;
    e.currentTarget.setAttribute("aria-pressed", state.favsOnly);
    render();
  });
  $("#reset").addEventListener("click", () => {
    Object.assign(state, { q: "", price: 0, pieces: 0, size: "", fabric: "", site: "", favsOnly: false });
    $("#q").value = "";
    $("#favs-toggle").setAttribute("aria-pressed", "false");
    document.querySelectorAll("#filters .pill").forEach((b) =>
      b.setAttribute("aria-pressed", String(state[b.dataset.key]) === b.dataset.value));
    updateMoreButton();
    render();
  });

  load();
})();
