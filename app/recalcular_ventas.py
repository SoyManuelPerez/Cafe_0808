import os
import sys
from bson import ObjectId

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.database import get_db

db = get_db()

def recalcular_todas_las_ventas():
    print("🚀 Iniciando recálculo masivo con regla de ÚLTIMA COMPRA y bolsas de 2.5kg...")
    
    # 1. Obtener costo unitario de la ÚLTIMA COMPRA para cada tipo de empaque
    tipos_emp = ["bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"]
    costos_empaques = {}
    
    for t in tipos_emp:
        ajuste = db.ajustes_empaques.find_one({"tipo_empaque": t})
        if ajuste and "costo_unitario" in ajuste:
            costos_empaques[t] = float(ajuste["costo_unitario"])
        else:
            # Buscar el registro más reciente por fecha y ID
            ultima_compra = db.compras_empaques.find_one(
                {"tipo_empaque": t},
                sort=[("fecha", -1), ("_id", -1)]
            )
            costos_empaques[t] = float(ultima_compra.get("costo_unitario", 0.0)) if ultima_compra else 0.0

    # 2. Respaldo de costo promedio global de café
    compras_cafe = list(db.compras.find())
    total_g_global = sum(c.get("gramos", 0) for c in compras_cafe)
    total_costo_global = sum(c.get("costo_total", 0.0) for c in compras_cafe)
    costo_promedio_gramo_global = (total_costo_global / total_g_global) if total_g_global > 0 else 0.0

    # 3. Mapeo de mayor costo por libra por nombre de producto
    productos_db = list(db.productos.find())
    costo_libra_por_nombre = {}
    for p in productos_db:
        nom = p.get("nombre")
        costo_lib = float(p.get("costo_por_libra", 0.0) or 0.0)
        if nom:
            if nom not in costo_libra_por_nombre or costo_lib > costo_libra_por_nombre[nom]:
                costo_libra_por_nombre[nom] = costo_lib

    ventas = list(db.ventas.find())
    print(f"📦 Se encontraron {len(ventas)} ventas para procesar.")

    actualizadas = 0

    for venta in ventas:
        venta_id = venta["_id"]
        items = venta.get("items", [])
        tipo_venta = venta.get("tipo_venta", "Normal")
        es_obsequio = (tipo_venta == "Obsequio")
        
        total_venta = 0.0 if es_obsequio else sum(item.get("subtotal", 0.0) for item in items)

        # Recalcular Costo de Café
        costo_cafe = 0.0
        for item in items:
            prod = None
            prod_id = item.get("producto_id")
            prod_nombre = item.get("nombre")

            if prod_id:
                try:
                    prod = db.productos.find_one({"_id": ObjectId(prod_id)})
                except Exception:
                    pass

            costo_libra = 0.0
            if prod and float(prod.get("costo_por_libra", 0.0) or 0.0) > 0:
                costo_libra = float(prod.get("costo_por_libra"))
            elif prod_nombre in costo_libra_por_nombre:
                costo_libra = costo_libra_por_nombre[prod_nombre]

            costo_gramo_item = (costo_libra / 500.0) if costo_libra > 0 else costo_promedio_gramo_global
            costo_cafe += item.get("gramos_totales", 0) * costo_gramo_item

        # Recalcular Costo de Empaques
        costo_empaques_total = 0.0
        for item in items:
            cant = item.get("cantidad", 0)
            g = item.get("gramaje", 0)
            if g == 250:
                costo_empaques_total += cant * (costos_empaques.get("bolsa_250g", 0) + costos_empaques.get("etiqueta_250g", 0))
            elif g == 500:
                costo_empaques_total += cant * (costos_empaques.get("bolsa_500g", 0) + costos_empaques.get("etiqueta_500g", 0))
            elif g == 2500:
                # 2.5kg: CERO costo de bolsa + etiqueta de 500g
                costo_empaques_total += cant * costos_empaques.get("etiqueta_500g", 0)

        costo_est = round(costo_cafe + costo_empaques_total)
        ganancia = total_venta - costo_est

        db.ventas.update_one(
            {"_id": venta_id},
            {"$set": {
                "total_venta": total_venta,
                "costo_estimado": costo_est,
                "ganancia": ganancia
            }}
        )
        actualizadas += 1

    print(f"✅ ¡Proceso finalizado con éxito! Se corrigieron {actualizadas} ventas.")

if __name__ == "__main__":
    recalcular_todas_las_ventas()
