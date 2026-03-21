import os
import json
import requests
import firebase_admin
from firebase_admin import credentials, firestore
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==========================================
# 1. CONFIGURACIÓN DE FIREBASE
# ==========================================
def inicializar_firebase():
    if "FIREBASE_KEY" in os.environ:
        try:
            key_dict = json.loads(os.environ["FIREBASE_KEY"])
            cred = credentials.Certificate(key_dict)
            print("🔐 Conectado a Firebase usando Secrets de GitHub.")
        except Exception as e:
            print(f"❌ Error en FIREBASE_KEY: {e}")
            return None
    else:
        try:
            cred = credentials.Certificate('firebase-key.json')
            print("🏠 Conectado a Firebase usando archivo local.")
        except: return None

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = inicializar_firebase()

# ==========================================
# 2. FUNCIÓN DE RECOLECCIÓN CON REINTENTOS
# ==========================================
def recolectar_masivo():
    if not db: return

    # Configurar reintentos automáticos a nivel de red
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    print("\n🇺🇾 INICIANDO RECOLECCIÓN REFORZADA (Uruguay)...")
    
    for pagina in range(1, 11): 
        print(f"🛰️ Intentando conectar con lote {pagina}...")
        
        url = "https://world.openfoodfacts.org/api/v2/search"
        params = {
            "countries_tags_en": "uruguay",
            "labels_tags_en": "vegan",
            "page": pagina,
            "page_size": 50, 
            "fields": "product_name_es,product_name,brands,code,image_url,ingredients_text_es"
        }
        
        headers = { 'User-Agent': 'AppVeganaUY - rubengjm@gmail.com' }

    # Intentamos la petición con un tiempo de espera muy largo
        try:
            response = session.get(url, headers=headers, params=params, timeout=90)
            
            if response.status_code != 200:
                print(f"⚠️ Servidor ocupado ({response.status_code}). Saltando...")
                continue
                
            data = response.json()
            productos = data.get('products', [])

            if not productos:
                print(f"🏁 No hay más datos en página {pagina}.")
                break

            batch = db.batch()
            conteo = 0

            for p in productos:
                codigo = str(p.get('code', ''))
                if not codigo: continue

                # Filtro de calidad manual (en nuestra PC, no en el servidor)
                nombre = p.get('product_name_es') or p.get('product_name')
                if not nombre: continue # Si no tiene nombre, lo ignoramos

                doc_ref = db.collection('productos').document(codigo)
                batch.set(doc_ref, {
                    'nombre': nombre,
                    'marca': p.get('brands', 'Marca desconocida'),
                    'codigo': codigo,
                    'es_vegano': True,
                    'imagen': p.get('image_url', ''),
                    'ingredientes': p.get('ingredients_text_es') or "Consultar envase",
                    'fuente': f"https://world.openfoodfacts.org/product/{codigo}",
                    'actualizado': firestore.SERVER_TIMESTAMP
                }, merge=True)
                conteo += 1

            if conteo > 0:
                batch.commit()
                print(f"✅ Página {pagina}: {conteo} productos sincronizados.")
            
            time.sleep(5) # Pausa larga para no estresar al servidor

        except Exception as e:
            print(f"⚠️ Error de conexión en lote {pagina}: {e}. Reintentando después...")
            time.sleep(10)
            continue

    print("\n🏆 PROCESO FINALIZADO.")

if __name__ == "__main__":
    recolectar_masivo()