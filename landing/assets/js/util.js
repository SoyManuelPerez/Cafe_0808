/* Utilidades compartidas */
import { WHATSAPP } from "./config.js";

export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];
export const reducido = matchMedia("(prefers-reduced-motion: reduce)").matches;

export const moneda = n => "$" + Math.round(n || 0).toLocaleString("es-CO");
export const waURL = txt => `https://wa.me/${WHATSAPP}?text=${encodeURIComponent(txt)}`;

export function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function img(nombre, { sm = false } = {}) {
  return `/assets/img/${nombre}${sm ? "-sm" : ""}.webp`;
}

// Guardado local seguro: si el navegador lo bloquea, la página sigue funcionando.
export const local = {
  leer(clave, defecto) {
    try { const v = localStorage.getItem(clave); return v ? JSON.parse(v) : defecto; } catch (_) { return defecto; }
  },
  guardar(clave, valor) {
    try { localStorage.setItem(clave, JSON.stringify(valor)); } catch (_) { /* sin almacenamiento */ }
  }
};

let tAviso;
export function aviso(texto, accion) {
  const caja = $("#aviso");
  $("#avisoTxt").textContent = texto;
  caja.querySelector("button")?.remove();
  if (accion) {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = accion.texto;
    b.addEventListener("click", () => { accion.fn(); caja.classList.remove("on"); });
    caja.appendChild(b);
  }
  caja.classList.add("on");
  clearTimeout(tAviso);
  tAviso = setTimeout(() => caja.classList.remove("on"), accion ? 5000 : 2600);
}
