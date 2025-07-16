from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import logging
import uuid # For generating unique session IDs
from werkzeug.utils import secure_filename # For handling filenames securely
import mimetypes # For guessing MIME types
import bcrypt
from datetime import datetime

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# Attempt to import the GeminiFlashAPI class and initialize it globally
gemini_api_client = None
try:
    from API_Interface import GeminiFlashAPI
    logging.info("Successfully imported GeminiFlashAPI from API_Interface.py")
    # Initialize the client globally, relying on API_Interface.py to use .env
    # and its new default model "gemini-2.0-flash"
    gemini_api_client = GeminiFlashAPI() 
    logging.info(f"Global GeminiFlashAPI client initialized successfully with model: {gemini_api_client.model_name} and API key: {gemini_api_client.api_key[:5]}...")
except ImportError as e:
    logging.error(f"CRITICAL_IMPORT_ERROR: Could not import GeminiFlashAPI from API_Interface.py: {e}. "
                  "The application WILL NOT connect to the actual Gemini API. Check for circular dependencies or file path issues.")
except ValueError as ve:
    logging.error(f"CRITICAL_CONFIG_ERROR: ValueError during global GeminiFlashAPI initialization (likely API key issue): {ve}. "
                  "Ensure GOOGLE_API_KEY is set correctly in your .env file.")
except Exception as ex:
    logging.error(f"CRITICAL_INIT_ERROR: An unexpected error occurred during global GeminiFlashAPI initialization: {ex}")

# Fallback to a dummy class ONLY if gemini_api_client is still None after attempts
if gemini_api_client is None:
    logging.warning("FALLBACK_TO_DUMMY_API: Global GeminiFlashAPI client failed to initialize. Using a DUMMY version.")
    class DummyGeminiAPI: # Renamed to avoid conflict if real one is also named GeminiFlashAPI
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
        
        # Add dummy chat methods to the DummyGeminiAPI
        def start_chat_session(self, history=None):
            logger.info(f"DUMMY_API_LOG: Starting a new dummy chat session.")
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
                            self.parts = [text] # Simulate a part existing
                            self.prompt_feedback = None
                    return DummyChatResponse(response_text)
            return DummyChatSession()
        
        def send_chat_message(self, chat_session, message_text, stream=False):
            logger.info(f"DUMMY_API_LOG: Sending message to dummy chat session: '{message_text}'")
            return chat_session.send_message(message_text, stream=stream)

    gemini_api_client = DummyGeminiAPI() # Assign the dummy instance to the global client

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_key_that_should_be_changed')

# --- Database Configuration (Handles both Replit/Postgres and local/SQLite) ---
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgres'):
    # Use PostgreSQL on Replit or other production environments
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
    logging.info("Connecting to PostgreSQL database.")
else:
    # Fallback to SQLite for local development
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'site.db')
    logging.info("DATABASE_URL not found or not a Postgres DB. Falling back to local SQLite database.")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login' # The route to redirect to for login
login_manager.login_message_category = 'info'


# --- Database Models ---

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    chat_sessions = db.relationship('ChatSession', backref='author', lazy=True)

    def set_password(self, password):
        # Hash password with bcrypt
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        # Check hashed password
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    history = db.Column(db.JSON, nullable=False, default=list) # Storing chat history as JSON
    appliance_type = db.Column(db.String(50), nullable=True)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('API Interface.html')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html') # We will create this file

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists. Please choose a different one.', 'warning')
            return redirect(url_for('register'))
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html') # We will create this file

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/past_sessions', methods=['GET'])
@login_required
def get_past_sessions():
    """
    API endpoint to retrieve all past chat sessions for the logged-in user.
    """
    try:
        sessions = ChatSession.query.filter_by(user_id=current_user.id).order_by(ChatSession.start_time.desc()).all()
        
        past_sessions_data = []
        for session in sessions:
            past_sessions_data.append({
                "session_id": session.session_uuid,
                "start_time": session.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "appliance_type": session.appliance_type,
                "history_preview": session.history[0]['parts'][0]['text'] if session.history and session.history[0]['parts'] and session.history[0]['parts'][0].get('text') else "No preview available."
            })
            
        return jsonify(past_sessions_data), 200
    except Exception as e:
        logging.error(f"Error fetching past sessions for user {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve past sessions."}), 500

