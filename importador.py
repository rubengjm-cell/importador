import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
import time

# ==========================================
# 1. CONFIGURACIÓN DE SEGURIDAD
# ==========================================
if "FIREBASE_KEY" in os.environ:
    # Caso GitHub
    key_dict = json.loads(os.environ["FIREBASE_KEY"])
    cred = credentials.Certificate(key_dict)
else:
    # Caso tu PC (Asegúrate de que el nombre de tu archivo .json sea este)
    cred = credentials.Certificate('firebase-key.json')

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# ==========================================
# 2. FUNCIÓN DE RECOLECCIÓN ULTRA-MASIVA
# ==========================================
def recolectar_masivo():
    print("🚀 INICIANDO RECOLECCIÓN ULTRA-MASIVA (Sin límites de país)...")
    
    # Vamos a pedir 100 páginas. Cada página de Open Food Facts tiene 20 productos.
    # Total esperado: 2.000 productos por cada vez que aprietes el botón.
    for pagina in range(1, 101): 
        print(f"🛰️ Explorando Galaxia de Productos - Página {pagina}...")
        
        # Usamos la URL de etiqueta 'vegan' que es la más estable
        url = f"https://uy.openfoodfacts.org/label/vegan/{pagina}.json"
        
        # Identificamos el robot para que no nos bloqueen
        headers = {
            'User-Agent': 'AppVeganaUY - Windows - Version 1.0 - rubengjm@gmail.com'
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"⚠️ Error en página {pagina} (Status: {response.status_code}). Saltando...")
                continue
                
            data = response.json()
            productos = data.get('products', [])

            if not productos:
                print(f"🏁 Fin de los datos en la página {pagina}.")
                break

            batch = db.batch()
            agregados_en_esta_pagina = 0

            for p in productos:
                codigo = p.get('code')
                if not codigo: continue

                doc_ref = db.collection('productos').document(codigo)
                
                # Priorizamos nombre en español, si no, el que venga
                nombre_final = p.get('product_name_es') or p.get('product_name') or 'Producto sin nombre'
                
                datos = {
                    'nombre': nombre_final,
                    'marca': p.get('brands', 'Marca desconocida'),
                    'codigo': codigo,
                    'es_vegano': True,
                    'imagen': p.get('image_url', ''),
                    'paises_venta': p.get('countries', 'Internacional'),
                    'actualizado': firestore.SERVER_TIMESTAMP
                }
                
                batch.set(doc_ref, datos, merge=True)
                agregados_en_esta_pagina += 1

            batch.commit() # Guarda los 20 productos de la página de un tirón
            print(f"✅ Página {pagina} procesada correctamente.")
            
            # Pausa de 1 segundo para no saturar el servidor
            time.sleep(1)

        except Exception as e:
            print(f"❌ Error crítico en página {pagina}: {e}")
            break

    print("\n🏆 ¡MISIÓN CUMPLIDA! Base de datos actualizada.")

if __name__ == "__main__":
    recolectar_masivo()