from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from functools import wraps
import os
import logging
import uuid
from werkzeug.utils import secure_filename
import mimetypes
from datetime import datetime
from supabase import create_client, Client

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# --- Supabase Configuration ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    logging.critical("SUPABASE_URL and SUPABASE_KEY must be set in environment variables.")
    supabase: Client = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    logging.info("Supabase client initialized successfully.")


# Attempt to import the GeminiFlashAPI class and initialize it globally
gemini_api_client = None
try:
    from API_Interface import GeminiFlashAPI
    logging.info("Successfully imported GeminiFlashAPI from API_Interface.py")
    gemini_api_client = GeminiFlashAPI()
    logging.info(f"Global GeminiFlashAPI client initialized successfully with model: {gemini_api_client.model_name} and API key: {gemini_api_client.api_key[:5]}...")
except ImportError as e:
    logging.error(f"CRITICAL_IMPORT_ERROR: Could not import GeminiFlashAPI from API_Interface.py: {e}. ")
except ValueError as ve:
    logging.error(f"CRITICAL_CONFIG_ERROR: ValueError during global GeminiFlashAPI initialization (likely API key issue): {ve}. ")
except Exception as ex:
    logging.error(f"CRITICAL_INIT_ERROR: An unexpected error occurred during global GeminiFlashAPI initialization: {ex}")

# Fallback to a dummy class ONLY if gemini_api_client is still None after attempts
if gemini_api_client is None:
    logging.warning("FALLBACK_TO_DUMMY_API: Global GeminiFlashAPI client failed to initialize. Using a DUMMY version.")
    class DummyGeminiAPI:
        def __init__(self, api_key=None, model_name="dummy-model-fallback"):
            self.api_key = "DUMMY_KEY_IN_USE"
            self.model_name = model_name
            logging.warning(f"Using DUMMY GeminiFlashAPI initialized with model: {self.model_name}. THIS IS NOT THE REAL API.")
        def generate_content(self, prompt, stream=False, generation_config=None, safety_settings=None):
            logging.info(f"Dummy generate_content called with prompt: '{prompt}' for model '{self.model_name}'")
            class DummyResponse:
                def __init__(self, text_content, parts_present=True, feedback=None):
                    self.text = text_content
                    self.parts = ["dummy_part"] if parts_present else []
                    self.prompt_feedback = feedback
            return DummyResponse(f"Simulated response for: '{prompt}' using {self.model_name}", feedback="No issues.")
        def count_tokens(self, prompt):
            return len(prompt.split())
        def start_chat_session(self, history=None):
            logging.info(f"DUMMY_API_LOG: Starting a new dummy chat session.")
            class DummyChatSession:
                def __init__(self):
                    self.history = history or []
                def send_message(self, message_text, stream=False):
                    self.history.append({"role": "user", "parts": [message_text]})
                    response_text = f"Simulated chat response to: '{message_text}'"
                    self.history.append({"role": "model", "parts": [response_text]})
                    class DummyChatResponse:
                        def __init__(self, text):
                            self.text = text
                            self.parts = [text]
                            self.prompt_feedback = None
                    return DummyChatResponse(response_text)
            return DummyChatSession()
        def send_chat_message(self, chat_session, message_text, stream=False):
            logging.info(f"DUMMY_API_LOG: Sending message to dummy chat session: '{message_text}'")
            return chat_session.send_message(message_text, stream=stream)
    gemini_api_client = DummyGeminiAPI()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_key_that_should_be_changed')

