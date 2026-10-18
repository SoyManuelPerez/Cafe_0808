/* Fichas de producto con forma de etiqueta: el cliente marca molienda y tostión
   en los mismos círculos que trae la etiqueta impresa. */
import { PRODUCTOS, TAMANOS, TAMANO_INICIAL, MOLIENDAS, TOSTIONES, MAX_POR_LINEA } from "./config.js";
import { $, $$, esc, img } from "./util.js";
import { precioDe } from "./precios.js";
import { agregar } from "./carrito.js";

const circulos = (grupo, lista, marcado, id, dosCol) => `
  <fieldset class="circulos${dosCol ? " dos-col" : ""}">
    <legend>${grupo === "molienda" ? "Molienda" : "Tostión"}</legend>
    ${lista.map(v => `<label class="circulo"><input type="radio" name="${grupo}-${id}" value="${esc(v)}"${v === marcado ? " checked" : ""}><i></i>${esc(v)}</label>`).join("")}
  </fieldset>`;

function ficha(p) {
  const nombreCompleto = p.subtitulo ? `${p.nombre} ${p.subtitulo}` : p.nombre;
  return `<article class="ficha" data-id="${p.id}" aria-labelledby="t-${p.id}">
    <figure class="ficha-foto" tabindex="0" role="button" aria-label="Ampliar foto de ${esc(nombreCompleto)}" data-zoom="${p.id}">
      <picture>
        <source srcset="${img(p.img, { sm: true })} 448w, ${img(p.img)} 896w" sizes="(max-width: 860px) 90vw, 42vw" type="image/webp">
        <img src="/assets/img/${p.img}.jpg" alt="Bolsa negra de café 0808 ${esc(nombreCompleto)} con etiqueta dorada" width="896" height="1195" loading="lazy" decoding="async">
      </picture>
      <span class="lupa">Ver etiqueta</span>
    </figure>

    <div class="etiqueta">
      <div class="et-fila et-top">
        <div class="et-campo"><small>Origen</small><b>${esc(p.origen)}</b></div>
        <div class="et-campo"><small>Proceso</small><b>${esc(p.proceso)}</b><span>${esc(p.acidez)}</span></div>
      </div>
      <div class="et-variedad">
        <div class="et-campo"><small>Variedad</small></div>
        <h3 id="t-${p.id}">${esc(p.nombre)}</h3>
        ${p.subtitulo ? `<p>${esc(p.subtitulo)}</p>` : ""}
      </div>
      <div class="et-fila et-detalle">
        <div>${circulos("molienda", MOLIENDAS, "Grano", p.id, true)}</div>
        <div class="et-campo"><small>Aroma</small><span>${esc(p.aroma)}</span><small class="mt">Sabor</small><span>${esc(p.sabor)}</span></div>
        <div class="et-campo"><small>msnm</small><b class="et-msnm">${p.msnm.toLocaleString("es-CO")}</b></div>
        <div>${circulos("tostion", TOSTIONES, "Medio", p.id, false)}</div>
      </div>
      <div class="et-pie">
        <div class="tamanos" role="radiogroup" aria-label="Tamaño de bolsa">
          ${TAMANOS.map(t => `<label><input type="radio" name="tamano-${p.id}" value="${t}"${t === TAMANO_INICIAL ? " checked" : ""}><span>${t} g</span></label>`).join("")}
        </div>
        <div class="precio" aria-live="polite"><strong data-precio>${"$" + precioDe(p.id, TAMANO_INICIAL).toLocaleString("es-CO")}</strong><small data-por>bolsa de ${TAMANO_INICIAL} g</small></div>
        <div class="et-acciones">
          <div class="paso" role="group" aria-label="Cantidad">
            <button type="button" data-d="-1" aria-label="Una menos">−</button>
            <output data-cant>1</output>
            <button type="button" data-d="1" aria-label="Una más">+</button>
          </div>
          <button type="button" class="btn btn-tinta" data-agregar>Agregar al pedido</button>
        </div>
      </div>
    </div>
  </article>`;
}

const valor = (art, nombre) => $(`input[name="${nombre}-${art.dataset.id}"]:checked`, art)?.value;

export function actualizarPreciosFichas() {
  $$(".ficha").forEach(art => {
    const t = Number(valor(art, "tamano"));
    $("[data-precio]", art).textContent = "$" + precioDe(art.dataset.id, t).toLocaleString("es-CO");
    $("[data-por]", art).textContent = `bolsa de ${t} g`;
  });
}

export function iniciarFichas() {
  const cont = $("#fichas");
  cont.innerHTML = PRODUCTOS.map(ficha).join("");

  cont.addEventListener("change", e => {
    if (e.target.name?.startsWith("tamano-")) actualizarPreciosFichas();
  });

  cont.addEventListener("click", e => {
    const art = e.target.closest(".ficha");
    if (!art) return;
    const out = $("[data-cant]", art);
    const paso = e.target.closest("[data-d]");
    if (paso) {
      out.textContent = Math.max(1, Math.min(MAX_POR_LINEA, Number(out.textContent) + Number(paso.dataset.d)));
      return;
    }
    if (e.target.closest("[data-agregar]")) {
      agregar({
        id: art.dataset.id,
        tamano: Number(valor(art, "tamano")),
        molienda: valor(art, "molienda"),
        tostion: valor(art, "tostion"),
        cant: Number(out.textContent)
      });
      out.textContent = "1";
    }
  });

  // Foto ampliada
  const modal = $("#modal");
  let foco = null;
  const abrirFoto = id => {
    const p = PRODUCTOS.find(x => x.id === id);
    foco = document.activeElement;
    $("#modalImg").src = `/assets/img/${p.img}.webp`;
    $("#modalImg").alt = `Etiqueta de ${p.nombre}`;
    modal.classList.add("abierto");
    $("#modalCerrar").focus();
  };
  const cerrarFoto = () => { modal.classList.remove("abierto"); foco?.focus(); };
  cont.addEventListener("click", e => { const z = e.target.closest("[data-zoom]"); if (z) abrirFoto(z.dataset.zoom); });
  cont.addEventListener("keydown", e => {
    if ((e.key === "Enter" || e.key === " ") && e.target.dataset.zoom) { e.preventDefault(); abrirFoto(e.target.dataset.zoom); }
  });
  modal.addEventListener("click", e => { if (e.target === modal || e.target.closest("#modalCerrar")) cerrarFoto(); });
  addEventListener("keydown", e => { if (e.key === "Escape" && modal.classList.contains("abierto")) cerrarFoto(); });

  // Las fichas aparecen al llegar a ellas
  const io = new IntersectionObserver(es => es.forEach(en => {
    if (en.isIntersecting) { en.target.classList.add("visible"); io.unobserve(en.target); }
  }), { threshold: .12 });
  $$(".ficha").forEach(f => io.observe(f));
}
