
import io
import base64
from flask import Flask, request, jsonify, render_template
from PIL import Image

app = Flask(__name__)

MAX_SIZE_KB = 800

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
        img = Image.open(file.stream)
        
        # Guardar la imagen en un buffer en memoria para obtener su tamaño inicial
        img_buffer = io.BytesIO()
        img.save(img_buffer, format=img.format or 'JPEG')
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
