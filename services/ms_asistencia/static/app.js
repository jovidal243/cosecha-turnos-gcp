// App del supervisor y del jefe de frente. Offline-first:
// cada marcación recibe un UUID en el dispositivo, se guarda en IndexedDB
// y se sincroniza en lote cuando hay conexión (el backend es idempotente).
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const hora = (ts) => (ts ? new Date(ts).toLocaleString("es-CO", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) : "—");
const hoyISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

let TOKEN = localStorage.getItem("token") || "";
let ROL = "";
let CATALOGO = JSON.parse(localStorage.getItem("catalogo") || '{"frentes":[],"trabajadores":[]}');

// ---------- IndexedDB: cola de marcaciones ----------
const db = new Promise((ok, mal) => {
  const r = indexedDB.open("turnos-cosecha", 1);
  r.onupgradeneeded = () => r.result.createObjectStore("cola", { keyPath: "id" });
  r.onsuccess = () => ok(r.result);
  r.onerror = () => mal(r.error);
});
async function cola(modo, fn) {
  const d = await db;
  return new Promise((ok, mal) => {
    const tx = d.transaction("cola", modo);
    const req = fn(tx.objectStore("cola"));
    tx.oncomplete = () => ok(req && req.result);
    tx.onerror = () => mal(tx.error);
  });
}
const encolar = (m) => cola("readwrite", (s) => s.put(m));
const pendientes = () => cola("readonly", (s) => s.getAll());
const quitar = (id) => cola("readwrite", (s) => s.delete(id));

