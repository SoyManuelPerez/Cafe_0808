/* =====================================================
   CONFIGURACIÓN DE LA LANDING — edita aquí tus datos
   ===================================================== */
export const WHATSAPP = "573012226387";            // 57 = Colombia + número
export const INSTAGRAM = "https://www.instagram.com/0808cafe/";
export const TIKTOK = "https://www.tiktok.com/@0808cafe";

// Precios de respaldo (pesos colombianos) por tamaño de bolsa.
// Si el producto existe en el sistema con el mismo nombre y gramaje, se usa el precio del sistema.
// "clave" es la palabra que se busca en el nombre del producto del sistema.
export const PRODUCTOS = [
  {
    id: "bourbon", clave: "bourbon", nombre: "Bourbon Rosado", subtitulo: "",
    img: "bourbon-rosado", origen: "Gigante – Huila / Colombia", proceso: "Honey", acidez: "Acidez baja",
    msnm: 1950, aroma: "Dulce, panela", sabor: "Frutal, caramelo",
    precios: { 250: 32000, 500: 58000 }
  },
  {
    id: "chiroso", clave: "chiroso", nombre: "Chiroso", subtitulo: "",
    img: "chiroso", origen: "Urrao – Antioquia / Colombia", proceso: "Lavado", acidez: "Acidez media",
    msnm: 2090, aroma: "Floral, lima", sabor: "Dulce, miel",
    precios: { 250: 34000, 500: 62000 }
  },
  {
    id: "blend", clave: "blend", nombre: "Blend", subtitulo: "Castillo – Caturra",
    img: "blend", origen: "Ciudad Bolívar – Antioquia / Colombia", proceso: "Lavado", acidez: "Acidez media",
    msnm: 1950, aroma: "Caramelo dulce", sabor: "Chocolate, panela",
    precios: { 250: 28000, 500: 50000 }
  }
];

export const TAMANOS = [250, 500];                 // gramos
export const TAMANO_INICIAL = 250;
export const MOLIENDAS = ["Grano", "Media", "Fina", "Gruesa"];   // mismo orden que la etiqueta
export const TOSTIONES = ["Claro", "Medio"];
export const MAX_POR_LINEA = 30;
