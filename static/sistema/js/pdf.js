/* Vista previa y descarga de facturas/pedidos en PDF.
   El PDF se dibuja página por página con PDF.js: funciona igual en computador, Android y
   iPhone (Safari no muestra PDF incrustados dentro de una ventana). */

// PDF.js 3.11.174 servido desde el propio sitio (static/sistema/vendor/pdfjs): no depende de internet externo.
const PDFJS_BASE = '/static/sistema/vendor/pdfjs';
let _pdfjsPromesa = null;

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

async function dibujarPdf(blob, contenedor) {
    const lib = await cargarPdfJs();
    const doc = await lib.getDocument({ data: new Uint8Array(await blob.arrayBuffer()), isEvalSupported: false }).promise;
    contenedor.innerHTML = '';
    const ancho = Math.max(280, contenedor.clientWidth - 24);
    const escalaPantalla = Math.min(window.devicePixelRatio || 1, 2);
    for (let n = 1; n <= doc.numPages; n++) {
        const pagina = await doc.getPage(n);
        const base = pagina.getViewport({ scale: 1 });
        const vista = pagina.getViewport({ scale: (ancho / base.width) * escalaPantalla });
        const canvas = document.createElement('canvas');
        canvas.className = 'pdf-pagina';
        canvas.width = Math.floor(vista.width);
        canvas.height = Math.floor(vista.height);
        canvas.style.width = `${Math.floor(vista.width / escalaPantalla)}px`;
        canvas.setAttribute('aria-label', `Página ${n} de ${doc.numPages}`);
        contenedor.appendChild(canvas);
        await pagina.render({ canvasContext: canvas.getContext('2d'), viewport: vista }).promise;
    }
}

async function abrirModalPdf(endpointUrl, tituloModal, filenameDescarga) {
    const container = document.getElementById('modal-body-pdf');
    document.getElementById('modal-titulo-pdf').textContent = '📄 ' + tituloModal;
    container.classList.add('pdf-visor');
    container.innerHTML = '<p class="pdf-estado">Cargando vista previa…</p>';
    document.getElementById('modal-factura').style.display = 'flex';
    nombrePdfDescarga = filenameDescarga || 'Documento.pdf';

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
        // Respaldo: visor del navegador. Si tampoco puede, queda el botón de descarga.
        container.innerHTML = `<iframe class="pdf-iframe" src="${urlPdfActual}" title="${esc(tituloModal)}"></iframe>
            <p class="pdf-estado">Si no ves el documento, usa <strong>Descargar PDF</strong>.</p>`;
    }
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
    const archivo = new File([blobPdfActual], nombrePdfDescarga, { type: 'application/pdf' });
    // En celular se abre el menú de compartir (guardar en Archivos, WhatsApp...) si está disponible.
    if (navigator.canShare && /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) && navigator.canShare({ files: [archivo] })) {
        navigator.share({ files: [archivo], title: nombrePdfDescarga }).catch(() => {});
        return;
    }
    const a = document.createElement('a');
    a.href = urlPdfActual;
    a.download = nombrePdfDescarga;
    document.body.appendChild(a);
    a.click();
    a.remove();
}
