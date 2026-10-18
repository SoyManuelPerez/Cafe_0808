/* Pedido: agregar, editar (tamaño, molienda, tostión, cantidad), quitar con deshacer
   y enviar por WhatsApp. Se guarda en este navegador para no perderlo al recargar. */
import { PRODUCTOS, TAMANOS, MOLIENDAS, TOSTIONES, MAX_POR_LINEA } from "./config.js";
import { $, aviso, esc, img, local, moneda, waURL } from "./util.js";
import { precioDe } from "./precios.js";

const CLAVE = "pedido_0808_v3";
const CLAVE_DATOS = "pedido_0808_datos";
let lineas = limpiar(local.leer(CLAVE, []));
let datos = local.leer(CLAVE_DATOS, { nombre: "", ciudad: "" });
let ultimoFoco = null;

function limpiar(lista) {
  // Descarta líneas viejas o alteradas que no correspondan a un producto/opción válida
  return (Array.isArray(lista) ? lista : []).filter(l =>
    PRODUCTOS.some(p => p.id === l.id) && TAMANOS.includes(l.tamano) &&
    MOLIENDAS.includes(l.molienda) && TOSTIONES.includes(l.tostion) &&
    Number.isInteger(l.cant) && l.cant > 0
  ).map(l => ({ ...l, cant: Math.min(l.cant, MAX_POR_LINEA) }));
}

const igual = (a, b) => a.id === b.id && a.tamano === b.tamano && a.molienda === b.molienda && a.tostion === b.tostion;
const producto = id => PRODUCTOS.find(p => p.id === id);
export const unidades = () => lineas.reduce((a, l) => a + l.cant, 0);
const total = () => lineas.reduce((a, l) => a + precioDe(l.id, l.tamano) * l.cant, 0);

function guardar() {
  local.guardar(CLAVE, lineas);
  pintar();
}

export function agregar(item) {
  const ya = lineas.find(l => igual(l, item));
  if (ya) ya.cant = Math.min(MAX_POR_LINEA, ya.cant + item.cant);
  else lineas.push({ ...item });
  guardar();
  const num = $("#numCarrito");
  num.classList.remove("salta"); void num.offsetWidth; num.classList.add("salta");
  aviso(`${producto(item.id).nombre} ${item.tamano} g agregado`, { texto: "Ver pedido", fn: abrir });
}

function quitar(i) {
  const [quitada] = lineas.splice(i, 1);
  guardar();
  aviso(`Quitaste ${producto(quitada.id).nombre}`, {
    texto: "Deshacer",
    fn: () => { lineas.splice(Math.min(i, lineas.length), 0, quitada); guardar(); }
  });
}

function editar(i, campo, valor) {
  const l = lineas[i];
  if (!l) return;
  if (campo === "cant") l.cant = Math.max(1, Math.min(MAX_POR_LINEA, valor));
  else l[campo] = campo === "tamano" ? Number(valor) : valor;
  // Si al editar queda igual a otra línea, se juntan
  const otra = lineas.findIndex((x, j) => j !== i && igual(x, l));
  if (otra !== -1) {
    lineas[otra].cant = Math.min(MAX_POR_LINEA, lineas[otra].cant + l.cant);
    lineas.splice(i, 1);
  }
  guardar();
}

function mensaje() {
  if (!lineas.length) return "Hola 0808 Café ☕ Quiero conocer más sobre sus cafés de especialidad.";
  const filas = lineas.map(l => {
    const p = producto(l.id);
    return `• ${l.cant} x ${p.nombre} ${l.tamano} g — Molienda: ${l.molienda}, Tostión: ${l.tostion} — ${moneda(precioDe(l.id, l.tamano) * l.cant)}`;
  });
  let txt = "Hola 0808 Café ☕ Quiero hacer este pedido:\n\n" + filas.join("\n") + `\n\nTotal: ${moneda(total())} (sin envío)`;
  const nombre = (datos.nombre || "").trim(), ciudad = (datos.ciudad || "").trim();
  if (nombre) txt += `\nNombre: ${nombre}`;
  if (ciudad) txt += `\nCiudad / barrio: ${ciudad}`;
  return txt + "\n\n¿Cómo coordinamos el pago y el envío?";
}

const opciones = (lista, actual, fmt = v => v) =>
  lista.map(v => `<option value="${esc(v)}"${v === actual ? " selected" : ""}>${esc(fmt(v))}</option>`).join("");