// ---------- API ----------
async function api(ruta, opciones = {}) {
  const r = await fetch(ruta, {
    ...opciones,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${TOKEN}`, ...(opciones.headers || {}) },
  });
  if (r.status === 401) { salir(); throw new Error("Sesión no válida"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Error ${r.status}`);
  return r.json();
}

// ---------- sesión ----------
async function entrar(token) {
  TOKEN = token;
  const yo = await api("/api/yo");
  ROL = yo.rol;
  localStorage.setItem("token", TOKEN);
  $("#login").hidden = true;
  $("#principal").hidden = false;
  $("#salir").hidden = false;
  $("#rol").textContent = ROL.replace("_", " ");
  await cargarCatalogo();
  fetch("/salud").then((r) => r.json()).then((s) => { $("#btn-cierre").hidden = s.modo !== "local"; }).catch(() => {});
  if (ROL === "analista") mostrar("ia");
}
function salir() {
  localStorage.removeItem("token");
  TOKEN = "";
  $("#principal").hidden = true;
  $("#login").hidden = false;
  $("#salir").hidden = true;
}

async function cargarCatalogo() {
  try {
    CATALOGO = await api("/api/catalogos");
    localStorage.setItem("catalogo", JSON.stringify(CATALOGO));
  } catch (e) { /* sin red: se usa el catálogo guardado */ }
  $("#frente").innerHTML = CATALOGO.frentes.map((f) => `<option value="${esc(f.id)}">${esc(f.nombre)}</option>`).join("");
  $("#lista-trabajadores").innerHTML = CATALOGO.trabajadores
    .map((t) => `<option value="${esc(t.codigo)}">${esc(t.nombre)} · ${esc(t.cargo)} · ${esc(t.frente_id)}</option>`).join("");
  const guardado = localStorage.getItem("frente");
  if (guardado) $("#frente").value = guardado;
}

// ---------- marcación ----------
function normalizarCodigo(v) {
  const t = v.trim().toUpperCase();
  const qr = CATALOGO.trabajadores.find((x) => x.qr === t);
  return qr ? qr.codigo : t;
}

function ubicacion(frente) {
  if ($("#simular-gps").checked || !navigator.geolocation) return Promise.resolve({ lat: frente.lat, lon: frente.lon });
  return new Promise((ok) => navigator.geolocation.getCurrentPosition(
    (p) => ok({ lat: p.coords.latitude, lon: p.coords.longitude }),
    () => ok({ lat: null, lon: null }),
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
  ));
}

async function marcar(tipo) {
  const codigo = normalizarCodigo($("#codigo").value);
  const frente = CATALOGO.frentes.find((f) => f.id === $("#frente").value);
  if (!codigo || !frente) return aviso("Seleccione frente y trabajador", true);
  localStorage.setItem("frente", frente.id);
  const pos = await ubicacion(frente);
  const m = { id: crypto.randomUUID(), codigo_trabajador: codigo, tipo, ts: new Date().toISOString(), frente_id: frente.id, ...pos, origen: "pwa" };
  await encolar(m);
  historial(m, "pendiente");
  $("#codigo").value = "";
  aviso(`${tipo === "entrada" ? "Entrada" : "Salida"} de ${codigo} guardada en el dispositivo`);
  sincronizar();
}

let sincronizando = false;
async function sincronizar() {
  const lista = await pendientes();
  $("#pendientes").textContent = `${lista.length} por sincronizar`;
  if (!lista.length || !navigator.onLine || sincronizando || !TOKEN) return;
  sincronizando = true;
  try {
    const { resultados } = await api("/api/marcaciones/lote", { method: "POST", body: JSON.stringify({ marcaciones: lista }) });
    for (const r of resultados) {
      if (r.resultado !== "error") await quitar(r.id);
      historial({ id: r.id }, r.resultado === "error" ? "error" : "enviada");
    }
    setTimeout(revisarEstados, 1500);
  } catch (e) {
    aviso(`Sin conexión con el servidor; se reintentará (${e.message})`, true);
  } finally {
    sincronizando = false;
    $("#pendientes").textContent = `${(await pendientes()).length} por sincronizar`;
  }
}

// historial local de las últimas marcaciones
const HIST = JSON.parse(localStorage.getItem("historial") || "[]");
function historial(m, estado) {
  const i = HIST.findIndex((h) => h.id === m.id);
  if (i >= 0) Object.assign(HIST[i], m.codigo_trabajador ? m : {}, { estado });
  else HIST.unshift({ ...m, estado });
  HIST.splice(15);
  localStorage.setItem("historial", JSON.stringify(HIST));
  pintarHistorial();
}
function pintarHistorial() {
  $("#ultimas").innerHTML = HIST.map((h) =>
    `<li><span><b>${esc(h.codigo_trabajador)}</b> · ${esc(h.tipo)} · ${hora(h.ts)}</span><span class="badge b-${esc(h.estado)}">${esc(h.estado)}</span></li>`
  ).join("") || '<li class="nota">Aún no hay marcaciones.</li>';
}
async function revisarEstados() {
  for (const h of HIST.filter((x) => x.estado === "enviada")) {
    try {
      const m = await api(`/api/marcaciones/${h.id}`);
      if (m.estado !== "recibida") historial(h, m.estado);
    } catch (e) { /* aún no */ }
  }
}

function aviso(t, error = false) {
  $("#msg-marcar").textContent = t;
  $("#msg-marcar").className = "mensaje" + (error ? " error" : "");
}

// lector QR con la API nativa BarcodeDetector (Chrome Android); si no existe, se digita el código
async function escanear() {
  if (!("BarcodeDetector" in window)) return aviso("Este navegador no lee QR; digite el código del carné", true);
  const video = $("#video");
  const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
  video.srcObject = stream; video.hidden = false; await video.play();
  const det = new BarcodeDetector({ formats: ["qr_code"] });
  const fin = () => { stream.getTracks().forEach((t) => t.stop()); video.hidden = true; };
  const t0 = Date.now();
  (async function bucle() {
    const cods = await det.detect(video).catch(() => []);
    if (cods.length) { $("#codigo").value = normalizarCodigo(cods[0].rawValue); fin(); return aviso("QR leído"); }
    if (Date.now() - t0 > 20000) { fin(); return aviso("No se detectó QR", true); }
    requestAnimationFrame(bucle);
  })();
}

// ---------- jornadas ----------
async function cargarJornadas() {
  const p = new URLSearchParams({ fecha: $("#f-fecha").value });
  if ($("#f-estado").value) p.set("estado", $("#f-estado").value);
  const js = await api(`/api/jornadas?${p}`);
  const tb = $("#tabla-jornadas tbody");
  tb.innerHTML = js.map((j) => {
    const hs = (j.hallazgos?.length ? j.hallazgos : j.hallazgos_entrada || [])
      .map((h) => `<div class="hallazgo">${esc(h.mensaje)} <code>${esc(h.regla)}</code></div>`).join("");
    const exp = j.explicacion_ia ? `<div class="explicacion">IA: ${esc(j.explicacion_ia)}</div>` : "";
    const acciones = ROL === "jefe_frente" && j.estado === "observado"
      ? `<button class="mini" data-d="aprobar" data-id="${esc(j.id)}">Aprobar</button> <button class="mini secundario" data-d="rechazar" data-id="${esc(j.id)}">Rechazar</button>` : "";
    return `<tr><td><b>${esc(j.codigo_trabajador)}</b><br><span class="nota">${esc(j.cargo)}</span></td><td>${esc(j.frente_id)}</td>
      <td>${hora(j.entrada_ts)}</td><td>${hora(j.salida_ts)}</td><td>${j.horas_trabajadas ?? "—"}</td>
      <td><span class="badge b-${esc(j.estado)}">${esc(j.estado)}</span></td><td>${hs}${exp}</td><td>${acciones}</td></tr>`;
  }).join("") || '<tr><td colspan="8" class="nota">Sin jornadas para la fecha.</td></tr>';
}

async function decidir(id, decision) {
  const comentario = prompt(`Comentario para ${decision}:`, "") ?? "";
  await api(`/api/jornadas/${id}/decision`, { method: "POST", body: JSON.stringify({ decision, comentario }) });
  cargarJornadas();
}

// ---------- alertas ----------
async function cargarAlertas() {
  const as = await api(`/api/alertas?fecha=${$("#a-fecha").value}`);
  $("#lista-alertas").innerHTML = as.map((a) =>
    `<li><span class="badge b-${esc(a.estado_registro)}">${esc(a.tipo)}</span> <b>${esc(a.codigo_trabajador)}</b> · ${esc(a.frente_id)} · ${hora(a.creada_en)}
     <div class="explicacion">${esc(a.explicacion_ia)} <span class="etiqueta-ia">(${esc(a.origen_explicacion)})</span></div></li>`
  ).join("") || '<li class="nota">Sin alertas pendientes.</li>';
}

// ---------- indicadores e IA ----------
async function cargarKpis() {
  const f = $("#k-fecha").value;
  const k = await api(`/api/kpis?fecha=${f}`);
  const pe = k.por_estado;
  const tarjetas = [
    ["Jornadas", k.jornadas_total], ["Válidas", pe.valido], ["Observadas", pe.observado], ["Aprobadas", pe.aprobado],
    ["Marcaciones rechazadas", k.marcaciones_rechazadas], ["Horas trabajadas", k.horas_trabajadas], ["Horas extra", k.horas_extra],
    ["Tasa de observación", `${(k.tasa_observacion * 100).toFixed(1)} %`], ["Anomalías (modelo)", k.anomalias_modelo],
  ];
  $("#kpis").innerHTML = tarjetas.map(([t, v]) => `<div class="kpi"><b>${esc(v)}</b><span>${esc(t)}</span></div>`).join("");
  try {
    const r = await api(`/api/resumenes/${f}`);
    $("#resumen").textContent = r.resumen;
    $("#origen-resumen").textContent = `(${r.origen_resumen})`;
  } catch (e) {
    $("#resumen").textContent = "Aún no se ha ejecutado el cierre diario de esta fecha.";
    $("#origen-resumen").textContent = "";
  }
}

async function preguntar(ev) {
  ev.preventDefault();
  const pregunta = $("#pregunta").value.trim();
  if (!pregunta) return;
  $("#respuesta").textContent = "Consultando…";
  try {
    const r = await api("/api/asistente", { method: "POST", body: JSON.stringify({ pregunta, fecha: $("#k-fecha").value }) });
    $("#respuesta").innerHTML = `${esc(r.texto)}<div class="etiqueta-ia">Origen: ${esc(r.origen)}</div>`;
  } catch (e) { $("#respuesta").textContent = e.message; }
}

// ---------- navegación ----------
function mostrar(tab) {
  document.querySelectorAll("nav button").forEach((b) => b.classList.toggle("activo", b.dataset.tab === tab));
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== `tab-${tab}`));
  const accion = { jornadas: cargarJornadas, alertas: cargarAlertas, ia: cargarKpis }[tab];
  if (accion) accion().catch((e) => alert(e.message));
}