@app.route('/api/chat_history/<session_uuid>', methods=['GET'])
@login_required
def get_chat_history(session_uuid):
    """
    API endpoint to retrieve the full history of a specific chat session.
    """
    try:
        session = ChatSession.query.filter_by(session_uuid=session_uuid, user_id=current_user.id).first()
        
        if not session:
            return jsonify({"error": "Session not found or permission denied."}), 404
            
        return jsonify({
            "session_id": session.session_uuid,
            "history": session.history,
            "appliance_type": session.appliance_type
        }), 200
    except Exception as e:
        logging.error(f"Error fetching history for session {session_uuid}: {e}", exc_info=True)
        return jsonify({"error": "Could not retrieve session history."}), 500

@app.route('/api/delete_session/<session_uuid>', methods=['DELETE'])
@login_required
def api_delete_session(session_uuid):
    """
    API endpoint to delete a specific chat session.
    """
    try:
        session = ChatSession.query.filter_by(session_uuid=session_uuid, user_id=current_user.id).first()
        
        if not session:
            return jsonify({"error": "Session not found or permission denied."}), 404
        
        db.session.delete(session)
        db.session.commit()
        
        logging.info(f"User {current_user.username} deleted session {session_uuid}.")
        return jsonify({"message": "Session deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting session {session_uuid} for user {current_user.id}: {e}", exc_info=True)
        return jsonify({"error": "Could not delete session."}), 500


@app.route('/api/new_chat', methods=['POST'])
@login_required
def api_new_chat():
    if not gemini_api_client or (hasattr(gemini_api_client, 'api_key') and gemini_api_client.api_key == "DUMMY_KEY_IN_USE"):
        return jsonify({"error": "Cannot start chat, API client is DUMMY or uninitialized.", "session_id": None}), 500
    try:
        # --- MODIFIED LOGIC ---
        data = request.get_json()
        if not data:
            logging.error("API_NEW_CHAT_ERROR: Request body is not JSON or is empty.")
            return jsonify({"error": "Invalid request: payload must be valid JSON.", "session_id": None}), 400

        appliance_type = data.get('appliance_type', 'Unknown')

        new_chat_session = ChatSession(
            user_id=current_user.id,
            appliance_type=appliance_type,
            history=[] # Start with empty history
        )
        db.session.add(new_chat_session)
        db.session.commit()

        logging.info(f"New DB chat session created with ID: {new_chat_session.id} (UUID: {new_chat_session.session_uuid}) for user {current_user.username}")

        # The 'chat_session' from Gemini API is now managed per-message, not stored long-term
        return jsonify({
            "message": "New chat session started in DB.", 
            "session_id": new_chat_session.session_uuid, # Use the UUID for client-side tracking
            "history": new_chat_session.history
        }), 200

    except Exception as e:
        logging.error(f"Error starting new chat session: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": f"Could not start new chat session: {str(e)}", "session_id": None}), 500

