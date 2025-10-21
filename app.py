
import io
import base64
import requests
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from PIL import Image

load_dotenv() # Carga las variables del archivo .env
app = Flask(__name__)

MAX_SIZE_KB = 800

# Leemos las credenciales de las variables de entorno
SIGHTENGINE_API_USER = os.getenv('SIGHTENGINE_API_USER')
SIGHTENGINE_API_SECRET = os.getenv('SIGHTENGINE_API_SECRET')

def check_image_moderation(image_bytes):
    """Verifica el contenido de la imagen usando Sightengine."""
    if not SIGHTENGINE_API_USER or not SIGHTENGINE_API_SECRET:
        # Si las credenciales no están configuradas en el entorno, se omite la verificación
        print("ADVERTENCIA: Las variables de entorno SIGHTENGINE_API_USER o SIGHTENGINE_API_SECRET no están configuradas. Omitiendo moderación.")
        return True, "Credenciales de API no configuradas"

    url = 'https://api.sightengine.com/1.0/check.json'
    files = {'media': image_bytes}
    params = {
        'models': 'nudity,wad,offensive', # Modelos para desnudez, armas y contenido ofensivo
        'api_user': SIGHTENGINE_API_USER,
        'api_secret': SIGHTENGINE_API_SECRET
    }
    
    try:
        response = requests.post(url, files=files, data=params)
        response.raise_for_status()
        output = response.json()
        print("Respuesta de Sightengine:", output) # Log para depuración

        # Comprobamos si la imagen es segura. Un valor alto en 'raw' indica desnudez explícita.
        if output.get('nudity', {}).get('raw') > 0.5:
            return False, "Contenido explícito para adultos detectado."
        if output.get('weapon') > 0.5:
            return False, "Contenido violento o de armas detectado."
        if output.get('offensive', {}).get('prob') > 0.5:
            return False, "Contenido ofensivo detectado."

        return True, "Imagen segura."

    except requests.exceptions.RequestException as e:
        print(f"Error al contactar la API de Sightengine: {e}")
        # Si la API falla, decidimos si bloquear o permitir. Por seguridad, podríamos bloquear.
        return False, "No se pudo verificar la imagen."
    except Exception as e:
        print(f"Error inesperado durante la moderación: {e}")
        return False, "Error inesperado durante la moderación."


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No se encontró ninguna imagen'}), 400

    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400

    try:
        image_bytes = file.read() # Leemos los bytes de la imagen

        # --- Verificación de Moderación ---
        is_safe, reason = check_image_moderation(io.BytesIO(image_bytes))
        if not is_safe:
            return jsonify({'error': f'Moderación fallida: {reason}'}), 400
        # ---------------------------------

        img = Image.open(io.BytesIO(image_bytes))
        
        # Guardar la imagen en un buffer en memoria para obtener su tamaño inicial
        img_buffer = io.BytesIO()
        # Usamos el formato original o JPEG como fallback
        img_format = img.format if img.format in ['JPEG', 'PNG'] else 'JPEG'
        if img.mode in ('RGBA', 'P') and img_format == 'JPEG':
            img = img.convert('RGB')
        img.save(img_buffer, format=img_format)
        initial_size_kb = len(img_buffer.getvalue()) / 1024

        if initial_size_kb <= MAX_SIZE_KB:
            # Si la imagen ya cumple con el tamaño, la devolvemos directamente
            img_buffer.seek(0)
            encoded_img = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            return jsonify({
                'image_data': encoded_img,
                'size': len(img_buffer.getvalue())
            })

        # Lógica de compresión iterativa
        quality = 95
        while quality > 10: # No bajar de 10 para no degradar demasiado
            compressed_buffer = io.BytesIO()
            # Asegurarse de que la imagen sea RGB para guardarla como JPEG
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(compressed_buffer, format='JPEG', quality=quality, optimize=True)
            
            new_size_kb = len(compressed_buffer.getvalue()) / 1024

            if new_size_kb <= MAX_SIZE_KB:
                compressed_buffer.seek(0)
                encoded_img = base64.b64encode(compressed_buffer.getvalue()).decode('utf-8')
                return jsonify({
                    'image_data': encoded_img,
                    'size': len(compressed_buffer.getvalue())
                })
            
            quality -= 5 # Reducir la calidad en pasos de 5

        return jsonify({'error': 'No se pudo comprimir la imagen al tamaño deseado sin perder demasiada calidad.'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
