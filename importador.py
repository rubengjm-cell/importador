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
            print("🏠 Conectado a Firebase localmente.")
        except: return None

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()

db = inicializar_firebase()

# ==========================================
# 2. FUNCIÓN DE RECOLECCIÓN EXPANDIDA
# ==========================================
def recolectar_masivo():
    if not db: return

    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))

    print("\n🇺🇾 INICIANDO RECOLECCIÓN EXPANDIDA (Sello + Análisis de Ingredientes)...")
    
    # Traemos TODO el catálogo de Uruguay (hasta 5000 productos para analizar)
    for pagina in range(1, 51): 
        print(f"🛰️ Explorando catálogo uruguayo - Página {pagina}...")
        
        url = "https://world.openfoodfacts.org/api/v2/search"
        params = {
            "countries_tags_en": "uruguay",
            # QUITAMOS EL FILTRO VEGANO DEL SERVIDOR PARA TRAER TODO
            "page": pagina,
            "page_size": 100, # Lotes de 100 productos
            # Pedimos los campos de etiquetas y de análisis de ingredientes
            "fields": "product_name_es,product_name,brands,code,image_url,ingredients_text_es,labels_tags,ingredients_analysis_tags"
        }
        
        headers = { 'User-Agent': 'AppVeganaUY - rubengjm@gmail.com' }

        try:
            response = session.get(url, headers=headers, params=params, timeout=60)
            
            if response.status_code != 200:
                print(f"⚠️ Servidor ocupado ({response.status_code}). Saltando...")
                continue
                
            data = response.json()
            productos = data.get('products', [])

            if not productos:
                print(f"🏁 Fin del catálogo de Uruguay en la página {pagina}.")
                break

            batch = db.batch()
            conteo_veganos = 0

            for p in productos:
                codigo = str(p.get('code', ''))
                if not codigo: continue

                nombre = p.get('product_name_es') or p.get('product_name')
                if not nombre: continue 

                # --- EL COLADOR INTELIGENTE ---
                etiquetas = p.get('labels_tags', [])
                analisis_ingredientes = p.get('ingredients_analysis_tags', [])

                # 1. Tiene el sello vegano oficial cargado por el usuario
                es_vegano_sello = 'en:vegan' in etiquetas
                
                # 2. El sistema de OFF leyó los ingredientes y determinó que es vegano
                es_vegano_analisis = 'en:vegan' in analisis_ingredientes

                # Si cumple cualquiera de las dos, ¡ADENTRO!
                if es_vegano_sello or es_vegano_analisis:
                    doc_ref = db.collection('productos').document(codigo)
                    batch.set(doc_ref, {
                        'nombre': nombre,
                        'marca': p.get('brands', 'Marca desconocida'),
                        'codigo': codigo,
                        'es_vegano': True,
                        'imagen': p.get('image_url', ''),
                        'ingredientes': p.get('ingredients_text_es') or "Consultar envase",
                        'fuente': f"https://world.openfoodfacts.org/product/{codigo}",
                        'deteccion': 'Sello Oficial' if es_vegano_sello else 'Análisis de Ingredientes',
                        'actualizado': firestore.SERVER_TIMESTAMP
                    }, merge=True)
                    conteo_veganos += 1

            if conteo_veganos > 0:
                batch.commit()
                print(f"✅ Página {pagina}: ¡{conteo_veganos} productos veganos rescatados!")
            else:
                print(f"ℹ️ Página {pagina}: Se analizaron 100 productos, ninguno vegano.")
            
            time.sleep(2) 

        except Exception as e:
            print(f"⚠️ Error en lote {pagina}: {e}. Reintentando después...")
            time.sleep(5)
            continue

    print("\n🏆 BÚSQUEDA EXPANDIDA FINALIZADA.")

if __name__ == "__main__":
    recolectar_masivo()