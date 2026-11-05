// SakayApp admin page: enter routes, stops and fares on a map.
"use strict";

const DAVAO = [7.0731, 125.6128];
const REUSE_STOP_M = 30;      // a placed stop this close to an existing stop reuses it (shared/transfer stop)
const FAR_FROM_LINE_M = 60;   // warn when a stop is this far from the drawn line
const VEHICLES = ["jeepney", "bus", "tricycle", "uv_express"];

const state = {
  token: sessionGet("sakay_token"),
  data: { stops: [], routes: [], fare_rules: [] },
  tab: "routes",
  draft: null,          // route being edited
  tool: null,           // "draw" | "stops" | null
  dirty: false,
  test: { origin: null, destination: null, rider: "regular", trips: [], selected: 0 },
};

// ---------------------------------------------------------------- utilities

function sessionGet(k) { try { return sessionStorage.getItem(k); } catch { return null; } }
function sessionSet(k, v) { try { v == null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v); } catch {} }

const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function status(msg, isError = false) {
  const el = $("#status");
  el.textContent = msg || "";
  el.classList.toggle("err", isError);
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401 && path !== "/auth/login") { logout(); throw new Error("Session expired, sign in again"); }
  if (res.status === 204) return null;
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = json.detail;
    throw new Error(Array.isArray(d) ? d.map((e) => `${e.loc.slice(1).join(".")}: ${e.msg}`).join("; ") : d || res.statusText);
  }
  return json;
}

const stopById = (id) => state.data.stops.find((s) => s.id === id);
const routesUsingStop = (id) => state.data.routes.filter((r) => r.stops.some((s) => s.id === id));
const today = () => new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------- map

const map = L.map("map", { zoomControl: true }).setView(DAVAO, 14);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const layers = {
  routes: L.layerGroup().addTo(map),
  stops: L.layerGroup().addTo(map),
  draft: L.layerGroup().addTo(map),
  test: L.layerGroup().addTo(map),
};

function dotIcon(color, size = 12) {
  return L.divIcon({ className: "", iconSize: [size, size],
    html: `<div class="stop-dot" style="width:${size}px;height:${size}px;background:${color}"></div>` });
}
function numIcon(n, color) {
  return L.divIcon({ className: "", iconSize: [20, 20],
    html: `<div class="num-icon" style="width:20px;height:20px;background:${color}">${n}</div>` });
}

function drawNetwork() {
  layers.routes.clearLayers();
  layers.stops.clearLayers();
  const editingId = state.draft?.id;
  for (const r of state.data.routes) {
    if (r.id === editingId) continue;
    const line = r.path_geojson?.coordinates?.map(([lng, lat]) => [lat, lng]) ??
      r.stops.map((s) => stopById(s.id)).filter(Boolean).map((s) => [s.lat, s.lng]);
    if (line.length < 2) continue;
    L.polyline(line, { color: r.color, weight: 4, opacity: state.draft || !r.is_active ? 0.35 : 0.8,
                       dashArray: r.is_active ? null : "6 6" })
      .bindTooltip(`${esc(r.code)} · ${esc(r.name)}`).addTo(layers.routes);
  }
  if (state.tab === "test") return;
  for (const s of state.data.stops) {
    const shared = routesUsingStop(s.id).length;
    const m = L.marker([s.lat, s.lng], {
      icon: dotIcon(shared > 1 ? "#6a1b9a" : shared ? "#455a64" : "#9e9e9e", shared > 1 ? 14 : 10),
      draggable: state.tab === "stops",
      title: s.name,
    });
    m.on("click", () => onStopClick(s));
    m.on("dragend", (e) => onStopDragged(s, e.target.getLatLng()));
    m.bindTooltip(`${esc(s.name)}${shared ? ` · ${shared} route(s)` : ""}`);
    m.addTo(layers.stops);
  }
}

map.on("click", (e) => {
  const p = { lat: e.latlng.lat, lng: e.latlng.lng };
  if (state.tab === "routes" && state.draft) {
    if (state.tool === "draw") addVertex(p);
    else if (state.tool === "stops") addStopAt(p);
  } else if (state.tab === "stops" && state.newStopMode) {
    createStopAt(p);
  } else if (state.tab === "test") {
    setTestPoint(p);
  }
});

