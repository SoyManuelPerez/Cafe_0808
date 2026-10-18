/* Arranque de la landing */
import { INSTAGRAM, TIKTOK } from "./config.js";
import { $, $$, moneda } from "./util.js";
import { precioMinimo, sincronizarPrecios } from "./precios.js";
import { iniciarCarrito, pintar as pintarCarrito } from "./carrito.js";
import { iniciarFichas, actualizarPreciosFichas } from "./fichas.js";
import { iniciarExtras } from "./extras.js";

document.documentElement.classList.add("js");

function iniciarBarra() {
  const barra = $("#barra"), nav = $("#nav"), btn = $("#menuBtn");
  const alHacerScroll = () => barra.classList.toggle("solida", scrollY > 30);
  addEventListener("scroll", alHacerScroll, { passive: true });
  alHacerScroll();
  const cerrarMenu = () => { nav.classList.remove("abierta"); btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", () => btn.setAttribute("aria-expanded", nav.classList.toggle("abierta")));
  $$("a", nav).forEach(a => a.addEventListener("click", cerrarMenu));
}

function iniciarEnlaces() {
  for (const id of ["lnkInstagram", "pieInstagram"]) $("#" + id).href = INSTAGRAM;
  for (const id of ["lnkTiktok", "pieTiktok"]) $("#" + id).href = TIKTOK;
  $("#anio").textContent = new Date().getFullYear();
  const frases = ["Café de especialidad", "Cosecha selecta", "Gigante, Huila", "Urrao, Antioquia", "Ciudad Bolívar", "100% colombiano", "Tostado en tandas pequeñas"];
  $("#cinta").innerHTML = [...frases, ...frases].map(t => `<span>${t}</span>`).join("");
}

function pintarPrecios() {
  $("#precioDesde").textContent = moneda(precioMinimo());
  actualizarPreciosFichas();
  pintarCarrito();
}

iniciarBarra();
iniciarEnlaces();
iniciarFichas();
iniciarCarrito();
iniciarExtras();
pintarPrecios();

// Precios vigentes del sistema (si hay cambios, se actualizan fichas y pedido)
sincronizarPrecios().then(cambio => { if (cambio) pintarPrecios(); });
