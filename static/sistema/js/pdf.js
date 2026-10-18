/* Vista previa y descarga de facturas/pedidos en PDF */

async function abrirModalPdf(endpointUrl, tituloModal, filenameDescarga) {
    const container = document.getElementById('modal-body-pdf');
    document.getElementById('modal-titulo-pdf').innerText = '📄 ' + tituloModal;
    container.innerHTML = '<div style="color:var(--gold-bright); text-align:center;">Cargando vista previa...</div>';
    document.getElementById('modal-factura').style.display = 'flex';

    nombrePdfDescarga = filenameDescarga || 'Documento.pdf';

    try {
        const res = await fetch(endpointUrl);
        const blob = await res.blob();
        blobPdfActual = blob;
        urlPdfActual = URL.createObjectURL(blob);

        container.innerHTML = `<object data="${urlPdfActual}" type="application/pdf"><p style="color:#fff;">Tu dispositivo no soporta previsualización integrada. Utiliza el botón inferior para descargar el PDF.</p></object>`;
    } catch (err) {
        container.innerHTML = '<div style="color:#ff6b6b; text-align:center;">Error al cargar la previsualización del PDF</div>';
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
    if (blobPdfActual) {
        const a = document.createElement('a');
        a.href = urlPdfActual;
        a.download = nombrePdfDescarga;
        document.body.appendChild(a);
        a.click();
        a.remove();
    }
}
