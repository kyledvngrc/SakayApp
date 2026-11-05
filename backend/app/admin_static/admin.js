// SakayApp admin page: draw routes, add landmarks and fares on a map.
"use strict";

const DAVAO = [7.0731, 125.6128];
const LOOP_TOLERANCE_M = 100;   // a one-way line ending this close to its start is a loop (matches config.py)
const VEHICLES = ["jeepney", "bus", "tricycle", "uv_express"];

const state = {
  token: sessionGet("sakay_token"),
  data: { landmarks: [], routes: [], fare_rules: [], transfer_points: [] },
  tab: "routes",
  draft: null,          // route being edited
  drawing: false,
  dirty: false,
  newLandmarkMode: false,
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

const landmarkById = (id) => state.data.landmarks.find((s) => s.id === id);
const today = () => new Date().toISOString().slice(0, 10);
const kindText = { both: "both ways", oneway: "one way", loop: "one-way loop" };

function draftKind(d) {
  if (d.is_bidirectional) return "both";
  return d.path.length > 2 && Geo.dist(d.path[0], d.path[d.path.length - 1]) <= LOOP_TOLERANCE_M ? "loop" : "oneway";
}

// ---------------------------------------------------------------- map

const map = L.map("map", { zoomControl: true }).setView(DAVAO, 14);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const layers = {
  routes: L.layerGroup().addTo(map),
  landmarks: L.layerGroup().addTo(map),
  draft: L.layerGroup().addTo(map),
  test: L.layerGroup().addTo(map),
};

function dotIcon(color, size = 12) {
  return L.divIcon({ className: "", iconSize: [size, size],
    html: `<div class="stop-dot" style="width:${size}px;height:${size}px;background:${color}"></div>` });
}
function labelIcon(text, color) {
  return L.divIcon({ className: "", iconSize: [20, 20],
    html: `<div class="num-icon" style="width:20px;height:20px;background:${color}">${text}</div>` });
}

const routeLine = (r) => (r.path_geojson?.coordinates ?? []).map(([lng, lat]) => [lat, lng]);

function drawNetwork() {
  layers.routes.clearLayers();
  layers.landmarks.clearLayers();
  const editingId = state.draft?.id;
  for (const r of state.data.routes) {
    if (r.id === editingId) continue;
    const line = routeLine(r);
    if (line.length < 2) continue;
    L.polyline(line, { color: r.color, weight: 4, opacity: state.draft || !r.is_active ? 0.35 : 0.8,
                       dashArray: r.is_active ? null : "6 6", interactive: !state.drawing })
      .bindTooltip(`${esc(r.code)} · ${esc(r.name)}`).addTo(layers.routes);
  }
  if (state.tab === "routes" && !state.draft) {
    for (const t of state.data.transfer_points) {
      L.circleMarker([t.lat, t.lng], { radius: 4, color: "#6a1b9a", weight: 1, fillOpacity: 0.8 })
        .bindTooltip(`${esc(t.from)} → ${esc(t.to)} · ${t.walk_m < 15 ? "lines meet" : `walk ${t.walk_m} m`}`)
        .addTo(layers.routes);
    }
  }
  if (state.tab === "test") return;
  for (const s of state.data.landmarks) {
    const m = L.marker([s.lat, s.lng], {
      icon: dotIcon("#f2a900", 12),
      draggable: state.tab === "landmarks",
      title: s.name,
    });
    m.on("click", () => onLandmarkClick(s));
    m.on("dragend", (e) => onLandmarkDragged(s, e.target.getLatLng()));
    m.bindTooltip(`★ ${esc(s.name)}`);
    m.addTo(layers.landmarks);
  }
}

map.on("click", (e) => {
  const p = { lat: e.latlng.lat, lng: e.latlng.lng };
  if (state.tab === "routes" && state.draft && state.drawing) addVertex(p);
  else if (state.tab === "landmarks" && state.newLandmarkMode) createLandmarkAt(p);
  else if (state.tab === "test") setTestPoint(p);
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
    status(`${state.data.routes.length} routes, ${state.data.landmarks.length} landmarks, ` +
           `${state.data.transfer_points.length} transfer points`);
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- tabs

function setTab(tab) {
  if (state.draft && state.dirty && !confirm("Discard unsaved route changes?")) return;
  state.tab = tab;
  state.draft = null; state.drawing = false; state.dirty = false; state.newLandmarkMode = false;
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  layers.draft.clearLayers();
  layers.test.clearLayers();
  render();
}

function render() {
  const panel = $("#panel");
  if (state.tab === "routes") panel.innerHTML = state.draft ? routeEditorHtml() : routeListHtml();
  if (state.tab === "landmarks") panel.innerHTML = landmarksHtml();
  if (state.tab === "fares") panel.innerHTML = faresHtml();
  if (state.tab === "test") panel.innerHTML = testHtml();
  drawNetwork();
  if (state.draft) drawDraft();
  if (state.tab === "test") drawTest();
  map.getContainer().style.cursor = state.drawing || state.newLandmarkMode || state.tab === "test" ? "crosshair" : "";
}

// ---------------------------------------------------------------- routes: list

function routeListHtml() {
  const items = state.data.routes.map((r) => `
    <li data-route="${r.id}">
      <span class="badge" style="background:${esc(r.color)}">${esc(r.code)}</span>
      <span class="grow"><div>${esc(r.name)}</div>
        <div class="sub">${r.length_km.toFixed(2)} km · ${kindText[draftKind({ is_bidirectional: r.is_bidirectional,
          path: routeLine(r).map(([lat, lng]) => ({ lat, lng })) })]}</div></span>
      ${r.is_active ? "" : '<span class="tag">inactive</span>'}
    </li>`).join("");
  return `
    <div class="actions"><button class="primary" data-act="new-route">+ New route</button></div>
    ${state.data.routes.length ? `<ul class="list">${items}</ul>` : '<p class="muted">No routes yet.</p>'}
    <p class="hint">Purple dots are transfer points, found automatically where routes cross or pass within
      a short walk of each other. Yellow dots are landmarks.</p>`;
}

function editRoute(route) {
  const r = route ?? { code: "", name: "", color: "#1E88E5", vehicle_type: "jeepney",
    is_bidirectional: true, is_active: true, path_geojson: null,
    data_source: "", collected_on: today() };
  state.draft = {
    id: r.id ?? null,
    code: r.code, name: r.name, color: r.color, vehicle_type: r.vehicle_type,
    is_bidirectional: r.is_bidirectional, is_active: r.is_active,
    data_source: r.data_source ?? "", collected_on: r.collected_on ?? "",
    path: (r.path_geojson?.coordinates ?? []).map(([lng, lat]) => ({ lat, lng })),
  };
  state.drawing = state.draft.path.length < 2;
  state.dirty = false;
  render();
  if (state.draft.path.length) map.fitBounds(L.latLngBounds(state.draft.path.map((p) => [p.lat, p.lng])).pad(0.2));
}

// ---------------------------------------------------------------- routes: editor

function routeEditorHtml() {
  const d = state.draft;
  const len = d.path.length >= 2 ? Geo.pathLength(d.path) : 0;
  const kind = draftKind(d);
  return `
    <div class="actions"><button class="link" data-act="back">← All routes</button></div>
    <h2>${d.id ? "Edit route" : "New route"}</h2>
    <div class="row">
      <label class="shrink" style="width:90px">Code <input data-f="code" value="${esc(d.code)}" placeholder="R03" maxlength="20"></label>
      <label>Name <input data-f="name" value="${esc(d.name)}" placeholder="Toril – Bankerohan"></label>
    </div>
    <p class="hint">Code: a short label for badges (letters, digits, - or _), e.g. the signboard name.
      Name it “Start – End” in the direction you draw, so directions can say “toward End”.</p>
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

    <h2>Route line <span class="muted small">${d.path.length} points · ${(len / 1000).toFixed(2)} km · ${kindText[kind]}</span></h2>
    <p class="hint">Click along the streets in the order the jeepney drives, from <b>S</b> (start) to <b>E</b> (end).
      Click on the line to insert a point, drag points to adjust, right-click a point to delete it.
      ${d.is_bidirectional ? "" : "For a one-way loop, finish back at the start; it is detected automatically."}
      Commuters can board and get off anywhere on the line; transfers are found where lines cross or come within 200 m.</p>
    <div class="actions">
      <button data-act="tool-draw" class="${state.drawing ? "on" : ""}">${state.drawing ? "Drawing… (click map)" : "Draw / edit line"}</button>
      <button data-act="undo-vertex" ${d.path.length ? "" : "disabled"}>Undo point</button>
      <button data-act="reverse-line" ${d.path.length >= 2 ? "" : "disabled"}>Reverse direction</button>
      <button data-act="clear-line" class="danger" ${d.path.length ? "" : "disabled"}>Clear line</button>
    </div>

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
    const line = L.polyline(d.path.map((p) => [p.lat, p.lng]), { color: d.color, weight: 6, opacity: 0.9 });
    line.on("click", (e) => {
      if (!state.drawing) return;
      L.DomEvent.stopPropagation(e);
      const p = { lat: e.latlng.lat, lng: e.latlng.lng };
      d.path.splice(Geo.nearestSegment(d.path, p) + 1, 0, p);
      changed(); render();
    });
    line.addTo(layers.draft);
  }
  if (state.drawing) {
    d.path.forEach((p, i) => {
      const m = L.marker([p.lat, p.lng], { icon: dotIcon("#fff", 12), draggable: true });
      m.on("drag", (e) => { d.path[i] = { lat: e.latlng.lat, lng: e.latlng.lng }; });
      m.on("dragend", () => { changed(); render(); });
      m.on("contextmenu", () => { d.path.splice(i, 1); changed(); render(); });
      m.addTo(layers.draft);
    });
  }
  if (d.path.length) {
    L.marker([d.path[0].lat, d.path[0].lng], { icon: labelIcon("S", "#2e7d32"), interactive: false }).addTo(layers.draft);
  }
  if (d.path.length >= 2) {
    const end = d.path[d.path.length - 1];
    L.marker([end.lat, end.lng], { icon: labelIcon("E", "#c62828"), interactive: false }).addTo(layers.draft);
  }
}

function changed() { state.dirty = true; }

function addVertex(p) {
  state.draft.path.push(p);
  changed(); render();
}

async function saveRoute() {
  const d = state.draft;
  if (!d.code || !d.name) return status("Give the route a code and a name", true);
  if (d.path.length < 2) return status("Draw the route line first (at least 2 points)", true);
  const body = {
    code: d.code.trim(), name: d.name.trim(), color: d.color, vehicle_type: d.vehicle_type,
    is_bidirectional: d.is_bidirectional, is_active: d.is_active,
    data_source: d.data_source || null, collected_on: d.collected_on || null,
    path: d.path,
  };
  try {
    status("Saving…");
    const res = d.id ? await api("PUT", `/admin/routes/${d.id}`, body) : await api("POST", "/admin/routes", body);
    await loadData();
    state.dirty = false;
    editRoute(state.data.routes.find((r) => r.id === res.id));
    status(`Saved ${body.code}. Network reloaded: ${res.network.routes} routes, ${res.network.transfer_points} transfer points.`);
  } catch (err) { status(err.message, true); }
}

async function deleteRoute() {
  const d = state.draft;
  if (!confirm(`Delete route ${d.code}?`)) return;
  try {
    await api("DELETE", `/admin/routes/${d.id}`);
    await loadData();
    state.dirty = false;
    setTab("routes");
    status(`Deleted ${d.code}`);
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- landmarks tab

function landmarksHtml() {
  const q = (state.landmarkFilter || "").toLowerCase();
  const sel = state.selectedLandmark && landmarkById(state.selectedLandmark);
  const rows = state.data.landmarks
    .filter((s) => !q || s.name.toLowerCase().includes(q) || (s.description || "").toLowerCase().includes(q))
    .slice(0, 300)
    .map((s) => `<li data-landmark="${s.id}">
        <span class="grow"><div>★ ${esc(s.name)}</div>
          ${s.description ? `<div class="sub">${esc(s.description)}</div>` : ""}</span>
      </li>`).join("");
  return `
    <div class="actions">
      <button data-act="new-landmark" class="${state.newLandmarkMode ? "on" : ""}">${state.newLandmarkMode ? "Click the map…" : "+ New landmark"}</button>
    </div>
    <p class="hint">Optional. Landmarks name the places in directions (“get off near SM Ecoland”).
      Add them at terminals, malls, schools, churches and well-known corners, close to the road. Drag one on the map to move it.</p>
    ${sel ? landmarkFormHtml(sel) : ""}
    <input id="landmark-filter" placeholder="Filter landmarks" value="${esc(state.landmarkFilter || "")}">
    <ul class="list">${rows || '<li class="muted">No landmarks yet.</li>'}</ul>`;
}

function landmarkFormHtml(s) {
  return `
    <div class="card" style="width:100%;padding:12px;margin-bottom:12px">
      <label>Name <input id="lf-name" value="${esc(s.name)}"></label>
      <label>Description <input id="lf-description" value="${esc(s.description)}" placeholder="e.g. in front of the main gate"></label>
      <div class="row">
        <label>Data source <input id="lf-source" value="${esc(s.data_source)}"></label>
        <label class="shrink" style="width:140px">Collected on <input id="lf-date" type="date" value="${esc(s.collected_on)}"></label>
      </div>
      <p class="hint">${s.lat.toFixed(6)}, ${s.lng.toFixed(6)}</p>
      <div class="actions">
        <button class="primary" data-act="save-landmark">Save landmark</button>
        <button data-act="close-landmark">Close</button>
        <button class="danger" data-act="delete-landmark">Delete</button>
      </div>
    </div>`;
}

function onLandmarkClick(s) {
  // Marker clicks don't reach the map, so pass them to the line tool too.
  if (state.tab === "routes" && state.draft && state.drawing) return addVertex({ lat: s.lat, lng: s.lng });
  if (state.tab === "landmarks") { state.selectedLandmark = s.id; render(); map.panTo([s.lat, s.lng]); }
}

async function onLandmarkDragged(s, latlng) {
  if (!confirm(`Move "${s.name}" here?`)) return render();
  try {
    await api("PATCH", `/admin/landmarks/${s.id}`, { lat: latlng.lat, lng: latlng.lng });
    await loadData(); render();
    status(`Moved ${s.name}`);
  } catch (err) { status(err.message, true); render(); }
}

async function createLandmarkAt(p) {
  const name = prompt("Landmark name (e.g. SM Ecoland):");
  state.newLandmarkMode = false;
  if (!name) return render();
  try {
    const res = await api("POST", "/admin/landmarks", { name, lat: p.lat, lng: p.lng, collected_on: today() });
    await loadData();
    state.selectedLandmark = res.id;
    render();
    status(`Created ${name}`);
  } catch (err) { status(err.message, true); render(); }
}

async function saveLandmark() {
  const id = state.selectedLandmark;
  try {
    await api("PATCH", `/admin/landmarks/${id}`, {
      name: $("#lf-name").value.trim(), description: $("#lf-description").value.trim() || null,
      data_source: $("#lf-source").value.trim() || null, collected_on: $("#lf-date").value || null,
    });
    await loadData(); render();
    status("Landmark saved");
  } catch (err) { status(err.message, true); }
}

async function deleteLandmark() {
  const s = landmarkById(state.selectedLandmark);
  if (!confirm(`Delete landmark "${s.name}"?`)) return;
  try {
    await api("DELETE", `/admin/landmarks/${s.id}`);
    state.selectedLandmark = null;
    await loadData(); render();
    status(`Deleted ${s.name}`);
  } catch (err) { status(err.message, true); }
}

// ---------------------------------------------------------------- fares tab

function faresHtml() {
  const f = state.editingFare;
  const rows = state.data.fare_rules.map((r) => `
    <tr data-fare="${r.id}" style="cursor:pointer">
      <td>${esc(r.vehicle_type)}</td><td>${r.base_km} km</td>
      <td>₱${r.base_fare.toFixed(2)} + ₱${r.per_km_rate.toFixed(2)}/km</td>
      <td>₱${r.discounted_base_fare.toFixed(2)} + ₱${r.discounted_per_km_rate.toFixed(2)}/km</td>
      <td>${esc(r.effective_date)}${r.is_placeholder ? ' <span class="tag">placeholder</span>' : ""}</td>
    </tr>`).join("");
  const anyReal = state.data.fare_rules.some((r) => !r.is_placeholder);
  return `
    ${anyReal ? "" : '<div class="notice">No real fare rule yet, so the app shows fares as unavailable. Add the official LTFRB fare matrix values with their citation.</div>'}
    <table><thead><tr><th>Vehicle</th><th>Base km</th><th>Regular</th><th>Discounted</th><th>Effective</th></tr></thead>
      <tbody>${rows}</tbody></table>
    <p class="hint">The rule with the latest effective date on or before today is used. Click a row to edit it.</p>
    <h2>${f?.id ? "Edit fare rule" : "Add fare rule"}</h2>
    <form id="fare-form">
      <label>Vehicle <select name="vehicle_type">${VEHICLES.map((v) =>
        `<option ${v === (f?.vehicle_type ?? "jeepney") ? "selected" : ""}>${v}</option>`).join("")}</select></label>
      <label>Base distance (km) <input name="base_km" type="number" step="0.01" min="0" required value="${f?.base_km ?? ""}"></label>
      <p class="hint">The base fare covers the base distance; each started kilometre after it adds the per-km amount.</p>
      <div class="row">
        <label>Regular base fare (₱) <input name="base_fare" type="number" step="0.01" min="0" required value="${f?.base_fare ?? ""}"></label>
        <label>Regular per extra km (₱) <input name="per_km_rate" type="number" step="0.01" min="0" required value="${f?.per_km_rate ?? ""}"></label>
      </div>
      <div class="row">
        <label>Discounted base fare (₱) <input name="discounted_base_fare" type="number" step="0.01" min="0" required value="${f?.discounted_base_fare ?? ""}"></label>
        <label>Discounted per extra km (₱) <input name="discounted_per_km_rate" type="number" step="0.01" min="0" required value="${f?.discounted_per_km_rate ?? ""}"></label>
      </div>
      <p class="hint">Discounted: students, seniors and PWDs. Enter the amounts exactly as listed in the fare matrix.</p>
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
    per_km_rate: fd.get("per_km_rate"), discounted_base_fare: fd.get("discounted_base_fare"),
    discounted_per_km_rate: fd.get("discounted_per_km_rate"),
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

const distText = (m) => (m < 950 ? `${Math.max(10, Math.round(m / 10) * 10)} m` : `${(m / 1000).toFixed(1)} km`);

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
        <span class="shrink">${trip.fare_available ? "₱" + trip.total_fare.toFixed(2) : "fare n/a"}</span>
      </div>
      <div class="sub muted small">${trip.ride_km.toFixed(1)} km ride · ${distText(trip.walking_m)} walk</div>
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
      [["Get on", s.board], ["Get off", s.alight]].forEach(([what, p]) =>
        L.marker([p.lat, p.lng], { icon: dotIcon(s.route.color, 12),
          title: `${what} ${s.route.code}${p.place.name ? ` (${p.place.kind} ${p.place.name})` : ""}` }).addTo(layers.test));
    }
  }
}

// ---------------------------------------------------------------- events

document.addEventListener("click", (e) => {
  const tabBtn = e.target.closest(".tabs button");
  if (tabBtn) return setTab(tabBtn.dataset.tab);

  const routeLi = e.target.closest("[data-route]");
  if (routeLi) return editRoute(state.data.routes.find((r) => r.id === Number(routeLi.dataset.route)));
  const landmarkLi = e.target.closest("[data-landmark]");
  if (landmarkLi) return onLandmarkClick(landmarkById(Number(landmarkLi.dataset.landmark)));
  const fareTr = e.target.closest("[data-fare]");
  if (fareTr) { state.editingFare = state.data.fare_rules.find((f) => f.id === Number(fareTr.dataset.fare)); return render(); }
  const tripDiv = e.target.closest("[data-trip]");
  if (tripDiv) { state.test.selected = Number(tripDiv.dataset.trip); return render(); }

  const act = e.target.closest("[data-act]")?.dataset.act;
  if (!act) return;
  const d = state.draft;
  const actions = {
    "new-route": () => editRoute(null),
    back: () => setTab("routes"),
    "tool-draw": () => { state.drawing = !state.drawing; render(); },
    "undo-vertex": () => { d.path.pop(); changed(); render(); },
    "reverse-line": () => { d.path.reverse(); changed(); render(); },
    "clear-line": () => { if (confirm("Clear the whole line?")) { d.path = []; changed(); render(); } },
    "save-route": saveRoute,
    "delete-route": deleteRoute,
    "new-landmark": () => { state.newLandmarkMode = !state.newLandmarkMode; render(); },
    "save-landmark": saveLandmark,
    "close-landmark": () => { state.selectedLandmark = null; render(); },
    "delete-landmark": deleteLandmark,
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
    if (f === "is_bidirectional") render();
    return;
  }
  if (e.target.id === "landmark-filter") {
    state.landmarkFilter = e.target.value;
    const pos = e.target.selectionStart;
    render();
    const input = $("#landmark-filter"); input.focus(); input.setSelectionRange(pos, pos);
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
