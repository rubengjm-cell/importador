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
    """Conecta con Firebase usando la llave de GitHub (Nube) o el archivo local (PC)."""
    if "FIREBASE_KEY" in os.environ:
        # CASO GITHUB ACTIONS: Lee el 'Secret' que cargaste en la web
        try:
            key_dict = json.loads(os.environ["FIREBASE_KEY"])
            cred = credentials.Certificate(key_dict)
            print("🔐 Conectado a Firebase usando Secrets de GitHub.")
        except Exception as e:
            print(f"❌ Error al procesar FIREBASE_KEY: {e}")
            return None
    else:
        # CASO LOCAL (Tu PC): Busca el archivo .json en la carpeta
        try:
            cred = credentials.Certificate('firebase-key.json')
            print("🏠 Conectado a Firebase usando archivo local.")
        except Exception as e:
            print(f"⚠️ No se encontró firebase-key.json ni Secret: {e}")
            return None

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

# Inicializamos la base de datos
db = inicializar_firebase()

# ==========================================
# 2. FUNCIÓN DE RECOLECCIÓN PARA URUGUAY
# ==========================================
def recolectar_masivo():
    if not db:
        print("❌ Error: Base de datos no disponible. Abortando.")
        return

    print("\n🇺🇾 INICIANDO RECOLECCIÓN ESPECÍFICA PARA URUGUAY...")
    
    # Escaneamos 10 páginas (aprox 200 productos)
    for pagina in range(1, 11): 
        print(f"🛰️ Buscando en Uruguay - Página {pagina}...")
        
        # API de Open Food Facts con filtros específicos
        url = "https://world.openfoodfacts.org/api/v2/search"
        params = {
            "countries_tags_en": "uruguay",
            "labels_tags_en": "vegan",
            "page": pagina,
            "page_size": 20,
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
                print(f"⚠️ Error {response.status_code} en página {pagina}. Saltando...")
                continue
                
            data = response.json()
            productos = data.get('products', [])

            if not productos:
                print(f"🏁 No hay más productos uruguayos en la página {pagina}.")
                break

            batch = db.batch()
            conteo = 0

            for p in productos:
                codigo = p.get('code')
                if not codigo: continue

                doc_ref = db.collection('productos').document(codigo)
                
                # Buscamos el mejor nombre disponible
                nombre = p.get('product_name_es') or p.get('product_name') or 'Producto sin nombre'
                
                datos = {
                    'nombre': nombre,
                    'marca': p.get('brands', 'Marca desconocida'),
                    'codigo': codigo,
                    'es_vegano': True,
                    'imagen': p.get('image_url', ''),
                    'ingredientes': p.get('ingredients_text_es') or "No detallados en la base",
                    'paises_venta': p.get('countries', 'Uruguay'),
                    'fuente': f"https://world.openfoodfacts.org/product/{codigo}",
                    'actualizado': firestore.SERVER_TIMESTAMP
                }
                
                batch.set(doc_ref, datos, merge=True)
                conteo += 1

            batch.commit()
            print(f"✅ Página {pagina}: {conteo} productos sincronizados con Firebase.")
            
            # Pausa para evitar bloqueos
            time.sleep(3)

        except Exception as e:
            print(f"❌ Error crítico en página {pagina}: {e}")
            break

    print("\n🏆 ¡PROCESO TERMINADO! Base de datos de Uruguay actualizada.")

# ==========================================
# 3. DISPARADOR DE EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    recolectar_masivo()