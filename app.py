from flask import Flask, request, jsonify
from google.oauth2 import id_token
from google.auth.transport import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Esto habilitará CORS para todas las rutas

CLIENT_ID = "277375272976-pkvaiiom7klc9mubv2aj8lbrtroqvb7i.apps.googleusercontent.com"  # Usa tu client_id

@app.route('/login', methods=['POST'])
def login():
    token = request.json.get('token')
    
    try:
        # Verificar el token con Google
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), CLIENT_ID)

        # ID token is valid. Get the user's Google Account info.
        userid = idinfo['sub']
        email = idinfo['email']
        name = idinfo.get('name')

        # Aquí podrías implementar la lógica para manejar usuarios en tu backend
        return jsonify({"message": "Login exitoso", "userid": userid, "email": email, "name": name}), 200

    except ValueError:
        # El token es inválido
        return jsonify({"error": "Invalid token"}), 401

if __name__ == '__main__':
    app.run(port=5005, debug=True)