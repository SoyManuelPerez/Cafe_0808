/* Vista previa, envío por WhatsApp y descarga de facturas/pedidos en PDF.
   El PDF se dibuja con PDF.js en alta resolución para que se lea nítido al hacer zoom,
   en computador, Android y iPhone (Safari no muestra PDF incrustados en una ventana). */

// PDF.js 3.11.174 servido desde el propio sitio (static/sistema/vendor/pdfjs): no depende de internet externo.
const PDFJS_BASE = '/static/sistema/vendor/pdfjs';
const PIXELES_MIN = 2000;     // ancho mínimo en píxeles con que se dibuja cada página
const PIXELES_MAX = 3000;     // tope para no gastar demasiada memoria en celulares
const ZOOM_PASOS = [1, 1.5, 2, 3];
let _pdfjsPromesa = null;
let endpointPdfActual = '';
let tituloPdfActual = '';
let zoomPdf = 1;
let renderPdfActual = null;   // promesa del dibujo en curso

function cargarPdfJs() {
    if (window.pdfjsLib) return Promise.resolve(window.pdfjsLib);
    if (_pdfjsPromesa) return _pdfjsPromesa;
    _pdfjsPromesa = new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = `${PDFJS_BASE}/pdf.min.js`;
        s.onload = () => {
            const lib = window.pdfjsLib;
            if (!lib) return reject(new Error('PDF.js no cargó'));
            lib.GlobalWorkerOptions.workerSrc = `${PDFJS_BASE}/pdf.worker.min.js`;
            resolve(lib);
        };
        s.onerror = () => { _pdfjsPromesa = null; reject(new Error('No se pudo cargar el visor de PDF')); };
        document.head.appendChild(s);
    });
    return _pdfjsPromesa;
}

const esCelular = () => /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

async function dibujarPdf(blob, contenedor) {
    const lib = await cargarPdfJs();
    const doc = await lib.getDocument({ data: new Uint8Array(await blob.arrayBuffer()), isEvalSupported: false }).promise;
    const hojas = document.createElement('div');
    hojas.className = 'pdf-hojas';
    const anchoPantalla = Math.max(280, contenedor.clientWidth - 24);
    const dpr = window.devicePixelRatio || 1;
    // Se dibuja con suficientes píxeles para ampliar hasta 3x sin que se pixele.
    const objetivo = Math.min(PIXELES_MAX, Math.max(PIXELES_MIN, anchoPantalla * dpr * 2.5));

    contenedor.innerHTML = '';
    contenedor.appendChild(hojas);
    for (let n = 1; n <= doc.numPages; n++) {
        const pagina = await doc.getPage(n);
        const base = pagina.getViewport({ scale: 1 });
        const vista = pagina.getViewport({ scale: objetivo / base.width });
        const canvas = document.createElement('canvas');
        canvas.className = 'pdf-pagina';
        canvas.width = Math.floor(vista.width);
        canvas.height = Math.floor(vista.height);
        canvas.setAttribute('role', 'img');
        canvas.setAttribute('aria-label', `Página ${n} de ${doc.numPages}`);
        hojas.appendChild(canvas);
        await pagina.render({ canvasContext: canvas.getContext('2d'), viewport: vista }).promise;
    }
    aplicarZoomPdf(1);
}

function aplicarZoomPdf(valor) {
    zoomPdf = valor;
    const hojas = document.querySelector('#modal-body-pdf .pdf-hojas');
    if (hojas) hojas.style.width = `${valor * 100}%`;
    const etiqueta = document.getElementById('pdf-zoom-valor');
    if (etiqueta) etiqueta.textContent = `${Math.round(valor * 100)}%`;
    document.getElementById('pdf-zoom-menos')?.toggleAttribute('disabled', valor <= ZOOM_PASOS[0]);
    document.getElementById('pdf-zoom-mas')?.toggleAttribute('disabled', valor >= ZOOM_PASOS[ZOOM_PASOS.length - 1]);
}

function cambiarZoomPdf(direccion) {
    const i = ZOOM_PASOS.indexOf(zoomPdf);
    const sig = ZOOM_PASOS[Math.max(0, Math.min(ZOOM_PASOS.length - 1, (i === -1 ? 0 : i) + direccion))];
    aplicarZoomPdf(sig);
}