// ---------------------------------------------------------------- auth

async function login(e) {
  e.preventDefault();
  const form = new FormData(e.target);
  $("#login-error").hidden = true;
  try {
    const res = await api("POST", "/auth/login", { email: form.get("email"), password: form.get("password") });
    state.token = res.token;
    sessionSet("sakay_token", res.token);
    await start();
  } catch (err) {
    $("#login-error").textContent = err.message;
    $("#login-error").hidden = false;
  }
}

function logout() {
  state.token = null;
  sessionSet("sakay_token", null);
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
}

async function loadData() {
  state.data = await api("GET", "/admin/data");
}

async function start() {
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  map.invalidateSize();
  try {
    await loadData();
    render();
    status(`${state.data.routes.length} routes, ${state.data.stops.length} stops loaded`);
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- tabs

function setTab(tab) {
  if (state.draft && state.dirty && !confirm("Discard unsaved route changes?")) return;
  state.tab = tab;
  state.draft = null; state.tool = null; state.dirty = false; state.newStopMode = false;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  layers.draft.clearLayers();
  layers.test.clearLayers();
  render();
}

function render() {
  const panel = $("#panel");
  if (state.tab === "routes") panel.innerHTML = state.draft ? routeEditorHtml() : routeListHtml();
  if (state.tab === "stops") panel.innerHTML = stopsHtml();
  if (state.tab === "fares") panel.innerHTML = faresHtml();
  if (state.tab === "test") panel.innerHTML = testHtml();
  drawNetwork();
  if (state.draft) drawDraft();
  if (state.tab === "test") drawTest();
  map.getContainer().style.cursor = state.tool || state.newStopMode || state.tab === "test" ? "crosshair" : "";
}

// ---------------------------------------------------------------- routes: list

function routeListHtml() {
  const items = state.data.routes.map((r) => `
    <li data-route="${r.id}">
      <span class="badge" style="background:${esc(r.color)}">${esc(r.code)}</span>
      <span class="grow"><div>${esc(r.name)}</div>
        <div class="sub">${r.stops.length} stops · ${r.total_km.toFixed(2)} km
          ${r.is_bidirectional ? "· both ways" : "· one way"}</div></span>
      ${r.is_active ? "" : '<span class="tag">inactive</span>'}
    </li>`).join("");
  return `
    <div class="actions"><button class="primary" data-act="new-route">+ New route</button></div>
    ${state.data.routes.length ? `<ul class="list">${items}</ul>` : '<p class="muted">No routes yet.</p>'}
    <p class="hint">Gray dots are stops; purple dots are shared by 2+ routes (transfer points).</p>`;
}

function editRoute(route) {
  const r = route ?? { code: "", name: "", color: "#1E88E5", vehicle_type: "jeepney",
    is_bidirectional: true, is_active: true, path_geojson: null, stops: [],
    data_source: "", collected_on: today() };
  state.draft = {
    id: r.id ?? null,
    code: r.code, name: r.name, color: r.color, vehicle_type: r.vehicle_type,
    is_bidirectional: r.is_bidirectional, is_active: r.is_active,
    data_source: r.data_source ?? "", collected_on: r.collected_on ?? "",
    path: (r.path_geojson?.coordinates ?? []).map(([lng, lat]) => ({ lat, lng })),
    stops: r.stops.map((s) => stopById(s.id)).filter(Boolean)
      .map((s) => ({ id: s.id, name: s.name, lat: s.lat, lng: s.lng, is_landmark: s.is_landmark })),
  };
  state.tool = state.draft.path.length < 2 ? "draw" : null;
  state.dirty = false;
  render();
  const pts = [...state.draft.path, ...state.draft.stops];
  if (pts.length) map.fitBounds(L.latLngBounds(pts.map((p) => [p.lat, p.lng])).pad(0.2));
}

// ---------------------------------------------------------------- routes: editor

function routeEditorHtml() {
  const d = state.draft;
  const len = d.path.length >= 2 ? Geo.pathLength(d.path) : 0;
  const stops = d.stops.map((s, i) => {
    const off = d.path.length >= 2 ? Geo.positionAlong(d.path, s).offset : 0;
    const others = s.id ? routesUsingStop(s.id).filter((r) => r.id !== d.id).map((r) => r.code) : [];
    return `
      <li>
        <span class="num" style="background:${esc(d.color)}">${i + 1}</span>
        ${s.id ? `<span class="grow">${s.is_landmark ? "★ " : ""}${esc(s.name)}
              ${others.length ? `<span class="shared">· also ${esc(others.join(", "))}</span>` : ""}</span>`
               : `<button class="link star ${s.is_landmark ? "on" : ""}" data-act="toggle-landmark" data-i="${i}"
                    title="${s.is_landmark ? "Landmark: named in directions" : "Generic stop: directions say “near” the closest landmark"}">${s.is_landmark ? "★" : "☆"}</button>
                  <input class="grow" data-stop-name="${i}" value="${esc(s.name)}" aria-label="Stop name">`}
        ${off > FAR_FROM_LINE_M ? `<span class="far" title="Far from the line">${Math.round(off)} m off</span>` : ""}
        <button class="link" data-act="zoom-stop" data-i="${i}" title="Show on map">◎</button>
        <button class="link" data-act="remove-stop" data-i="${i}" title="Remove from route">✕</button>
      </li>`;
  }).join("");

  return `
    <div class="actions"><button class="link" data-act="back">← All routes</button></div>
    <h2>${d.id ? "Edit route" : "New route"}</h2>
    <div class="row">
      <label class="shrink" style="width:90px">Code <input data-f="code" value="${esc(d.code)}" placeholder="R03" maxlength="20"></label>
      <label>Name <input data-f="name" value="${esc(d.name)}" placeholder="Toril – Bankerohan"></label>
    </div>
    <div class="row">
      <label class="shrink" style="width:70px">Color <input data-f="color" type="color" value="${esc(d.color)}"></label>
      <label>Vehicle
        <select data-f="vehicle_type">${VEHICLES.map((v) =>
          `<option ${v === d.vehicle_type ? "selected" : ""}>${v}</option>`).join("")}</select></label>
    </div>
    <label class="check"><input type="checkbox" data-f="is_bidirectional" ${d.is_bidirectional ? "checked" : ""}> Runs both ways on the same streets</label>
    <label class="check"><input type="checkbox" data-f="is_active" ${d.is_active ? "checked" : ""}> Active (shown to commuters)</label>
    <div class="row">
      <label>Data source <input data-f="data_source" value="${esc(d.data_source)}" placeholder="e.g. group ride, LTFRB list"></label>
      <label class="shrink" style="width:140px">Collected on <input data-f="collected_on" type="date" value="${esc(d.collected_on)}"></label>
    </div>

    <h2>1 · Route line <span class="muted small">${d.path.length} points · ${(len / 1000).toFixed(2)} km</span></h2>
    <p class="hint">Turn on drawing, then click along the streets in the direction the jeepney travels. Drag points to adjust; right-click a point to delete it.</p>
    <div class="actions">
      <button data-act="tool-draw" class="${state.tool === "draw" ? "on" : ""}">${state.tool === "draw" ? "Drawing… (click map)" : "Draw line"}</button>
      <button data-act="undo-vertex" ${d.path.length ? "" : "disabled"}>Undo point</button>
      <button data-act="clear-line" class="danger" ${d.path.length ? "" : "disabled"}>Clear line</button>
    </div>

    <h2>2 · Stops <span class="muted small">${d.stops.length} stops</span></h2>
    <p class="hint">Stops are kept in order along the line. A stop placed within ${REUSE_STOP_M} m of an existing stop reuses it, so routes that meet share a transfer stop.
      Rename stops at terminals, malls, schools and corners; they become ★ landmarks that directions name ("get off at …"). Other stops are described as "near" the closest landmark.</p>
    <div class="actions">
      <button data-act="tool-stops" class="${state.tool === "stops" ? "on" : ""}" ${d.path.length >= 2 ? "" : "disabled"}>${state.tool === "stops" ? "Placing… (click map)" : "Place stops"}</button>
    </div>
    <div class="row">
      <label>Auto-place every <input id="spacing" type="number" min="100" max="1000" step="50" value="250"></label>
      <span class="shrink muted" style="padding-top:18px">m</span>
      <button class="shrink" data-act="auto-stops" style="margin-top:14px" ${d.path.length >= 2 ? "" : "disabled"}>Auto-place</button>
    </div>
    <ul class="stop-list">${stops || '<li class="muted">No stops yet.</li>'}</ul>

    <div class="actions" style="margin-top:16px">
      <button class="primary" data-act="save-route">Save route</button>
      <button data-act="back">Cancel</button>
      ${d.id ? '<button class="danger" data-act="delete-route">Delete route</button>' : ""}
    </div>`;
}

function drawDraft() {
  const d = state.draft;
  layers.draft.clearLayers();
  if (d.path.length >= 2) {
    L.polyline(d.path.map((p) => [p.lat, p.lng]), { color: d.color, weight: 6, opacity: 0.9 }).addTo(layers.draft);
  }
  if (state.tool === "draw") {
    d.path.forEach((p, i) => {
      const m = L.marker([p.lat, p.lng], { icon: dotIcon("#fff", 12), draggable: true });
      m.on("drag", (e) => { d.path[i] = { lat: e.latlng.lat, lng: e.latlng.lng }; });
      m.on("dragend", () => { changed(); sortStops(); render(); });
      m.on("contextmenu", () => { d.path.splice(i, 1); changed(); sortStops(); render(); });
      m.addTo(layers.draft);
    });
  }
  d.stops.forEach((s, i) => L.marker([s.lat, s.lng], { icon: numIcon(i + 1, d.color), interactive: false })
    .addTo(layers.draft));
}

function changed() { state.dirty = true; }

function sortStops() {
  const d = state.draft;
  if (d.path.length < 2) return;
  d.stops.sort((a, b) => Geo.positionAlong(d.path, a).along - Geo.positionAlong(d.path, b).along);
}

function addVertex(p) {
  state.draft.path.push(p);
  changed(); sortStops(); render();
}

// Nearest existing stop (not already on this draft) within REUSE_STOP_M.
function reusableStop(p) {
  const onDraft = new Set(state.draft.stops.map((s) => s.id).filter(Boolean));
  return state.data.stops
    .filter((s) => !onDraft.has(s.id))
    .map((s) => ({ s, d: Geo.dist(s, p) }))
    .filter((x) => x.d <= REUSE_STOP_M)
    .sort((a, b) => a.d - b.d)[0]?.s;
}

function newStopName() {
  const code = state.draft.code || "Route";
  const newCount = state.draft.stops.filter((s) => !s.id).length;   // reused stops keep their names
  return `${code} stop ${newCount + 1}`;
}

function addStopAt(p) {
  const d = state.draft;
  const existing = reusableStop(p);
  if (existing) d.stops.push(draftStop(existing));
  else d.stops.push({ id: null, name: newStopName(), lat: p.lat, lng: p.lng, is_landmark: false });
  changed(); sortStops(); render();
}

function addExistingStop(s) {
  const d = state.draft;
  if (d.stops.some((x) => x.id === s.id)) { status(`${s.name} is already on this route`); return; }
  d.stops.push(draftStop(s));
  changed(); sortStops(); render();
}

const draftStop = (s) => ({ id: s.id, name: s.name, lat: s.lat, lng: s.lng, is_landmark: s.is_landmark });

function autoPlaceStops() {
  const d = state.draft;
  const spacing = Math.max(100, Number($("#spacing").value) || 250);
  let added = 0, reused = 0;
  // 1. Existing stops the line passes through become shared (transfer) stops.
  const onDraft = new Set(d.stops.map((s) => s.id).filter(Boolean));
  for (const s of state.data.stops) {
    if (!onDraft.has(s.id) && Geo.positionAlong(d.path, s).offset <= REUSE_STOP_M) {
      d.stops.push(draftStop(s)); reused++;
    }
  }
  // 2. Fill the gaps with evenly spaced stops.
  for (const p of Geo.pointsEvery(d.path, spacing)) {
    if (d.stops.some((s) => Geo.dist(s, p) < spacing / 2)) continue;   // already a stop nearby
    const existing = reusableStop(p);
    if (existing) { d.stops.push(draftStop(existing)); reused++; }
    else { d.stops.push({ id: null, name: newStopName(), lat: p.lat, lng: p.lng, is_landmark: false }); added++; }
  }
  changed(); sortStops(); render();
  status(`Added ${added} new stops, reused ${reused} existing. Rename the ones at landmarks; renamed stops become ★ landmarks.`);
}

async function saveRoute() {
  const d = state.draft;
  if (!d.code || !d.name) return status("Give the route a code and a name", true);
  if (d.stops.length < 2) return status("A route needs at least 2 stops", true);
  const body = {
    code: d.code.trim(), name: d.name.trim(), color: d.color, vehicle_type: d.vehicle_type,
    is_bidirectional: d.is_bidirectional, is_active: d.is_active,
    data_source: d.data_source || null, collected_on: d.collected_on || null,
    path: d.path,
    stops: d.stops.map((s) => (s.id ? { id: s.id }
      : { name: s.name.trim() || newStopName(), lat: s.lat, lng: s.lng, is_landmark: !!s.is_landmark })),
  };
  try {
    status("Saving…");
    const res = d.id ? await api("PUT", `/admin/routes/${d.id}`, body) : await api("POST", "/admin/routes", body);
    await loadData();
    state.dirty = false;
    editRoute(state.data.routes.find((r) => r.id === res.id));
    status(`Saved ${body.code}. Network reloaded: ${res.network.routes} routes, ${res.network.legs} legs.`);
  } catch (err) { status(err.message, true); }
}

async function deleteRoute() {
  const d = state.draft;
  if (!confirm(`Delete route ${d.code}? Its stops are kept.`)) return;
  try {
    await api("DELETE", `/admin/routes/${d.id}`);
    await loadData();
    state.dirty = false;
    setTab("routes");
    status(`Deleted ${d.code}`);
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- stops tab

function stopsHtml() {
  const q = (state.stopFilter || "").toLowerCase();
  const sel = state.selectedStop && stopById(state.selectedStop);
  const rows = state.data.stops
    .filter((s) => !q || s.name.toLowerCase().includes(q) || (s.landmark || "").toLowerCase().includes(q))
    .slice(0, 300)
    .map((s) => {
      const rs = routesUsingStop(s.id);
      return `<li data-stop="${s.id}">
        <span class="grow"><div>${s.is_landmark ? "★ " : ""}${esc(s.name)}</div>
          <div class="sub">${rs.length ? esc(rs.map((r) => r.code).join(", ")) : "not on any route"}${s.landmark ? " · " + esc(s.landmark) : ""}</div></span>
      </li>`;
    }).join("");
  return `
    <div class="actions">
      <button data-act="new-stop" class="${state.newStopMode ? "on" : ""}">${state.newStopMode ? "Click the map…" : "+ New stop"}</button>
    </div>
    <p class="hint">Drag a stop on the map to move it; route distances update automatically. ★ marks landmarks used in directions.</p>
    ${sel ? stopFormHtml(sel) : ""}
    <input id="stop-filter" placeholder="Filter stops" value="${esc(state.stopFilter || "")}">
    <ul class="list">${rows || '<li class="muted">No stops.</li>'}</ul>`;
}

function stopFormHtml(s) {
  const rs = routesUsingStop(s.id);
  return `
    <div class="card" style="width:100%;padding:12px;margin-bottom:12px">
      <label>Name <input id="sf-name" value="${esc(s.name)}"></label>
      <label class="check"><input type="checkbox" id="sf-is-landmark" ${s.is_landmark ? "checked" : ""}> ★ Landmark (named in directions)</label>
      <label>Description <input id="sf-landmark" value="${esc(s.landmark)}" placeholder="e.g. in front of SM Ecoland"></label>
      <div class="row">
        <label>Data source <input id="sf-source" value="${esc(s.data_source)}"></label>
        <label class="shrink" style="width:140px">Collected on <input id="sf-date" type="date" value="${esc(s.collected_on)}"></label>
      </div>
      <p class="hint">${s.lat.toFixed(6)}, ${s.lng.toFixed(6)} · ${rs.length ? "on " + esc(rs.map((r) => r.code).join(", ")) : "not on any route"}</p>
      <div class="actions">
        <button class="primary" data-act="save-stop">Save stop</button>
        <button data-act="close-stop">Close</button>
        <button class="danger" data-act="delete-stop" ${rs.length ? 'disabled title="Remove it from its routes first"' : ""}>Delete</button>
      </div>
    </div>`;
}

function onStopClick(s) {
  // Marker clicks don't reach the map, so handle the editing tools here too.
  if (state.tab === "routes" && state.draft && state.tool === "draw") return addVertex({ lat: s.lat, lng: s.lng });
  if (state.tab === "routes" && state.draft && state.tool === "stops") return addExistingStop(s);
  if (state.tab === "stops") { state.selectedStop = s.id; render(); map.panTo([s.lat, s.lng]); }
}

async function onStopDragged(s, latlng) {
  if (!confirm(`Move "${s.name}" here?`)) return render();
  try {
    await api("PATCH", `/admin/stops/${s.id}`, { lat: latlng.lat, lng: latlng.lng });
    await loadData(); render();
    status(`Moved ${s.name}`);
  } catch (err) { status(err.message, true); render(); }
}

async function createStopAt(p) {
  const name = prompt("Stop name (e.g. the nearest landmark):");
  state.newStopMode = false;
  if (!name) return render();
  try {
    const res = await api("POST", "/admin/stops", { name, lat: p.lat, lng: p.lng, collected_on: today() });
    await loadData();
    state.selectedStop = res.id;
    render();
    status(`Created ${name}`);
  } catch (err) { status(err.message, true); render(); }
}

async function saveStop() {
  const id = state.selectedStop;
  try {
    await api("PATCH", `/admin/stops/${id}`, {
      name: $("#sf-name").value.trim(), landmark: $("#sf-landmark").value.trim() || null,
      is_landmark: $("#sf-is-landmark").checked,
      data_source: $("#sf-source").value.trim() || null, collected_on: $("#sf-date").value || null,
    });
    await loadData(); render();
    status("Stop saved");
  } catch (err) { status(err.message, true); }
}

async function deleteStop() {
  const s = stopById(state.selectedStop);
  if (!confirm(`Delete stop "${s.name}"?`)) return;
  try {
    await api("DELETE", `/admin/stops/${s.id}`);
    state.selectedStop = null;
    await loadData(); render();
    status(`Deleted ${s.name}`);
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- fares tab

function faresHtml() {
  const f = state.editingFare;
  const rows = state.data.fare_rules.map((r) => `
    <tr data-fare="${r.id}" style="cursor:pointer">
      <td>${esc(r.vehicle_type)}</td><td>₱${r.base_fare.toFixed(2)} / ${r.base_km} km</td>
      <td>+₱${r.per_km_rate.toFixed(2)}/km</td><td>${Math.round(r.discount_rate * 100)}%</td>
      <td>${esc(r.effective_date)}${r.is_placeholder ? ' <span class="tag">placeholder</span>' : ""}</td>
    </tr>`).join("");
  const anyReal = state.data.fare_rules.some((r) => !r.is_placeholder);
  return `
    ${anyReal ? "" : '<div class="notice">No real fare rule yet, so the app shows fares as unavailable. Add the official LTFRB fare matrix values with their citation.</div>'}
    <table><thead><tr><th>Vehicle</th><th>Base</th><th>Per km</th><th>Disc.</th><th>Effective</th></tr></thead>
      <tbody>${rows}</tbody></table>
    <p class="hint">The rule with the latest effective date on or before today is used. Click a row to edit it.</p>
    <h2>${f?.id ? "Edit fare rule" : "Add fare rule"}</h2>
    <form id="fare-form">
      <label>Vehicle <select name="vehicle_type">${VEHICLES.map((v) =>
        `<option ${v === (f?.vehicle_type ?? "jeepney") ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <div class="row">
        <label>Base fare (₱) <input name="base_fare" type="number" step="0.01" min="0" required value="${f?.base_fare ?? ""}"></label>
        <label>Base distance (km) <input name="base_km" type="number" step="0.01" min="0" required value="${f?.base_km ?? ""}"></label>
      </div>
      <div class="row">
        <label>Each extra km (₱) <input name="per_km_rate" type="number" step="0.01" min="0" required value="${f?.per_km_rate ?? ""}"></label>
        <label>Discount (0–1) <input name="discount_rate" type="number" step="0.001" min="0" max="0.999" required value="${f?.discount_rate ?? ""}"></label>
      </div>
      <label>Effective date <input name="effective_date" type="date" required value="${esc(f?.effective_date ?? "")}"></label>
      <label>Source / citation <input name="source" required minlength="3" value="${esc(f?.source ?? "")}" placeholder="e.g. LTFRB Memorandum Circular No. …"></label>
      <label class="check"><input type="checkbox" name="is_placeholder" ${f?.is_placeholder ? "checked" : ""}> Placeholder (not shown to commuters)</label>
      <div class="actions">
        <button class="primary" type="submit">${f?.id ? "Save changes" : "Add rule"}</button>
        ${f?.id ? '<button type="button" data-act="cancel-fare">Cancel</button><button type="button" class="danger" data-act="delete-fare">Delete</button>' : ""}
      </div>
    </form>`;
}

async function saveFare(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {
    vehicle_type: fd.get("vehicle_type"), base_fare: fd.get("base_fare"), base_km: fd.get("base_km"),
    per_km_rate: fd.get("per_km_rate"), discount_rate: fd.get("discount_rate"),
    effective_date: fd.get("effective_date"), source: fd.get("source").trim(),
    is_placeholder: fd.get("is_placeholder") === "on",
  };
  const id = state.editingFare?.id;
  try {
    id ? await api("PUT", `/admin/fare-rules/${id}`, body) : await api("POST", "/admin/fare-rules", body);
    state.editingFare = null;
    await loadData(); render();
    status("Fare rule saved");
  } catch (err) { status(err.message, true); }
}

async function deleteFare() {
  if (!confirm("Delete this fare rule?")) return;
  try {
    await api("DELETE", `/admin/fare-rules/${state.editingFare.id}`);
    state.editingFare = null;
    await loadData(); render();
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- test tab

function testHtml() {
  const t = state.test;
  const pt = (p) => (p ? `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}` : "—");
  const trips = t.trips.map((trip, i) => `
    <div class="trip ${i === t.selected ? "sel" : ""}" data-trip="${i}">
      <div class="row">
        <span>${trip.route_codes.map((c) => {
          const r = state.data.routes.find((x) => x.code === c);
          return `<span class="badge" style="background:${esc(r?.color ?? "#555")}">${esc(c)}</span>`;
        }).join(" → ")}</span>
        <span class="shrink">${trip.minutes} min · ${trip.fare_available ? "₱" + trip.total_fare.toFixed(2) : "fare n/a"}</span>
      </div>
      <ol>${trip.segments.map((s) => `<li>${esc(s.instruction)}${s.kind === "ride" && s.fare != null ? ` · ₱${s.fare.toFixed(2)}` : ""}</li>`).join("")}</ol>
    </div>`).join("");
  return `
    <p class="hint">Click the map to set the start, then the destination. Uses the same planner as the app (active routes only); test searches are not counted in the stats.</p>
    <p>Start: <strong>${pt(t.origin)}</strong><br>Destination: <strong>${pt(t.destination)}</strong></p>
    <label>Rider <select id="test-rider">${["regular", "student", "senior", "pwd"].map((r) =>
      `<option ${r === t.rider ? "selected" : ""}>${r}</option>`).join("")}</select></label>
    <div class="actions"><button data-act="test-reset">Reset</button></div>
    ${t.notice ? `<div class="notice">${esc(t.notice)}</div>` : ""}
    ${trips}`;
}

function setTestPoint(p) {
  const t = state.test;
  if (!t.origin || t.destination) { t.origin = p; t.destination = null; t.trips = []; t.notice = null; }
  else { t.destination = p; runTest(); }
  render();
}

async function runTest() {
  const t = state.test;
  try {
    const res = await api("POST", "/trips/plan?log_search=false",
      { origin: t.origin, destination: t.destination, rider_type: t.rider });
    t.trips = res.trips; t.notice = res.notice; t.selected = 0;
    render();
  } catch (err) { status(err.message, true); }
}

function drawTest() {
  const t = state.test;
  layers.test.clearLayers();
  if (t.origin) L.marker([t.origin.lat, t.origin.lng], { icon: dotIcon("#2e7d32", 16), title: "Start" }).addTo(layers.test);
  if (t.destination) L.marker([t.destination.lat, t.destination.lng], { icon: dotIcon("#c62828", 16), title: "Destination" }).addTo(layers.test);
  const trip = t.trips[t.selected];
  if (!trip) return;
  for (const s of trip.segments) {
    const line = s.path.map((p) => [p.lat, p.lng]);
    if (s.kind === "walk") L.polyline(line, { color: "#555", weight: 3, dashArray: "4 6" }).addTo(layers.test);
    else {
      L.polyline(line, { color: s.route.color, weight: 6 }).bindTooltip(s.route.code).addTo(layers.test);
      [s.board, s.alight].forEach((st) => L.marker([st.lat, st.lng], { icon: dotIcon(s.route.color, 12), title: st.name }).addTo(layers.test));
    }
  }
}

// ---------------------------------------------------------------- events

document.addEventListener("click", (e) => {
  const tabBtn = e.target.closest(".tabs button");
  if (tabBtn) return setTab(tabBtn.dataset.tab);

  const routeLi = e.target.closest("[data-route]");
  if (routeLi) return editRoute(state.data.routes.find((r) => r.id === Number(routeLi.dataset.route)));
  const stopLi = e.target.closest("[data-stop]");
  if (stopLi) { const s = stopById(Number(stopLi.dataset.stop)); return onStopClick(s); }
  const fareTr = e.target.closest("[data-fare]");
  if (fareTr) { state.editingFare = state.data.fare_rules.find((f) => f.id === Number(fareTr.dataset.fare)); return render(); }
  const tripDiv = e.target.closest("[data-trip]");
  if (tripDiv) { state.test.selected = Number(tripDiv.dataset.trip); return render(); }

  const act = e.target.closest("[data-act]")?.dataset.act;
  if (!act) return;
  const i = Number(e.target.closest("[data-i]")?.dataset.i);
  const d = state.draft;
  const actions = {
    "new-route": () => editRoute(null),
    back: () => setTab("routes"),
    "tool-draw": () => { state.tool = state.tool === "draw" ? null : "draw"; render(); },
    "tool-stops": () => { state.tool = state.tool === "stops" ? null : "stops"; render(); },
    "undo-vertex": () => { d.path.pop(); changed(); sortStops(); render(); },
    "clear-line": () => { if (confirm("Clear the whole line?")) { d.path = []; changed(); render(); } },
    "auto-stops": autoPlaceStops,
    "remove-stop": () => { d.stops.splice(i, 1); changed(); render(); },
    "toggle-landmark": () => { d.stops[i].is_landmark = !d.stops[i].is_landmark; changed(); render(); },
    "zoom-stop": () => map.setView([d.stops[i].lat, d.stops[i].lng], 17),
    "save-route": saveRoute,
    "delete-route": deleteRoute,
    "new-stop": () => { state.newStopMode = !state.newStopMode; render(); },
    "save-stop": saveStop,
    "close-stop": () => { state.selectedStop = null; render(); },
    "delete-stop": deleteStop,
    "cancel-fare": () => { state.editingFare = null; render(); },
    "delete-fare": deleteFare,
    "test-reset": () => { state.test = { ...state.test, origin: null, destination: null, trips: [], notice: null }; render(); },
  };
  actions[act]?.();
});

document.addEventListener("input", (e) => {
  const d = state.draft;
  const f = e.target.dataset.f;
  if (d && f) {
    d[f] = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    changed();
    if (f === "color") drawDraft();
    return;
  }
  if (d && e.target.dataset.stopName !== undefined) {
    const st = d.stops[Number(e.target.dataset.stopName)];
    st.name = e.target.value;
    if (!st.is_landmark) {                    // renaming a generic stop makes it a landmark
      st.is_landmark = true;
      const star = e.target.parentElement.querySelector(".star");
      if (star) { star.textContent = "★"; star.classList.add("on"); }
    }
    changed();
    return;
  }
  if (e.target.id === "stop-filter") {
    state.stopFilter = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const input = $("#stop-filter"); input.focus(); input.setSelectionRange(pos, pos);
  }
});

document.addEventListener("change", (e) => {
  if (e.target.id === "test-rider") {
    state.test.rider = e.target.value;
    if (state.test.origin && state.test.destination) runTest();
  }
});

document.addEventListener("submit", (e) => {
  if (e.target.id === "login-form") return login(e);
  if (e.target.id === "fare-form") return saveFare(e);
});

$("#logout").addEventListener("click", logout);
window.addEventListener("beforeunload", (e) => { if (state.dirty) e.preventDefault(); });

// ---------------------------------------------------------------- boot
if (state.token) start(); else logout();
