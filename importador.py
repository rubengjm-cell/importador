import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
import time

# ==========================================
# 1. CONFIGURACIÓN DE SEGURIDAD Y FIREBASE
# ==========================================
def inicializar_firebase():
    if "FIREBASE_KEY" in os.environ:
        try:
            key_dict = json.loads(os.environ["FIREBASE_KEY"])
            cred = credentials.Certificate(key_dict)
            print("🔐 Conectado a Firebase usando Secrets de GitHub.")
        except Exception as e:
            print(f"❌ Error al procesar FIREBASE_KEY: {e}")
            return None
    else:
        try:
            cred = credentials.Certificate('firebase-key.json')
            print("🏠 Conectado a Firebase usando archivo local.")
        except Exception as e:
            print(f"⚠️ No se encontró firebase-key.json ni Secret: {e}")
            return None

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = inicializar_firebase()

# ==========================================
# 2. FUNCIÓN DE RECOLECCIÓN DUAL (TEXTO + CÓDIGO 773)
# ==========================================
def recolectar_masivo():
    if not db:
        print("❌ Error: Base de datos no disponible. Abortando.")
        return

    print("\n🇺🇾 INICIANDO BÚSQUEDA DUAL (País: Uruguay OR Prefijo: 773)...")
    
    # Aumentamos a 50 páginas porque al buscar "vegan" global hay mucho más que filtrar
    for pagina in range(1, 51): 
        print(f"🛰️ Analizando lote de productos veganos - Página {pagina}...")
        
        url = "https://world.openfoodfacts.org/api/v2/search"
# CAMBIO: Buscamos específicamente el prefijo 773 en el código
        params = {
            "code": "773*", # El asterisco busca todo lo que empiece con 773
            "labels_tags_en": "vegan",
            "page": pagina,
            "page_size": 20, # Bajamos a 50 para que el servidor responda más rápido
            "fields": "product_name,product_name_es,brands,code,image_url,ingredients_text_es,countries"
        }
        
        headers = {
            'User-Agent': 'AppVeganaUY - rubengjm@gmail.com (Investigación personal)'
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 429:
                print("⏳ Servidor saturado. Esperando 30 segundos...")
                time.sleep(30)
                continue

            if response.status_code != 200:
                print(f"⚠️ Error {response.status_code} en página {pagina}.")
                continue
                
            data = response.json()
            productos = data.get('products', [])

            if not productos:
                break

            batch = db.batch()
            conteo_uruguay = 0

            for p in productos:
                codigo = str(p.get('code', ''))
                if not codigo: continue

                # --- FILTRO DUAL ---
                # Condición A: El código empieza con 773 (Prefijo GS1 Uruguay)
                es_773 = codigo.startswith('773')
                
                # Condición B: El texto de países contiene "uruguay"
                paises = str(p.get('countries', '')).lower()
                es_pais_uruguay = 'uruguay' in paises

                # SI CUMPLE ALGUNA DE LAS DOS, LO GUARDAMOS
                if es_773 or es_pais_uruguay:
                    doc_ref = db.collection('productos').document(codigo)
                    nombre = p.get('product_name_es') or p.get('product_name') or 'Producto sin nombre'
                    
                    # Identificamos por qué se guardó para saber la calidad del dato
                    metodo = "Por Prefijo 773" if es_773 else "Por Etiqueta Uruguay"
                    if es_773 and es_pais_uruguay: metodo = "Detección Completa"

                    datos = {
                        'nombre': nombre,
                        'marca': p.get('brands', 'Marca desconocida'),
                        'codigo': codigo,
                        'es_vegano': True,
                        'imagen': p.get('image_url', ''),
                        'ingredientes': p.get('ingredients_text_es') or "No detallados",
                        'paises_venta': p.get('countries', 'Uruguay'),
                        'fuente': f"https://world.openfoodfacts.org/product/{codigo}",
                        'metodo_deteccion': metodo,
                        'actualizado': firestore.SERVER_TIMESTAMP
                    }
                    
                    batch.set(doc_ref, datos, merge=True)
                    conteo_uruguay += 1

            if conteo_uruguay > 0:
                batch.commit()
                print(f"✅ Página {pagina}: Se encontraron {conteo_uruguay} productos uruguayos.")
            else:
                print(f"ℹ️ Página {pagina}: Sin novedades para Uruguay.")
            
            time.sleep(2) # Pausa amigable

        except Exception as e:
            print(f"❌ Error en página {pagina}: {e}")
            break

    print("\n🏆 ¡PROCESO TERMINADO! Base de datos sincronizada.")

if __name__ == "__main__":
    recolectar_masivo()