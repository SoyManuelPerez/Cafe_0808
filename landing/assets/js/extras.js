/* Secciones interactivas: test del café ideal, guía de molienda y gráfico de altura */
import { PRODUCTOS, TAMANO_INICIAL } from "./config.js";
import { $, $$, esc, img } from "./util.js";
import { agregar } from "./carrito.js";

/* ---------------- Test ---------------- */
const PREGUNTAS = [
  { q: "¿Cómo tomas tu café normalmente?", o: [
    ["Con leche o con bastante azúcar", { blend: 2 }],
    ["Negro, sin nada", { chiroso: 2, bourbon: 1 }],
    ["Con un toque de panela o miel", { bourbon: 2, blend: 1 }] ] },
  { q: "¿Qué sabor te provoca más?", o: [
    ["Chocolate y panela", { blend: 3 }],
    ["Frutas y caramelo", { bourbon: 3 }],
    ["Flores, cítricos y miel", { chiroso: 3 }] ] },
  { q: "¿Qué tanta acidez te gusta?", o: [
    ["Muy poca, suave y redondo", { bourbon: 2 }],
    ["Equilibrada", { blend: 2, chiroso: 1 }],
    ["Viva y fresca", { chiroso: 2 }] ] }
];
const MOTIVO = {
  bourbon: "Dulce y suave, con muy poca acidez. Su proceso honey le da un cuerpo redondo con notas de caramelo y panela. Si te gusta el café amable, empieza por aquí.",
  blend: "Achocolatado y redondo. Es el café de todos los días y el que mejor se lleva con la leche.",
  chiroso: "Floral y cítrico, con dulzor a miel. Es el de mayor altura de los tres (2.090 m) y el más expresivo. Mejor si lo tomas negro."
};

function iniciarTest() {
  const caja = $("#quizCaja");
  let paso = 0, puntos;

  const inicio = () => { paso = 0; puntos = { bourbon: 0, blend: 0, chiroso: 0 }; pregunta(); };
  const pregunta = () => {
    const q = PREGUNTAS[paso];
    caja.innerHTML = `<div class="progreso"><i style="width:${(paso / PREGUNTAS.length) * 100}%"></i></div>
      <p class="quiz-paso">Pregunta ${paso + 1} de ${PREGUNTAS.length}</p>
      <p class="quiz-q">${esc(q.q)}</p>
      <div class="quiz-ops">${q.o.map((o, i) => `<button type="button" data-i="${i}">${esc(o[0])}</button>`).join("")}</div>`;
    requestAnimationFrame(() => { $(".progreso i", caja).style.width = ((paso + 1) / PREGUNTAS.length) * 100 + "%"; });
  };
  const resultado = () => {
    const id = Object.entries(puntos).sort((a, b) => b[1] - a[1])[0][0];
    const p = PRODUCTOS.find(x => x.id === id);
    caja.innerHTML = `<div class="quiz-res">
      <img src="${img(p.img, { sm: true })}" alt="Bolsa de ${esc(p.nombre)}" width="140" height="187">
      <div>
        <p class="quiz-paso">Tu café es</p>
        <h3>${esc(p.nombre)}</h3>
        <p>${esc(MOTIVO[id])}</p>
        <div class="acciones">
          <button class="btn btn-ambar" type="button" data-agregar="${id}">Agregar ${TAMANO_INICIAL} g al pedido</button>
          <button class="btn btn-linea" type="button" data-repetir>Probar otro</button>
        </div>
        <p class="quiz-nota">Se agrega en grano y tostión media. Puedes cambiar la molienda en tu pedido.</p>
      </div>
    </div>`;
  };

  caja.addEventListener("click", e => {
    const op = e.target.closest(".quiz-ops button");
    if (op) {
      const pts = PREGUNTAS[paso].o[+op.dataset.i][1];
      for (const k in pts) puntos[k] += pts[k];
      paso++;
      paso < PREGUNTAS.length ? pregunta() : resultado();
      $("button", caja)?.focus();
      return;
    }
    if (e.target.closest("[data-repetir]")) { inicio(); return; }
    const add = e.target.closest("[data-agregar]");
    if (add) agregar({ id: add.dataset.agregar, tamano: TAMANO_INICIAL, molienda: "Grano", tostion: "Medio", cant: 1 });
  });
  inicio();
}

