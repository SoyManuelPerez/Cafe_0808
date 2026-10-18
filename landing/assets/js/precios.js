/* Precios: toma los del sistema (si existen) y si no, los de config.js */
import { PRODUCTOS, TAMANOS } from "./config.js";

const normal = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

export function precioDe(id, tamano) {
  const p = PRODUCTOS.find(x => x.id === id);
  return p ? Number(p.precios[tamano] || 0) : 0;
}

export function precioMinimo() {
  const todos = PRODUCTOS.flatMap(p => TAMANOS.map(t => p.precios[t]).filter(Boolean));
  return todos.length ? Math.min(...todos) : 0;
}

/** Pide los precios vigentes al sistema. Devuelve true si cambió alguno. */
export async function sincronizarPrecios() {
  try {
    const res = await fetch("/api/public/precios", { headers: { Accept: "application/json" } });
    if (!res.ok) return false;
    const lista = await res.json();
    if (!Array.isArray(lista)) return false;
    let cambio = false;
    for (const p of PRODUCTOS) {
      for (const t of TAMANOS) {
        const encontrado = lista.find(x => normal(x.nombre).includes(p.clave) && Number(x.gramaje) === t && x.precio > 0);
        if (encontrado && encontrado.precio !== p.precios[t]) {
          p.precios[t] = encontrado.precio;
          cambio = true;
        }
      }
    }
    return cambio;
  } catch (_) {
    return false; // sin conexión con el sistema: se quedan los precios de config.js
  }
}
