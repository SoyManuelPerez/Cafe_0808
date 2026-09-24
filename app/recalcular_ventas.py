import os
import sys
from bson import ObjectId

# Ajustar rutas para importar la base de datos de la app
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.database import get_db

db = get_db()

def recalcular_todas_las_ventas():
    print("🚀 Iniciando recalculo masivo de ventas...")
    
    # 1. Obtener el resumen actualizado de empaques para sus costos unitarios
    # Si no hay ventas previas en la función de resumen, asignamos valores por defecto o leemos ajustes
    tipos_emp = ["bolsa_250g", "bolsa_500g", "etiqueta_250g", "etiqueta_500g"]
    costos_empaques = {}
    
    for t in tipos_emp:
        ajuste = db.ajustes_empaques.find_one({"tipo_empaque": t})
        if ajuste and "costo_unitario" in ajuste:
            costos_empaques[t] = float(ajuste["costo_unitario"])
        else:
            # Si no hay ajuste manual, calcular promedio desde compras
            compras = list(db.compras_empaques.find({"tipo_empaque": t}))
            cant_total = sum(c.get("cantidad", 0) for c in compras)
            costo_total = sum(c.get("costo_total", 0.0) for c in compras)
            costos_empaques[t] = (costo_total / cant_total) if cant_total > 0 else 0.0

    # 2. Obtener costo promedio por gramo global de respaldo (por si algún producto viejo no tiene costo por libra)
    compras_cafe = list(db.compras.find())
    total_g_global = sum(c.get("gramos", 0) for c in compras_cafe)
    total_costo_global = sum(c.get("costo_total", 0.0) for c in compras_cafe)
    costo_promedio_gramo_global = (total_costo_global / total_g_global) if total_g_global > 0 else 0.0

    # 3. Obtener todas las ventas registradas
    ventas = list(db.ventas.find())
    print(f"📦 Se encontraron {len(ventas)} ventas para procesar.")

    actualizadas = 0

    for venta in ventas:
        venta_id = venta["_id"]
        items = venta.get("items", [])
        tipo_venta = venta.get("tipo_venta", "Normal")
        es_obsequio = (tipo_venta == "Obsequio")
        
        # Recalcular Total Venta
        total_venta = 0.0 if es_obsequio else sum(item.get("subtotal", 0.0) for item in items)

        # Recalcular Costo de Café específico por producto
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

            if not prod and prod_nombre:
                prod = db.productos.find_one({"nombre": prod_nombre})

            costo_libra = float(prod.get("costo_por_libra", 0.0)) if (prod and "costo_por_libra" in prod) else 0.0
            
            # Si tiene costo por libra asignado usa ese, de lo contrario respalda con el promedio
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

        # Costo Estimado Final y Ganancia
        costo_est = round(costo_cafe + costo_empaques_total)
        ganancia = total_venta - costo_est

        # Actualizar documento en MongoDB
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
