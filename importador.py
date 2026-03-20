def recolectar_masivo():
    print("🇺🇾 INICIANDO RECOLECCIÓN ESPECÍFICA PARA URUGUAY...")
    
    # Bajamos el número de páginas para que no nos bloqueen (probá con 10 primero)
    for pagina in range(1, 11): 
        print(f"🛰️ Buscando en Uruguay - Página {pagina}...")
        
        # CAMBIO CLAVE: Usamos la búsqueda por país y etiqueta, es más liviana para el servidor
        url = "https://world.openfoodfacts.org/api/v2/search"
        params = {
            "countries_tags_en": "uruguay",
            "labels_tags_en": "vegan",
            "page": pagina,
            "page_size": 20,
            "fields": "product_name,brands,code,image_url,ingredients_text_es,countries"
        }
        
        headers = {
            'User-Agent': 'AppVeganaUY - rubengjm@gmail.com (Investigación personal)'
        }

        try:
            # Agregamos los parámetros (params) en lugar de la URL larga
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 429:
                print("⏳ El servidor dice que vamos muy rápido. Esperando 30 segundos...")
                time.sleep(30)
                continue

            if response.status_code != 200:
                print(f"⚠️ Error {response.status_code} en página {pagina}. Saltando...")
                continue
                
            data = response.json()
            productos = data.get('products', [])

            if not productos:
                print(f"🏁 No hay más productos uruguayos.")
                break

            batch = db.batch()
            for p in productos:
                codigo = p.get('code')
                if not codigo: continue

                doc_ref = db.collection('productos').document(codigo)
                
                # Guardamos la fuente para que la App la muestre
                datos = {
                    'nombre': p.get('product_name') or 'Producto sin nombre',
                    'marca': p.get('brands', 'Marca desconocida'),
                    'codigo': codigo,
                    'es_vegano': True,
                    'imagen': p.get('image_url', ''),
                    'ingredientes': p.get('ingredients_text_es') or "No detallados",
                    'paises_venta': p.get('countries', 'Uruguay'),
                    'fuente': f"https://world.openfoodfacts.org/product/{codigo}",
                    'actualizado': firestore.SERVER_TIMESTAMP
                }
                batch.set(doc_ref, datos, merge=True)

            batch.commit()
            print(f"✅ Página {pagina} guardada en Firebase.")
            
            # Pausa más larga (3 segundos) para que el servidor no se enoje
            time.sleep(3)

        except Exception as e:
            print(f"❌ Error en página {pagina}: {e}")
            break