export function pintar() {
  const n = unidades();
  $("#numCarrito").textContent = n;
  const cuenta = $("#granoCuenta");
  cuenta.textContent = n;
  cuenta.classList.toggle("on", n > 0);
  const grano = $("#grano");
  grano.setAttribute("aria-label", n ? `Ver tu pedido (${n})` : "Escribir por WhatsApp");
  grano.href = waURL(mensaje());
  $("#btnContacto").href = waURL(lineas.length ? mensaje() : "Hola 0808 Café ☕ Tengo una pregunta sobre sus cafés.");

  const cuerpo = $("#carritoCuerpo");
  $("#carritoPie").hidden = !lineas.length;
  if (!lineas.length) {
    cuerpo.innerHTML = `<div class="vacio"><p>Tu pedido está vacío. Elige un café, marca molienda y tostión, y agrégalo.</p>
      <a class="btn btn-tinta" href="#cafes" data-cerrar>Ver cafés</a></div>`;
    return;
  }

  cuerpo.innerHTML = lineas.map((l, i) => {
    const p = producto(l.id);
    return `<article class="linea" data-i="${i}">
      <img src="${img(p.img, { sm: true })}" alt="" width="64" height="85" loading="lazy">
      <div>
        <div class="linea-top"><h3>${esc(p.nombre)}</h3><span class="linea-precio">${moneda(precioDe(l.id, l.tamano) * l.cant)}</span></div>
        <div class="linea-ops">
          <label>Tamaño<select data-campo="tamano" aria-label="Tamaño de ${esc(p.nombre)}">${opciones(TAMANOS, l.tamano, t => `${t} g`)}</select></label>
          <label>Molienda<select data-campo="molienda" aria-label="Molienda de ${esc(p.nombre)}">${opciones(MOLIENDAS, l.molienda)}</select></label>
          <label>Tostión<select data-campo="tostion" aria-label="Tostión de ${esc(p.nombre)}">${opciones(TOSTIONES, l.tostion)}</select></label>
        </div>
        <div class="linea-pie">
          <div class="paso" role="group" aria-label="Cantidad de ${esc(p.nombre)}">
            <button type="button" data-d="-1" aria-label="Quitar una">−</button>
            <output aria-live="polite">${l.cant}</output>
            <button type="button" data-d="1" aria-label="Agregar una">+</button>
          </div>
          <button type="button" class="quitar" data-quitar>Quitar</button>
        </div>
      </div>
    </article>`;
  }).join("") + `<div class="carrito-datos">
      <label>Tu nombre (opcional)<input id="pedNombre" maxlength="60" autocomplete="name" value="${esc(datos.nombre)}"></label>
      <label>Ciudad o barrio (opcional)<input id="pedCiudad" maxlength="80" autocomplete="address-level2" value="${esc(datos.ciudad)}"></label>
    </div>`;

  $("#carritoTotal").textContent = moneda(total());
  $("#enviarPedido").href = waURL(mensaje());
}

export function abrir() {
  ultimoFoco = document.activeElement;
  $("#aviso").classList.remove("on");
  $("#carrito").classList.add("abierto");
  $("#carrito").setAttribute("aria-hidden", "false");
  $("#velo").classList.add("abierto");
  document.body.classList.add("carrito-abierto");
  $("#cerrarCarrito").focus();
}

export function cerrar() {
  $("#carrito").classList.remove("abierto");
  $("#carrito").setAttribute("aria-hidden", "true");
  $("#velo").classList.remove("abierto");
  document.body.classList.remove("carrito-abierto");
  if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
}

export function iniciarCarrito() {
  const cuerpo = $("#carritoCuerpo");
  cuerpo.addEventListener("click", e => {
    if (e.target.closest("[data-cerrar]")) { cerrar(); return; }
    const art = e.target.closest(".linea");
    if (!art) return;
    const i = +art.dataset.i;
    const paso = e.target.closest("[data-d]");
    if (paso) {
      const nueva = lineas[i].cant + Number(paso.dataset.d);
      if (nueva < 1) quitar(i); else editar(i, "cant", nueva);
      return;
    }
    if (e.target.closest("[data-quitar]")) quitar(i);
  });
  cuerpo.addEventListener("change", e => {
    const sel = e.target.closest("select[data-campo]");
    if (!sel) return;
    const i = +sel.closest(".linea").dataset.i, campo = sel.dataset.campo, antes = lineas.length;
    editar(i, campo, sel.value);
    // Mantiene el foco en el mismo selector tras repintar (si la línea no se fusionó)
    if (lineas.length === antes) $(`.linea[data-i="${i}"] select[data-campo="${campo}"]`)?.focus();
  });
  cuerpo.addEventListener("input", e => {
    if (e.target.id === "pedNombre") datos.nombre = e.target.value;
    else if (e.target.id === "pedCiudad") datos.ciudad = e.target.value;
    else return;
    local.guardar(CLAVE_DATOS, datos);
    const url = waURL(mensaje());
    $("#enviarPedido").href = url;
    $("#grano").href = url;
  });

  $("#abrirCarrito").addEventListener("click", abrir);
  $("#cerrarCarrito").addEventListener("click", cerrar);
  $("#velo").addEventListener("click", cerrar);
  $("#vaciarCarrito").addEventListener("click", () => {
    const copia = lineas;
    lineas = [];
    guardar();
    aviso("Vaciaste el pedido", { texto: "Deshacer", fn: () => { lineas = copia; guardar(); } });
  });
  // El grano abre el pedido si hay productos; si no, va directo a WhatsApp
  $("#grano").addEventListener("click", e => {
    if (lineas.length) { e.preventDefault(); abrir(); }
  });
  addEventListener("keydown", e => {
    if (e.key === "Escape" && $("#carrito").classList.contains("abierto")) cerrar();
  });
  // Si el pedido cambia en otra pestaña, se sincroniza
  addEventListener("storage", e => {
    if (e.key === CLAVE) { lineas = limpiar(local.leer(CLAVE, [])); pintar(); }
  });
  pintar();
}