/* ---------------- Molienda ---------------- */
const METODOS = [
  { n: "Prensa francesa", g: "Gruesa", t: "4 minutos de infusión", tip: "Cuerpo pleno y textura sedosa. Con molienda gruesa no queda turbio ni amargo. Va muy bien con el Blend.", size: 9 },
  { n: "V60 / Chemex", g: "Media", t: "2 a 3 minutos", tip: "Resalta lo floral y lo frutal. Es el método ideal para el Chiroso y el Bourbon Rosado.", size: 6 },
  { n: "Cafetera de goteo", g: "Media", t: "5 a 6 minutos", tip: "Práctica para varias tazas. La molienda media da un café equilibrado. Cualquiera de los tres funciona.", size: 6 },
  { n: "Moka / greca", g: "Fina", t: "4 a 5 minutos", tip: "Intenso y concentrado. Fina, sin llegar a polvo, para que no amargue. Prueba el Blend.", size: 3.5 },
  { n: "Espresso", g: "Fina", t: "25 a 30 segundos", tip: "Pide molienda fina y ajusta según tu máquina. El Blend se lleva muy bien con leche.", size: 2.6 },
  { n: "Sin molino", g: "Media", t: "lo recibes molido y listo", tip: "Marca molienda media: sirve para goteo, V60 y la mayoría de cafeteras caseras.", size: 6 },
  { n: "Con molino", g: "Grano", t: "Muélelo justo antes de preparar", tip: "Si tienes molino, pídelo en grano: el aroma y el sabor se conservan mucho más tiempo.", size: 20 }
];

function iniciarMolienda() {
  const cont = $("#metodos"), polvo = $("#polvo");
  cont.innerHTML = METODOS.map((m, i) => `<button type="button" role="tab" aria-selected="${i === 0}" data-i="${i}">${esc(m.n)}</button>`).join("");
  const piezas = Array.from({ length: 70 }, () => {
    const el = document.createElement("i");
    polvo.appendChild(el);
    return { el, rx: Math.random(), ry: Math.random(), v: .6 + Math.random() * .8 };
  });
  const pintar = i => {
    const m = METODOS[i];
    $("#mNombre").textContent = m.g === "Grano" ? "Pídelo en grano" : "Molienda " + m.g.toLowerCase();
    $("#mTiempo").textContent = `${m.n}: ${m.t}`;
    $("#mTip").textContent = m.tip;
    const W = polvo.clientWidth, H = polvo.clientHeight;
    const cuantos = Math.min(70, Math.round(900 / (m.size * m.size)) + 6);
    piezas.forEach((p, k) => {
      const s = m.size * p.v;
      Object.assign(p.el.style, {
        display: k < cuantos ? "block" : "none", width: s + "px", height: (m.g === "Grano" ? s * 1.45 : s) + "px",
        left: p.rx * (W - s) + "px", top: p.ry * (H - s) + "px", transform: `rotate(${p.rx * 360}deg)`,
        background: m.g === "Grano" ? "linear-gradient(100deg,transparent 44%,#3a2200 44%,#3a2200 56%,transparent 56%),#f5a70b" : "#6b3f1d"
      });
    });
  };
  cont.addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b) return;
    $$("button", cont).forEach(x => x.setAttribute("aria-selected", x === b));
    pintar(+b.dataset.i);
  });
  let tRes;
  addEventListener("resize", () => {
    clearTimeout(tRes);
    tRes = setTimeout(() => pintar(+$('[aria-selected="true"]', cont).dataset.i), 150);
  });
  pintar(0);
}

/* ---------------- Gráfico de altura ---------------- */
function iniciarAltura() {
  const svg = $("#montana");
  new IntersectionObserver((es, io) => es.forEach(e => {
    if (e.isIntersecting) { svg.classList.add("visible"); io.disconnect(); }
  }), { threshold: .3 }).observe(svg);
}

export function iniciarExtras() {
  iniciarTest();
  iniciarMolienda();
  iniciarAltura();
}