# --- DECORATOR FOR AUTHENTICATION ---
def supabase_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token is missing or invalid."}), 401
        
        jwt = auth_header.split(' ')[1]
        
        try:
            user_response = supabase.auth.get_user(jwt)
            if not user_response.user:
                 return jsonify({"error": "Invalid or expired token."}), 401
        except Exception as e:
            logging.error(f"Token validation error: {e}")
            return jsonify({"error": "Token validation failed.", "details": str(e)}), 401
            
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    # Serve the main application page, which will handle auth state client-side
    return render_template('API Interface.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    username = data.get('username')

    if not email or not password or not username:
        return jsonify({"error": "Email, password, and username are required."}), 400

    try:
        res = supabase.auth.sign_up({
            "email": email, 
            "password": password,
            "options": {
                "data": { "username": username }
            }
        })
        return jsonify({"message": "Registration successful! Please check your email to confirm."}), 201
    except Exception as e:
        error_message = str(e)
        logging.error(f"Registration failed: {error_message}")
        return jsonify({"error": "Registration failed", "details": error_message}), 500


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return jsonify({ "access_token": res.session.access_token }), 200
    except Exception as e:
        error_message = str(e)
        logging.error(f"Login failed: {error_message}")
        return jsonify({"error": "Login failed", "details": error_message}), 401


@app.route("/api/logout", methods=['POST'])
@supabase_login_required
def api_logout():
    jwt = request.headers.get('Authorization').split(' ')[1]
    try:
        supabase.auth.sign_out(jwt)
        return jsonify({"message": "Logout successful."}), 200
    except Exception as e:
        return jsonify({"error": "Logout failed", "details": str(e)}), 500


@app.route('/api/past_sessions', methods=['GET'])
@supabase_login_required
def get_past_sessions():
    jwt = request.headers.get('Authorization').split(' ')[1]
    user = supabase.auth.get_user(jwt).user
    
    try:
        sessions_res = supabase.table('chat_session').select('*').eq('user_id', str(user.id)).order('start_time', desc=True).execute()
        
        past_sessions_data = []
        for session in sessions_res.data:
            preview = "No preview available."
            if session.get("history"):
                for item in session["history"]:
                    if item.get('role') == 'model' and item.get('parts') and item['parts'][0].get('text'):
                        preview = item['parts'][0]['text']
                        break
            past_sessions_data.append({
                "session_id": session.get("session_uuid"),
                "start_time": session.get("start_time"),
                "appliance_type": session.get("appliance_type"),
                "history_preview": preview
            })
        return jsonify(past_sessions_data), 200
    except Exception as e:
        logging.error(f"Error fetching past sessions for user {user.id}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve past sessions."}), 500


@app.route('/api/chat_history/<session_uuid>', methods=['GET'])
@supabase_login_required
def get_chat_history(session_uuid):
    jwt = request.headers.get('Authorization').split(' ')[1]
    user = supabase.auth.get_user(jwt).user
    
    try:
        session_res = supabase.table('chat_session').select('*').eq('session_uuid', session_uuid).eq('user_id', str(user.id)).single().execute()
        session = session_res.data
        return jsonify({
            "session_id": session.get("session_uuid"),
            "history": session.get("history", []),
            "appliance_type": session.get("appliance_type")
        }), 200
    except Exception as e:
        logging.error(f"Error fetching history for session {session_uuid}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve session history."}), 500


@app.route('/api/delete_session/<session_uuid>', methods=['DELETE'])
@supabase_login_required
def api_delete_session(session_uuid):
    jwt = request.headers.get('Authorization').split(' ')[1]
    user = supabase.auth.get_user(jwt).user
    try:
        delete_res = supabase.table('chat_session').delete().eq('session_uuid', session_uuid).eq('user_id', str(user.id)).execute()
        if not delete_res.data:
            return jsonify({"error": "Session not found or permission denied."}), 404
        logging.info(f"User {user.email} deleted session {session_uuid}.")
        return jsonify({"message": "Session deleted successfully."}), 200
    except Exception as e:
        logging.error(f"Error deleting session {session_uuid} for user {user.id}: {e}", exc_info=True)
        return jsonify({"error": "Could not delete session."}), 500


