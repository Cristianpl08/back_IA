from flask import Flask, request, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests
from flask_cors import CORS
from routes import api_bp  # Asegúrate de que api_bp está importado correctamente
app = Flask(__name__)
CORS(app)  # Esto habilitará CORS para todas las rutas

CLIENT_ID = "611668385896-jeom4mshdeqc55rh8hfs2bgi6dnka1q3.apps.googleusercontent.com"  # cristianp app

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return '', 200  # Responder a preflight

    token = request.json.get('token')

    try:
        # Verificar el token con Google
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)
        userid = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name')

        return jsonify({"message": "Login exitoso", "userid": userid, "email": email, "name": name}), 200

    except ValueError:
        return jsonify({"error": "Invalid token"}), 401

app.register_blueprint(api_bp, url_prefix='/api')  # Usa un prefijo para evitar confusiones

if __name__ == '__main__':
    app.run(port=5005, debug=True)