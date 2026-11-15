/* First Tech Job: all filtering happens here in the browser, on /api/jobs. */
(() => {
  "use strict";

  const TIME_WINDOWS = [
    { label: "1 day", days: 1 }, { label: "3 days", days: 3 }, { label: "5 days", days: 5 },
    { label: "1 week", days: 7 }, { label: "2 weeks", days: 14 },
  ];
  const TZ = "Asia/Kolkata";
  const DAY = 86400000;
  const EXP_LEVELS = ["Freshers welcome", "Less than 1 year", "1 year asked", "Internship", "Experience not mentioned", "Some experience preferred"];
  const MODES = ["Office", "Hybrid", "Remote"];
  const KINDS = [{ label: "Jobs", value: "job" }, { label: "Internships", value: "internship" }];

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const keyOf = (j) => j.dedupe_key;

  let DATA = null;
  const saved = new Set();
  const applied = new Set();
  const prevVisit = store.get("lastVisit", 0);
  store.set("lastVisit", Date.now());

  // ---------- PIN (asked once, remembered on this device) ----------
  async function getPin(force) {
    let pin = force ? "" : store.get("pin", "");
    if (pin) return pin;
    pin = (window.prompt("Enter your PIN to save, mark applied or refresh") || "").trim();
    if (!pin) return "";
    const r = await fetch("api/pin", { method: "POST", headers: { "x-pin": pin } });
    if (!r.ok) { alert("That PIN didn't work. Try again?"); return ""; }
    store.set("pin", pin);
    return pin;
  }

  async function api(path, body) {
    let pin = await getPin(false);
    if (!pin) return null;
    const send = (p) => fetch(path, { method: "POST", headers: { "x-pin": p, "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
    let r = await send(pin);
    if (r.status === 401) {
      store.set("pin", "");
      pin = await getPin(true);
      if (!pin) return null;
      r = await send(pin);
    }
    const data = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, data };
  }

  const defaults = () => ({ days: 14, kinds: [], roles: [], exps: [], areas: [], modes: [], platforms: [], q: "", sort: "new",
    salary: false, email: false, nocons: false, nobond: false });
  let F = Object.assign(defaults(), store.get("filters", {}));
  let tab = "all";

  // ---------- time ----------
  const ts = (j) => (j.posted_at ? Date.parse(j.posted_at) : NaN);
  const istDay = (t) => {
    const p = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(t);
    return Date.parse(p + "T00:00:00Z");
  };
  const daysAgo = (j) => {
    const t = ts(j);
    if (isNaN(t)) return Infinity;
    if (j.posted_precision === "date") return Math.round((istDay(Date.now()) - t) / DAY);
    return (Date.now() - t) / DAY;
  };
  const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"} ago`;

  function relative(j) {
    const t = ts(j);
    if (isNaN(t)) return "Date unknown";
    if (j.posted_precision === "date") {
      const d = Math.max(0, Math.round((istDay(Date.now()) - t) / DAY));
      return d === 0 ? "Today" : plural(d, "day");
    }
    const mins = Math.max(0, Math.floor((Date.now() - t) / 60000));
    const pre = j.posted_precision === "hour" ? "about " : j.posted_precision === "seen" ? "First seen " : "";
    let s;
    if (mins < 60) s = mins <= 1 ? "just now" : plural(mins, "minute");
    else if (mins < 1440) s = plural(Math.floor(mins / 60), "hour");
    else s = plural(Math.floor(mins / 1440), "day");
    s = pre + s;
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function exact(j) {
    const t = ts(j);
    if (isNaN(t)) return "";
    if (j.posted_precision === "date") {
      return new Intl.DateTimeFormat("en-IN", { timeZone: "UTC", weekday: "short", month: "short", day: "numeric", year: "numeric" }).format(t) + " (time not given)";
    }
    const s = new Intl.DateTimeFormat("en-IN", {
      timeZone: TZ, weekday: "short", month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
    }).format(t);
    if (j.posted_precision === "hour") return s.replace(/:\d\d/, ":00") + " (approx.)";
    if (j.posted_precision === "seen") return s + " (site shows no post date)";
    return s;
  }

  const isNew = (j) => {
    const seen = Date.parse(j.first_seen || "");
    return prevVisit ? seen > prevVisit : daysAgo(j) <= 1;
  };

  // ---------- filtering ----------
  function baseList() {
    if (!DATA) return [];
    if (tab === "hidden") return DATA.hidden;
    let l = DATA.jobs;
    if (tab === "saved") l = l.filter((j) => saved.has(keyOf(j)));
    if (tab === "applied") l = l.filter((j) => applied.has(keyOf(j)));
    if (tab === "new") l = l.filter(isNew);
    return l;
  }

  const platformsOf = (j) => [j.platform, ...(j.also_on || []).map((a) => a.platform)];
  const kindOf = (j) => (j.is_internship ? "internship" : "job");
  const hasBond = (j) => (j.flags || []).some((f) => /bond/i.test(f));
  const viaCons = (j) => (j.flags || []).includes("Via consultancy");

  function passes(j, skip) {
    if (skip !== "days" && daysAgo(j) > F.days) return false;
    if (skip !== "kinds" && F.kinds.length && !F.kinds.includes(kindOf(j))) return false;
    if (skip !== "roles" && F.roles.length && !j.roles.some((r) => F.roles.includes(r))) return false;
    if (skip !== "exps" && F.exps.length && !F.exps.includes(j.experience)) return false;
    if (skip !== "areas" && F.areas.length && !(j.areas || []).some((a) => F.areas.includes(a))) return false;
    if (skip !== "modes" && F.modes.length && !F.modes.includes(j.work_mode || "")) return false;
    if (skip !== "platforms" && F.platforms.length && !platformsOf(j).some((p) => F.platforms.includes(p))) return false;
    if (F.salary && !j.salary) return false;
    if (F.email && !(j.emails || []).length) return false;
    if (F.nocons && viaCons(j)) return false;
    if (F.nobond && hasBond(j)) return false;
    if (F.q) {
      if (j._hay === undefined) {
        j._hay = `${j.title} ${j.company} ${j.location} ${(j.areas || []).join(" ")} ${(j.skills || []).join(" ")} ${j.description}`.toLowerCase();
      }
      if (!F.q.toLowerCase().split(/\s+/).every((w) => j._hay.includes(w))) return false;
    }
    return true;
  }

  function filtered() {
    const l = baseList().filter((j) => passes(j));
    const by = {
      new: (a, b) => (ts(b) || 0) - (ts(a) || 0),
      old: (a, b) => (ts(a) || 0) - (ts(b) || 0),
      salary: (a, b) => (!!b.salary - !!a.salary) || (ts(b) || 0) - (ts(a) || 0),
    }[F.sort];
    return l.sort(by);
  }

  // ---------- chips ----------
  function chipGroup(el, items, active, onPick) {
    el.innerHTML = items.map((it) =>
      `<button type="button" class="chip${active(it.value) ? " on" : ""}" data-v="${esc(it.value)}">${esc(it.label)}${it.count != null ? ` <small>${it.count}</small>` : ""}</button>`
    ).join("");
    el.onclick = (e) => {
      const b = e.target.closest(".chip");
      if (b) onPick(b.dataset.v);
    };
  }

  const toggleIn = (arr, v) => (arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  function facet(dim, valuesOf) {
    const counts = {};
    for (const j of baseList()) if (passes(j, dim)) for (const v of new Set(valuesOf(j))) counts[v] = (counts[v] || 0) + 1;
    return counts;
  }

  function multi(sel, dim, items, valuesOf) {
    const c = facet(dim, valuesOf);
    chipGroup($(sel), items.map((it) => ({ ...it, count: c[it.value] || 0 })),
      (v) => F[dim].includes(v), (v) => { F[dim] = toggleIn(F[dim], v); update(); });
  }

  function renderFilters() {
    const tc = (d) => baseList().filter((j) => passes(j, "days") && daysAgo(j) <= d).length;
    chipGroup($("#f-time"), TIME_WINDOWS.map((w) => ({ label: w.label, value: String(w.days), count: tc(w.days) })),
      (v) => +v === F.days, (v) => { F.days = +v; update(); });

    multi("#f-kind", "kinds", KINDS, (j) => [kindOf(j)]);
    multi("#f-role", "roles", DATA.roles.map((r) => ({ label: r, value: r })), (j) => j.roles);
    const ec = facet("exps", (j) => [j.experience]);
    multi("#f-exp", "exps", EXP_LEVELS.filter((x) => ec[x] || F.exps.includes(x)).map((x) => ({ label: x, value: x })), (j) => [j.experience]);
    multi("#f-area", "areas", DATA.areas.map((a) => ({ label: a, value: a })), (j) => j.areas || []);
    multi("#f-mode", "modes", MODES.map((m) => ({ label: m, value: m })), (j) => [j.work_mode || ""]);
    multi("#f-platform", "platforms", Object.keys(DATA.sources).map((p) => ({ label: p, value: p })), platformsOf);

    const active = F.kinds.length + F.roles.length + F.exps.length + F.areas.length + F.modes.length + F.platforms.length +
      (F.q ? 1 : 0) + F.salary + F.email + F.nocons + F.nobond;
    $("#f-toggle").innerHTML = active ? `More filters <b>(${active} active)</b>` : "More filters";

    $("#f-q").value = F.q;
    $("#f-sort").value = F.sort;
    for (const k of ["salary", "email", "nocons", "nobond"]) $(`#f-${k}`).checked = F[k];
  }

  // ---------- cards ----------
  function card(j) {
    const k = keyOf(j);
    const links = [{ platform: j.platform, url: j.url }, ...(j.also_on || [])]
      .map((l) => `<a class="btn primary" href="${esc(l.url)}" target="_blank" rel="noopener">Open on ${esc(l.platform)} ↗</a>`).join("");
    const contact = [
      j.address ? `<div><span>Address:</span> ${esc(j.address)}</div>` : "",
      (j.emails || []).length ? `<div><span>Email:</span> ${j.emails.map((e) => `<a href="mailto:${esc(e)}">${esc(e)}</a>`).join(", ")}</div>` : "",
      (j.phones || []).length ? `<div><span>Phone:</span> ${j.phones.map((p) => `<a href="tel:${esc(p.replace(/[^\d+]/g, ""))}">${esc(p)}</a>`).join(", ")}</div>` : "",
    ].join("");
    const hiddenWhy = tab === "hidden" ? `<span class="badge why">${esc(j.hidden_reason)}</span>` : "";
    const exp = j.experience ? `${j.experience}${j.exp_range ? ` · ${j.exp_range}` : ""}` : "";
    const good = /^(Freshers|Less than|Internship)/.test(j.experience || "");
    return `<article class="card${applied.has(k) ? " applied" : ""}" data-k="${esc(k)}">
      <div class="top"><h3>${esc(j.title)}</h3>${isNew(j) && tab !== "hidden" ? '<span class="badge new">NEW</span>' : ""}${hiddenWhy}</div>
      <p class="co">${esc(j.company || "Company not shown")}</p>
      <p class="loc">📍 ${esc(j.location || (j.areas || []).join(", ") || "Location not shown")}${j.work_mode ? ` · ${esc(j.work_mode)}` : ""}</p>
      <p class="when"><b>${esc(relative(j))}</b> · ${esc(exact(j))}</p>
      ${j.salary ? `<p class="sal">${esc(j.salary)}</p>` : ""}
      <div class="tags">
        ${exp ? `<span class="tag exp${good ? " good" : ""}">${esc(exp)}</span>` : ""}
        ${j.roles.map((r) => `<span class="tag">${esc(r)}</span>`).join("")}
        ${(j.flags || []).map((f) => `<span class="tag warn">⚠ ${esc(f)}</span>`).join("")}
      </div>
      ${(j.skills || []).length ? `<div class="skills">${j.skills.map((s) => `<span>${esc(s)}</span>`).join("")}</div>` : ""}
      ${contact ? `<div class="contact">${contact}</div>` : ""}
      ${j.description ? `<details class="desc"><summary>Read the job description</summary><pre>${esc(j.description)}</pre></details>` : ""}
      <div class="actions">
        ${links}
        <button type="button" class="btn${saved.has(k) ? " saved" : ""}" data-act="save">${saved.has(k) ? "★ Saved" : "☆ Save"}</button>
        <button type="button" class="btn${applied.has(k) ? " on" : ""}" data-act="applied">${applied.has(k) ? "✓ Applied" : "Mark applied"}</button>
      </div>
    </article>`;
  }

  const inWindow = () => DATA.jobs.filter((j) => daysAgo(j) <= 14);

  function renderList() {
    const l = filtered();
    const all = inWindow();
    $("#n-all").textContent = all.length;
    $("#n-new").textContent = all.filter(isNew).length;
    $("#n-saved").textContent = all.filter((j) => saved.has(keyOf(j))).length;
    $("#n-applied").textContent = all.filter((j) => applied.has(keyOf(j))).length;
    $("#n-hidden").textContent = DATA.hidden.length;

    let note = `${l.length} job${l.length === 1 ? "" : "s"}`;
    if (tab === "hidden") {
      const hc = DATA.hidden_counts || {};
      const notListed = Object.entries(hc).filter(([r]) => !DATA.hidden.some((h) => h.hidden_reason === r));
      note += " hidden (senior or 2+ years, outside India, or asks for money)." +
        (notListed.length ? " Not listed at all: " + notListed.map(([r, n]) => `${n} ${r}`).join(", ") + "." : "");
    }
    $("#count").textContent = note;
    $("#list").innerHTML = l.length ? l.map(card).join("")
      : `<div class="empty">No jobs match these filters yet. Try a longer time window or fewer filters.</div>`;
  }

  function update() {
    store.set("filters", F);
    renderFilters();
    renderList();
  }

  // ---------- Excel ----------
  function toExcel(rows, name) {
    if (!window.XLSX) { alert("The Excel tool is still loading. Try again in a moment."); return; }
    const out = rows.map((j, i) => ({
      "No.": i + 1,
      "Posted (India time)": exact(j),
      "Posted": relative(j),
      "Job title": j.title,
      "Company": j.company,
      "Type": j.is_internship ? "Internship" : "Job",
      "Role group(s)": j.roles.join(", "),
      "Experience asked": j.experience || "",
      "Experience range": j.exp_range || "",
      "Location": j.location,
      "City": (j.areas || []).join(", "),
      "Work mode": j.work_mode || "",
      "Salary / stipend": j.salary,
      "Skills": (j.skills || []).join(", "),
      "Warnings": (j.flags || []).join(", "),
      "Office / work address": j.address,
      "Recruiter email(s)": (j.emails || []).join(", "),
      "Phone(s)": (j.phones || []).join(", "),
      "Platform": j.platform,
      "Job link": j.url,
      "Also posted on": (j.also_on || []).map((a) => `${a.platform}: ${a.url}`).join("\n"),
      "Company website": j.company_url,
      "Saved": saved.has(keyOf(j)) ? "Yes" : "",
      "Applied": applied.has(keyOf(j)) ? "Yes" : "",
      "Hidden because": j.hidden_reason || "",
      "Job description": (j.description || "").slice(0, 32000),
    }));
    const ws = XLSX.utils.json_to_sheet(out);
    const cols = Object.keys(out[0] || { x: 1 });
    ws["!cols"] = cols.map((c) => ({ wch: { "No.": 5, "Job title": 34, "Company": 28, "Job link": 45, "Job description": 80, "Skills": 30,
      "Office / work address": 32, "Recruiter email(s)": 28, "Posted (India time)": 30 }[c] || 16 }));
    const linkCol = cols.indexOf("Job link");
    out.forEach((r, i) => {
      const ref = XLSX.utils.encode_cell({ r: i + 1, c: linkCol });
      if (ws[ref] && r["Job link"]) ws[ref].l = { Target: r["Job link"] };
    });
    if (out.length) ws["!autofilter"] = { ref: XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: out.length, c: cols.length - 1 } }) };
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Jobs");
    const day = new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
    XLSX.writeFile(wb, `${name}_${day}.xlsx`);
  }

  // ---------- events ----------
  function wire() {
    $("#tabs").onclick = (e) => {
      const b = e.target.closest("button[data-tab]");
      if (!b) return;
      tab = b.dataset.tab;
      document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b));
      update();
    };
    let t;
    $("#f-q").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { F.q = e.target.value.trim(); update(); }, 150); };
    $("#f-sort").onchange = (e) => { F.sort = e.target.value; update(); };
    for (const k of ["salary", "email", "nocons", "nobond"]) $(`#f-${k}`).onchange = (e) => { F[k] = e.target.checked; update(); };
    $("#f-reset").onclick = () => { F = defaults(); update(); };
    $("#f-toggle").onclick = () => {
      const open = $(".filters").classList.toggle("open");
      $("#f-toggle").setAttribute("aria-expanded", String(open));
    };
    $("#list").onclick = async (e) => {
      const b = e.target.closest("button[data-act]");
      if (!b || b.disabled) return;
      const k = b.closest(".card").dataset.k;
      const isSave = b.dataset.act === "save";
      const set = isSave ? saved : applied;
      const want = !set.has(k);
      want ? set.add(k) : set.delete(k);       // optimistic
      renderList();
      const r = await api("api/status", isSave ? { key: k, saved: want } : { key: k, applied: want });
      if (!r || !r.ok) {
        want ? set.delete(k) : set.add(k);     // undo
        renderList();
        if (r) alert(r.data.error || "Couldn't save that. Please try again.");
      }
    };
    $("#refresh").onclick = async () => {
      const btn = $("#refresh");
      btn.disabled = true;
      btn.textContent = "Checking…";
      const r = await api("api/refresh");
      btn.disabled = false;
      btn.textContent = "↻ Check now";
      if (r) alert(r.data.message || r.data.error || "Done");
    };
    $("#dl-filtered").onclick = () => toExcel(filtered(), "Tech_jobs_filtered");
    $("#dl-all").onclick = () => toExcel([...DATA.jobs].sort((a, b) => (ts(b) || 0) - (ts(a) || 0)), "Tech_jobs_all");
  }

  const agoText = (iso) => {
    const mins = Math.round((Date.now() - Date.parse(iso)) / 60000);
    return mins < 1 ? "just now" : mins < 60 ? `${mins} min ago` : mins < 1440 ? `${Math.round(mins / 60)} h ago` : `${Math.round(mins / 1440)} days ago`;
  };

  function renderHeader() {
    $("#updated").textContent = DATA.generated_at
      ? `Updated ${agoText(DATA.generated_at)} · ${inWindow().length} jobs across India`
      : "The first search hasn't finished yet.";
    const perPlatform = {};
    for (const j of inWindow()) for (const p of platformsOf(j)) perPlatform[p] = (perPlatform[p] || 0) + 1;
    $("#sources").innerHTML = Object.entries(DATA.sources).map(([n, s]) => {
      const tip = s.ok ? `Last checked ${s.at ? agoText(s.at) : "–"}` : s.error;
      const label = s.running ? "searching…" : s.ok ? (perPlatform[n] || 0) : "blocked this time";
      return `<span class="src ${s.ok ? "ok" : "bad"}" title="${esc(tip)}">${esc(n)} ${esc(label)}</span>`;
    }).join("");
    $("#links").innerHTML = DATA.links.map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name)}</a></li>`).join("");
  }

  Promise.all([
    fetch("api/jobs").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
    fetch("api/status", { cache: "no-store" }).then((r) => (r.ok ? r.json() : {})).catch(() => ({})),
  ])
    .then(([d, marks]) => {
      for (const [k, m] of Object.entries(marks)) {
        if (m.saved) saved.add(k);
        if (m.applied) applied.add(k);
      }
      // Hidden jobs come one row per platform: merge copies of the same job into one card.
      const merged = new Map();
      for (const h of d.hidden) {
        const m = merged.get(h.dedupe_key);
        if (!m) merged.set(h.dedupe_key, { ...h, also_on: [] });
        else m.also_on.push({ platform: h.platform, url: h.url });
      }
      d.hidden = [...merged.values()];
      d.roles = Array.isArray(d.roles) ? d.roles : Object.keys(d.roles || {});
      DATA = d;
      // Drop remembered filter values that no longer exist.
      F.roles = F.roles.filter((r) => d.roles.includes(r));
      F.areas = F.areas.filter((a) => d.areas.includes(a));
      F.exps = F.exps.filter((x) => EXP_LEVELS.includes(x));
      F.platforms = F.platforms.filter((p) => p in d.sources);
      renderHeader();
      wire();
      update();
    })
    .catch(() => { $("#updated").textContent = "Couldn't load the jobs right now. Please refresh in a minute."; });
})();
