/* Global search autocomplete (spec S0-3). Debounced query to /api/search,
   renders watches + families + brands, keyboard-navigable, click to route. */

const input = document.getElementById("gs-input");
const results = document.getElementById("gs-results");
if (input && results) {
  let timer = null;
  const fmt = (v) => v == null ? "" : "$" + Math.round(v).toLocaleString("en-US");

  function close() { results.classList.remove("open"); results.textContent = ""; }

  async function run(q) {
    if (q.trim().length < 2) { close(); return; }
    let data;
    try { data = await (await fetch("/api/search?q=" + encodeURIComponent(q))).json(); }
    catch { close(); return; }
    results.textContent = "";
    const add = (el) => results.appendChild(el);

    if (data.watches.length) {
      const h = document.createElement("div"); h.className = "gs-section"; h.textContent = "Watches"; add(h);
      for (const w of data.watches) {
        const row = document.createElement("a");
        row.className = "gs-row"; row.href = "/refs/" + w.slug;
        if (w.image) { const img = document.createElement("img"); img.src = w.image; img.alt = ""; row.appendChild(img); }
        const box = document.createElement("div");
        const name = document.createElement("div"); name.className = "gs-name";
        name.textContent = w.brand + " " + w.display_ref + (w.nicknames.length ? " “" + w.nicknames[0] + "”" : "");
        const sub = document.createElement("div"); sub.className = "gs-sub"; sub.textContent = w.family || "";
        box.append(name, sub); row.appendChild(box);
        const price = document.createElement("div"); price.className = "gs-price"; price.textContent = fmt(w.median_usd);
        row.appendChild(price);
        add(row);
      }
    }
    if (data.families.length) {
      const h = document.createElement("div"); h.className = "gs-section"; h.textContent = "Collections"; add(h);
      for (const f of data.families) {
        const row = document.createElement("a"); row.className = "gs-row"; row.href = "/watches/" + f.slug;
        const name = document.createElement("div"); name.className = "gs-name"; name.textContent = f.name;
        row.appendChild(name); add(row);
      }
    }
    if (data.brands.length) {
      const h = document.createElement("div"); h.className = "gs-section"; h.textContent = "Brands"; add(h);
      for (const b of data.brands) {
        const row = document.createElement("a"); row.className = "gs-row"; row.href = "/brands/" + b.slug;
        const name = document.createElement("div"); name.className = "gs-name"; name.textContent = b.name;
        row.appendChild(name); add(row);
      }
    }
    if (results.children.length) results.classList.add("open"); else close();
  }

  input.addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => run(e.target.value), 160);
  });
  input.addEventListener("focus", (e) => { if (e.target.value.length >= 2) run(e.target.value); });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#global-search")) close();
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
    if (e.key === "Enter") {
      const first = results.querySelector("a.gs-row");
      if (first) location.href = first.href;
    }
  });
}