function estadoRed() {
  $("#red").textContent = navigator.onLine ? "En línea" : "Sin señal";
  $("#red").classList.toggle("offline", !navigator.onLine);
  if (navigator.onLine) sincronizar();
}

document.addEventListener("DOMContentLoaded", () => {
  ["#f-fecha", "#a-fecha", "#k-fecha"].forEach((s) => ($(s).value = hoyISO()));
  $("#form-login").addEventListener("submit", (e) => {
    e.preventDefault();
    entrar($("#token").value.trim()).catch((err) => ($("#login-error").textContent = err.message));
  });
  $("#salir").addEventListener("click", salir);
  document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => mostrar(b.dataset.tab)));
  $("#btn-entrada").addEventListener("click", () => marcar("entrada"));
  $("#btn-salida").addEventListener("click", () => marcar("salida"));
  $("#btn-qr").addEventListener("click", () => escanear().catch((e) => aviso(e.message, true)));
  $("#btn-cargar").addEventListener("click", () => cargarJornadas().catch((e) => alert(e.message)));
  $("#btn-alertas").addEventListener("click", () => cargarAlertas().catch((e) => alert(e.message)));
  $("#btn-kpis").addEventListener("click", () => cargarKpis().catch((e) => alert(e.message)));
  $("#btn-cierre").addEventListener("click", async () => {
    const b = $("#btn-cierre");
    b.disabled = true;
    b.textContent = "Ejecutando cierre…";
    try {
      const r = await fetch("/local/reportes/tareas/cierre-diario", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fecha: $("#k-fecha").value }) });
      const c = await r.json();
      $("#msg-cierre").textContent = `Cierre ejecutado: ${c.jornadas_pagables} jornadas enviadas a nómina, ${c.jornadas_pendientes} pendientes por decidir.`;
      await cargarKpis();
    } catch (e) {
      $("#msg-cierre").textContent = `No se pudo ejecutar el cierre: ${e.message}`;
    } finally {
      b.disabled = false;
      b.textContent = "Ejecutar cierre diario (demo local)";
    }
  });
  $("#tabla-jornadas").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-d]");
    if (b) decidir(b.dataset.id, b.dataset.d).catch((err) => alert(err.message));
  });
  $("#form-ia").addEventListener("submit", preguntar);
  window.addEventListener("online", estadoRed);
  window.addEventListener("offline", estadoRed);
  estadoRed();
  pintarHistorial();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
  if (TOKEN) entrar(TOKEN).catch(() => salir());
  setInterval(sincronizar, 30000);
});