@app.route('/api/chat_message', methods=['POST'])
@login_required
def api_chat_message():
    # Check if the request is multipart (for file uploads) or JSON
    if request.content_type.startswith('multipart/form-data'):
        session_id = request.form.get('session_id')
        prompt = request.form.get('prompt')
        media_file = request.files.get('media_file')
        media_bytes = None
        media_mime_type = None

        if media_file and media_file.filename:
            filename = secure_filename(media_file.filename)
            media_bytes = media_file.read()
            # Try to guess MIME type from filename, or use what the browser sent
            media_mime_type = media_file.content_type 
            if not media_mime_type or media_mime_type == 'application/octet-stream': # Fallback if browser sends generic type
                guessed_type, _ = mimetypes.guess_type(filename)
                if guessed_type:
                    media_mime_type = guessed_type
            logging.info(f"Received file: {filename}, MIME type: {media_mime_type}, Size: {len(media_bytes)} bytes")
        else:
            logging.info("No media file uploaded or filename is empty.")

    elif request.content_type.startswith('application/json'):
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON input"}), 400
        session_id = data.get('session_id')
        prompt = data.get('prompt')
        # No media file expected for JSON requests in this setup
        media_bytes = None
        media_mime_type = None
    else:
        return jsonify({"error": "Unsupported Content-Type"}), 415

    if not session_id or (prompt is None and media_bytes is None): # Prompt can be empty if media is present
        return jsonify({"error": "session_id and either prompt or a media file are required"}), 400
    
    # Ensure prompt is at least an empty string if None and media is present, to avoid issues with API_Interface
    if prompt is None and media_bytes is not None:
        prompt = ""
    elif prompt is None: # This case should be caught by the check above, but as a safeguard
        return jsonify({"error": "Prompt is required if no media is sent"}), 400

    # --- NEW LOGIC: Get chat from DB ---
    db_chat_session = ChatSession.query.filter_by(session_uuid=session_id, user_id=current_user.id).first()

    if not db_chat_session:
        return jsonify({"error": "Chat session not found or you do not have permission to access it."}), 404

    # Handle DUMMY API client case
    if not gemini_api_client or (hasattr(gemini_api_client, 'api_key') and gemini_api_client.api_key == "DUMMY_KEY_IN_USE"):
        if hasattr(gemini_api_client, 'send_chat_message'):
            # The dummy API is stateless and doesn't use the database session.
            dummy_chat_session = gemini_api_client.start_chat_session()
            response = gemini_api_client.send_chat_message(dummy_chat_session, prompt)
            return jsonify({"generatedText": response.text, "history": [], "error": "Using DUMMY API for chat."})
        return jsonify({"error": "API client is DUMMY or uninitialized for chat.", "history": []}), 500

    # Real API client interaction
    try:
        # Create Gemini session from DB history INSIDE the try-catch block
        gemini_chat_session = gemini_api_client.start_chat_session(history=db_chat_session.history)

        response = gemini_api_client.send_chat_message(
            gemini_chat_session,
            prompt,
            media_bytes=media_bytes,
            media_mime_type=media_mime_type
        )

        # Now update the DB with a robust, serialized version of the history
        history_list = []
        for entry in gemini_chat_session.history:
            parts_list = []
            # We only care about parts that have text content for our history
            for part in entry.parts:
                if hasattr(part, 'text') and part.text:
                    parts_list.append({'text': part.text})
            
            # Only add the message to our history if it has valid text parts
            if parts_list:
                history_list.append({'role': entry.role, 'parts': parts_list})

        db_chat_session.history = history_list
        db.session.commit()

        serializable_history = db_chat_session.history

        return jsonify({"generatedText": response.text, "history": serializable_history})
    except ValueError as ve:
        logging.error(f"ValueError sending chat message in session {session_id}: {ve}", exc_info=True)
        return jsonify({"error": f"Input error: {str(ve)}", "history": []}), 400
    except Exception as e:
        logging.error(f"Error sending chat message in session {session_id}: {e}", exc_info=True)
        return jsonify({"error": f"An error occurred while communicating with the AI: {str(e)}", "history": []}), 500

if __name__ == '__main__':
    # Ensure 'templates' directory exists for Flask
    if not os.path.exists('templates'):
        os.makedirs('templates')
        logging.info("Created 'templates' directory.")

    # Helper: Move 'API Interface.html' to 'templates' if it exists in the root
    source_html_path = 'API Interface.html'
    dest_html_path = os.path.join('templates', 'API Interface.html')
    if os.path.exists(source_html_path) and not os.path.exists(dest_html_path):
        import shutil
        try:
            shutil.move(source_html_path, dest_html_path)
            logging.info(f"Moved '{source_html_path}' to '{dest_html_path}'.")
        except Exception as e:
            logging.error(f"Could not move '{source_html_path}' to '{dest_html_path}': {e}")
    elif not os.path.exists(dest_html_path):
        logging.warning(f"'{dest_html_path}' not found. Please ensure 'API Interface.html' is in the 'templates' folder.")
    
    with app.app_context():
        db.create_all() # Creates the database tables from the models

    logging.info("Starting Flask app on http://127.0.0.1:5000")
    app.run(debug=True, port=5000) 