@app.route('/api/new_chat', methods=['POST'])
@supabase_login_required
def api_new_chat():
    jwt = request.headers.get('Authorization').split(' ')[1]
    user = supabase.auth.get_user(jwt).user
    
    if not gemini_api_client or (hasattr(gemini_api_client, 'api_key') and gemini_api_client.api_key == "DUMMY_KEY_IN_USE"):
        return jsonify({"error": "Cannot start chat, API client is DUMMY or uninitialized."}), 500
    
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid request: payload must be valid JSON."}), 400
        appliance_type = data.get('appliance_type', 'Unknown')
        insert_data = {'user_id': str(user.id), 'appliance_type': appliance_type, 'history': [] }
        new_session_res = supabase.table('chat_session').insert(insert_data).execute()
        new_session = new_session_res.data[0]
        logging.info(f"New DB chat session created with UUID: {new_session['session_uuid']} for user {user.email}")
        return jsonify({
            "message": "New chat session started in DB.", 
            "session_id": new_session['session_uuid'],
            "history": new_session['history']
        }), 200
    except Exception as e:
        logging.error(f"Error starting new chat session: {e}", exc_info=True)
        return jsonify({"error": f"Could not start new chat session: {str(e)}"}), 500

@app.route('/api/chat_message', methods=['POST'])
@supabase_login_required
def api_chat_message():
    jwt = request.headers.get('Authorization').split(' ')[1]
    user = supabase.auth.get_user(jwt).user
    
    media_bytes, media_mime_type = None, None
    if request.content_type.startswith('multipart/form-data'):
        session_id = request.form.get('session_id')
        prompt = request.form.get('prompt')
        media_file = request.files.get('media_file')
        if media_file and media_file.filename:
            filename = secure_filename(media_file.filename)
            media_bytes = media_file.read()
            media_mime_type = media_file.content_type or mimetypes.guess_type(filename)[0]
            logging.info(f"Received file: {filename}, MIME type: {media_mime_type}, Size: {len(media_bytes)} bytes")
    elif request.content_type.startswith('application/json'):
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid JSON input"}), 400
        session_id = data.get('session_id')
        prompt = data.get('prompt')
    else:
        return jsonify({"error": "Unsupported Content-Type"}), 415

    if not session_id or (prompt is None and not media_bytes):
        return jsonify({"error": "session_id and either prompt or a media file are required"}), 400
    prompt = prompt or ""

    try:
        session_res = supabase.table('chat_session').select('history').eq('session_uuid', session_id).eq('user_id', str(user.id)).single().execute()
        db_history = session_res.data.get('history', [])
    except Exception:
        return jsonify({"error": "Chat session not found or permission denied."}), 404

    if not gemini_api_client or (hasattr(gemini_api_client, 'api_key') and gemini_api_client.api_key == "DUMMY_KEY_IN_USE"):
        dummy_chat = gemini_api_client.start_chat_session()
        response = gemini_api_client.send_chat_message(dummy_chat, prompt)
        return jsonify({"generatedText": response.text, "history": [], "error": "Using DUMMY API."})

    try:
        gemini_chat = gemini_api_client.start_chat_session(history=db_history)
        response = gemini_api_client.send_chat_message(gemini_chat, prompt, media_bytes=media_bytes, media_mime_type=media_mime_type)

        history_list = [{'role': entry.role, 'parts': [{'text': part.text} for part in entry.parts if hasattr(part, 'text')]} for entry in gemini_chat.history if entry.parts]
        update_res = supabase.table('chat_session').update({'history': history_list}).eq('session_uuid', session_id).execute()

        if not update_res.data: raise Exception("Failed to update session history.")
        return jsonify({"generatedText": response.text, "history": update_res.data[0]['history']})
    except Exception as e:
        logging.error(f"Error in chat message for session {session_id}: {e}", exc_info=True)
        return jsonify({"error": f"An error occurred with the AI: {str(e)}"}), 500

if __name__ == '__main__':
    if not os.path.exists('templates'):
        os.makedirs('templates')
    source_html_path = 'API Interface.html'
    dest_html_path = os.path.join('templates', 'API Interface.html')
    if os.path.exists(source_html_path) and not os.path.exists(dest_html_path):
        import shutil
        shutil.move(source_html_path, dest_html_path)
    
    logging.info("Starting Flask app...")
    app.run(debug=True, host='0.0.0.0', port=5000) 