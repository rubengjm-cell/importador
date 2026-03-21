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
# 2. FUNCIÓN DE RECOLECCIÓN PROFESIONAL
# ==========================================
def recolectar_masivo():
    if not db:
        print("❌ Error: Base de datos no disponible. Abortando.")
        return

    print("\n🇺🇾 INICIANDO BÚSQUEDA PROFESIONAL (Basada en Documentación OFF)")
    print("🎯 Filtros: Uruguay + Vegano + Ingredientes Completos")
    
    # Escaneamos las primeras 20 páginas (suficiente para el volumen de Uruguay)
    for pagina in range(1, 21): 
        print(f"🛰️ Consultando lote {pagina}...")
        
        # Usamos la API v2 con los tags extraídos de data-fields.txt
        url = "https://world.openfoodfacts.org/api/v2/search"
        
        params = {
            # Filtros por 'tags' (etiquetas estandarizadas) según la Wiki de OFF
            "countries_tags_en": "uruguay",
            "labels_tags_en": "vegan",
            # Filtro de calidad: solo productos que ya tengan ingredientes cargados
            "states_tags_en": "ingredients-completed",
            "page": pagina,
            "page_size": 50, 
            # Pedimos solo los campos necesarios para ahorrar ancho de banda
            "fields": "product_name_es,product_name,brands,code,image_url,ingredients_text_es,countries_tags"
        }
        
        headers = {
            'User-Agent': 'AppVeganaUY - rubengjm@gmail.com (Investigación personal)'
        }

        try:
            # Aumentamos el timeout a 45 segundos por seguridad
            response = requests.get(url, headers=headers, params=params, timeout=45)
            
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
                print(f"🏁 No se encontraron más productos oficiales para Uruguay.")
                break

            batch = db.batch()
            conteo_página = 0

            for p in productos:
                codigo = str(p.get('code', ''))
                if not codigo: continue

                # Priorizamos el nombre en español para la App
                nombre = p.get('product_name_es') or p.get('product_name') or 'Producto sin nombre'
                
                doc_ref = db.collection('productos').document(codigo)
                
                datos = {
                    'nombre': nombre,
                    'marca': p.get('brands', 'Marca desconocida'),
                    'codigo': codigo,
                    'es_vegano': True,
                    'imagen': p.get('image_url', ''),
                    'ingredientes': p.get('ingredients_text_es') or "Ver envase",
                    'fuente': f"https://world.openfoodfacts.org/product/{codigo}",
                    'actualizado': firestore.SERVER_TIMESTAMP
                }
                
                # Agregamos una marca si detectamos el prefijo 773 de Uruguay
                if codigo.startswith('773'):
                    datos['registro_uruguayo'] = True
                
                batch.set(doc_ref, datos, merge=True)
                conteo_página += 1

            if conteo_página > 0:
                batch.commit()
                print(f"✅ Página {pagina}: {conteo_página} productos sincronizados.")
            
            # Pausa de 2 segundos entre páginas para no ser bloqueados
            time.sleep(2) 

        except Exception as e:
            print(f"❌ Error crítico en página {pagina}: {e}")
            # Si hay timeout, esperamos y seguimos con la siguiente página
            time.sleep(5)
            continue

    print("\n🏆 ¡MISIÓN CUMPLIDA! Tu base de datos está al día con Uruguay.")

# ==========================================
# 3. DISPARADOR DE EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    recolectar_masivo()