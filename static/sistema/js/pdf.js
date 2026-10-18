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
        await dibujarPdf(blob, container);
    } catch (err) {
        console.error('Vista previa con PDF.js falló:', err);
        // Respaldo: visor del navegador. Si tampoco puede, quedan los botones de abrir y descargar.
        container.innerHTML = `<iframe class="pdf-iframe" src="${urlPdfActual}" title="${esc(tituloModal)}"></iframe>
            <p class="pdf-estado">Si no ves el documento, usa <strong>Abrir PDF</strong> o <strong>Descargar</strong>.</p>`;
    }
}

/* Envía la factura por WhatsApp sin descargarla.
   - Celular: abre el menú de compartir con el PDF adjunto (eliges WhatsApp y el chat).
   - Computador: abre WhatsApp con el chat del cliente (si tiene celular registrado) y un
     enlace seguro para ver la factura, válido por 30 días. */
async function enviarPdfWhatsapp() {
    if (!blobPdfActual) return;
    const archivo = new File([blobPdfActual], nombrePdfDescarga, { type: 'application/pdf' });

    if (esCelular() && navigator.canShare && navigator.canShare({ files: [archivo] })) {
        try {
            await navigator.share({ files: [archivo], title: tituloPdfActual, text: `${tituloPdfActual} · 0808 Café de Especialidad` });
            return;
        } catch (err) {
            if (err && err.name === 'AbortError') return; // el usuario cerró el menú
            // si compartir falla, se usa el enlace
        }
    }

    // La ventana se abre ya (dentro del clic) para que el navegador no la bloquee.
    const ventana = window.open('', '_blank');
    try {
        const res = await fetch(endpointPdfActual.replace(/\/pdf$/, '/whatsapp'));
        const datos = await res.json();
        if (!res.ok) throw new Error(datos.detail || 'No se pudo crear el enlace.');
        const tipoDoc = endpointPdfActual.includes('/cotizaciones/') ? 'tu pedido' : 'tu factura';
        const saludo = datos.cliente && datos.cliente !== 'Cliente General' ? `Hola ${datos.cliente} ☕` : 'Hola ☕';
        const texto = `${saludo}\nTe compartimos ${tipoDoc} N° ${datos.numero} de 0808 Café por ${fmtCOP(datos.total)}.\n\nPuedes verla aquí: ${datos.url}\n\n¡Gracias por tu compra!`;
        const destino = `https://wa.me/${datos.telefono || ''}?text=${encodeURIComponent(texto)}`;
        if (ventana) ventana.location.href = destino; else location.href = destino;
    } catch (err) {
        if (ventana) ventana.close();
        alert(err.message || 'No se pudo preparar el envío por WhatsApp.');
    }
}

// Abre el PDF original en otra pestaña: máxima nitidez con el visor del dispositivo.
function abrirPdfCompleto() {
    if (urlPdfActual) window.open(urlPdfActual, '_blank');
}

function cerrarModalFactura() {
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