async function abrirModalPdf(endpointUrl, tituloModal, filenameDescarga) {
    const container = document.getElementById('modal-body-pdf');
    document.getElementById('modal-titulo-pdf').textContent = '📄 ' + tituloModal;
    container.classList.add('pdf-visor');
    container.innerHTML = '<p class="pdf-estado">Cargando vista previa…</p>';
    document.getElementById('modal-factura').style.display = 'flex';
    nombrePdfDescarga = filenameDescarga || 'Documento.pdf';
    endpointPdfActual = endpointUrl;
    tituloPdfActual = tituloModal;
    aplicarZoomPdf(1);

    let blob;
    try {
        const res = await fetch(endpointUrl);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `No se pudo generar el documento (error ${res.status}).`);
        }
        blob = await res.blob();
        blobPdfActual = blob;
        urlPdfActual = URL.createObjectURL(blob);
    } catch (err) {
        container.innerHTML = `<p class="pdf-estado pdf-error">${esc(err.message)}</p>`;
        return;
    }

    try {
        renderPdfActual = dibujarPdf(blob, container);
        await renderPdfActual;
    } catch (err) {
        console.error('Vista previa con PDF.js falló:', err);
        // Respaldo: visor del navegador. Si tampoco puede, quedan los botones de abrir y descargar.
        container.innerHTML = `<iframe class="pdf-iframe" src="${urlPdfActual}" title="${esc(tituloModal)}"></iframe>
            <p class="pdf-estado">Si no ves el documento, usa <strong>Abrir PDF</strong> o <strong>Descargar</strong>.</p>`;
    }
}

/* ---------------- Enviar por WhatsApp como imagen ----------------
   Ningún navegador puede abrir el chat de una persona con una imagen ya adjunta
   (WhatsApp solo acepta texto en ese enlace). Por eso:
     1) se copia una imagen HD de la factura,
     2) se abre directamente el chat del cliente,
     3) en el chat se mantiene presionado y se elige "Pegar". */

let imagenFacturaBlob = null;
let contactoFactura = null;

// Une las páginas dibujadas en una sola imagen PNG y recorta el blanco sobrante de abajo.
async function generarImagenFactura() {
    // Si la factura aún se está dibujando, se espera a que termine (si no, saldría en blanco).
    if (renderPdfActual) await renderPdfActual.catch(() => {});
    let paginas = [...document.querySelectorAll('#modal-body-pdf canvas.pdf-pagina')];
    if (!paginas.length && blobPdfActual) {
        const oculto = document.createElement('div');
        oculto.style.cssText = 'position:fixed;left:-9999px;top:0;width:800px';
        document.body.appendChild(oculto);
        try { await dibujarPdf(blobPdfActual, oculto); paginas = [...oculto.querySelectorAll('canvas')]; }
        finally { setTimeout(() => oculto.remove(), 0); }
    }
    if (!paginas.length) throw new Error('No se pudo preparar la imagen de la factura.');

    const recortes = paginas.map(c => ({ c, alto: altoConContenido(c) }));
    const ancho = paginas[0].width;
    const separacion = Math.round(ancho * 0.02);
    const alto = recortes.reduce((a, r) => a + r.alto, 0) + separacion * (recortes.length - 1);
    const lienzo = document.createElement('canvas');
    lienzo.width = ancho;
    lienzo.height = alto;
    const ctx = lienzo.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, ancho, alto);
    let y = 0;
    for (const r of recortes) {
        ctx.drawImage(r.c, 0, 0, r.c.width, r.alto, 0, y, r.c.width, r.alto);
        y += r.alto + separacion;
    }
    return new Promise((ok, mal) => lienzo.toBlob(b => b ? ok(b) : mal(new Error('No se pudo crear la imagen.')), 'image/png'));
}

// Alto útil de una página: hasta la última fila con tinta + un margen.
function altoConContenido(canvas) {
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    const w = canvas.width, h = canvas.height, bloque = 24;
    for (let y = h - bloque; y > 0; y -= bloque) {
        const datos = ctx.getImageData(0, y, w, bloque).data;
        for (let i = 0; i < datos.length; i += 16) {
            if (datos[i] < 235 || datos[i + 1] < 235 || datos[i + 2] < 235) {
                return Math.min(h, y + bloque + Math.round(w * 0.05));
            }
        }
    }
    return h;
}

async function enviarPdfWhatsapp() {
    if (!blobPdfActual) return;
    const promesaImagen = generarImagenFactura();
    const promesaContacto = fetch(endpointPdfActual.replace(/\/pdf$/, '/whatsapp'))
        .then(r => r.ok ? r.json() : {}).catch(() => ({}));

    // Copiar debe empezar dentro del toque del usuario; se le pasa la promesa de la imagen.
    let copiada = false;
    if (navigator.clipboard && window.ClipboardItem) {
        try {
            await navigator.clipboard.write([new ClipboardItem({ 'image/png': promesaImagen })]);
            copiada = true;
        } catch (err) {
            console.warn('No se pudo copiar la imagen:', err);
        }
    }
    try {
        imagenFacturaBlob = await promesaImagen;
    } catch (err) {
        alert(err.message);
        return;
    }
    contactoFactura = await promesaContacto;
    mostrarPanelWhatsapp(copiada);
}

function mostrarPanelWhatsapp(copiada) {
    cerrarPanelWhatsapp();
    const c = contactoFactura || {};
    const cliente = c.cliente && c.cliente !== 'Cliente General' ? c.cliente : '';
    const tel = (c.telefono || '').replace(/^57/, '');
    const tipo = endpointPdfActual.includes('/cotizaciones/') ? 'pedido' : 'factura';
    const panel = document.createElement('div');
    panel.id = 'panel-wa';
    panel.className = 'panel-wa';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Enviar por WhatsApp');
    panel.innerHTML = `
        <div class="panel-wa-caja">
            <button type="button" class="panel-wa-cerrar" onclick="cerrarPanelWhatsapp()" aria-label="Cerrar">✕</button>
            <h4>Enviar ${tipo}${cliente ? ' a ' + esc(cliente) : ''}</h4>
            <p class="panel-wa-estado ${copiada ? 'ok' : 'aviso'}">${copiada
                ? `✓ Imagen de la ${tipo} copiada en alta resolución.`
                : 'Este navegador no permite copiar la imagen. Usa <b>Compartir imagen</b>.'}</p>
            <label for="wa-telefono">Celular de WhatsApp</label>
            <div class="panel-wa-tel"><span>+57</span><input id="wa-telefono" type="tel" inputmode="numeric" maxlength="15" placeholder="300 123 4567" value="${esc(tel)}"></div>
            ${copiada ? `<ol class="panel-wa-pasos">
                <li>Toca <b>Abrir chat</b>.</li>
                <li>En el chat, mantén presionada la caja de texto y elige <b>Pegar</b>.</li>
                <li>Envía la imagen.</li>
            </ol>` : ''}
            <div class="panel-wa-botones">
                <button type="button" class="btn-wa" onclick="abrirChatWhatsapp()">Abrir chat${cliente ? ' de ' + esc(cliente.split(' ')[0]) : ''}</button>
                <button type="button" class="btn-secundario" onclick="compartirImagenFactura()">Compartir imagen</button>
                <button type="button" class="btn-secundario" onclick="descargarImagenFactura()">Guardar imagen</button>
            </div>
        </div>`;
    document.querySelector('#modal-factura .modal-container').appendChild(panel);
    if (!tel) panel.querySelector('#wa-telefono').focus();
}

function cerrarPanelWhatsapp() {
    document.getElementById('panel-wa')?.remove();
}

function abrirChatWhatsapp() {
    const crudo = (document.getElementById('wa-telefono')?.value || '').replace(/\D/g, '');
    if (crudo.length < 10) {
        alert('Escribe el celular del cliente (10 dígitos).');
        document.getElementById('wa-telefono')?.focus();
        return;
    }
    const tel = crudo.length === 10 ? '57' + crudo : crudo;
    // En celular se abre la app de WhatsApp directo en el chat; en computador, WhatsApp Web/Escritorio.
    if (esCelular()) location.href = `whatsapp://send?phone=${tel}`;
    else window.open(`https://wa.me/${tel}`, '_blank');
}

// Alternativa: menú de compartir del teléfono con la imagen adjunta.
async function compartirImagenFactura() {
    if (!imagenFacturaBlob) return;
    const archivo = new File([imagenFacturaBlob], nombrePdfDescarga.replace(/\.pdf$/i, '.png'), { type: 'image/png' });
    if (navigator.canShare && navigator.canShare({ files: [archivo] })) {
        try { await navigator.share({ files: [archivo] }); } catch (_) { /* cancelado */ }
    } else {
        descargarImagenFactura();
    }
}

function descargarImagenFactura() {
    if (!imagenFacturaBlob) return;
    const url = URL.createObjectURL(imagenFacturaBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = nombrePdfDescarga.replace(/\.pdf$/i, '.png');
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// Abre el PDF original en otra pestaña: máxima nitidez con el visor del dispositivo.
function abrirPdfCompleto() {
    if (urlPdfActual) window.open(urlPdfActual, '_blank');
}

function cerrarModalFactura() {
    cerrarPanelWhatsapp();
    imagenFacturaBlob = null;
    document.getElementById('modal-factura').style.display = 'none';
    document.getElementById('modal-body-pdf').innerHTML = '';
    if (urlPdfActual) {
        URL.revokeObjectURL(urlPdfActual);
        urlPdfActual = '';
        blobPdfActual = null;
    }
}

function descargarPdfDesdeModal() {
    if (!blobPdfActual) return;
    const a = document.createElement('a');
    a.href = urlPdfActual;
    a.download = nombrePdfDescarga;
    document.body.appendChild(a);
    a.click();
    a.remove();
}
