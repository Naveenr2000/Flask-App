import os
import subprocess
import soundfile as sf
import noisereduce as nr
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import fitz  
import uuid

# Vertex AI imports for transcription and LLM tasks
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Google Cloud Text-to-Speech import
from google.cloud import texttospeech

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a proper secret key in production
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Path to store conversation history
CONVO_HISTORY_FILE = os.path.join(UPLOAD_FOLDER, "conversation_history.txt")

# Initialize Vertex AI with your project details
project_id = 'project1-speech-to-text'  # update with your project ID
vertexai.init(project=project_id, location="us-central1")
# Use the Gemini model (adjust model name if needed)
model = GenerativeModel("gemini-1.5-flash-001")

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'webm', 'pdf'}

def allowed_file(filename):
    """Return True if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_webm_to_wav(input_path):
    output_path = input_path.replace('.webm', '.wav')
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-ac', '1', '-ar', '16000', output_path], check=True)
        os.remove(input_path)  
        return output_path
    except Exception as e:
        print(f" WebM to WAV conversion failed: {e}")
        return None

def convert_wav_to_mp3(input_path):
    output_path = input_path.replace('.wav', '.mp3')
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-ac', '1', '-ar', '16000', '-b:a', '128k', output_path], check=True)
        return output_path
    except Exception as e:
        print(f" WAV to MP3 conversion failed: {e}")
        return None

def reduce_noise(file_path):
    try:
        audio, sr = sf.read(file_path, dtype='float32')
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)  # Convert to mono if needed
        denoised_audio = nr.reduce_noise(y=audio, sr=sr, y_noise=audio[:sr])
        sf.write(file_path, denoised_audio, sr)
    except Exception as e:
        print(f" Noise reduction failed: {e}")

def extract_pdf_text(pdf_path):
    """Extract text from a PDF file using PyMuPDF."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

# Setting the Global variable to hold the book text once uploaded
book_text = ""

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    global book_text
    if 'bookPdf' not in request.files:
        return "No file part", 400
    pdf_file = request.files['bookPdf']
    if pdf_file.filename == '':
        return "No selected file", 400
    if not allowed_file(pdf_file.filename):
        return "Invalid file type", 400

    pdf_filename = secure_filename(pdf_file.filename)
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], pdf_filename)
    pdf_file.save(pdf_path)
    
    # Extracting the text from the uploaded PDF
    book_text = extract_pdf_text(pdf_path)
    return "PDF uploaded and parsed successfully!", 200

def text_to_speech(text, output_folder=UPLOAD_FOLDER):
    """Convert the given text to speech (MP3) using Google Cloud TTS."""
    client = texttospeech.TextToSpeechClient()
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    mp3_filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
    mp3_path = os.path.join(output_folder, mp3_filename)
    with open(mp3_path, 'wb') as out:
        out.write(response.audio_content)
    return mp3_path

def save_conversation(question, answer):
    """Append the current Q&A pair with a timestamp to the history file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"{timestamp}\nQuestion: {question}\nAnswer: {answer}\n--------\n"
    with open(CONVO_HISTORY_FILE, 'a') as f:
        f.write(entry)

@app.route('/ask_book', methods=['POST'])
def ask_book():
    global book_text
    if not book_text:
        return jsonify({'error': 'Please upload a PDF book first.'}), 400
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio file found'}), 400

    audio_file = request.files['audio_data']
    if audio_file.filename == '' or not allowed_file(audio_file.filename):
        return jsonify({'error': 'Invalid file type or no file selected'}), 400

    # Saving the recorded audio as WebM
    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d-%I%M%S%p')}.webm")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    audio_file.save(file_path)

    # Converting the WebM to WAV for processing
    wav_path = convert_webm_to_wav(file_path)
    if not wav_path:
        return jsonify({'error': 'WebM to WAV conversion failed'}), 500
    reduce_noise(wav_path)

    # Transcribing the audio question using Vertex AI
    try:
        with open(wav_path, 'rb') as f:
            audio_bytes = f.read()
        transcribe_prompt = """
        Please provide a verbatim English transcript of the following audio:
        """
        audio_part = Part.from_data(audio_bytes, mime_type="audio/wav")
        contents = [audio_part, transcribe_prompt]
        transcribe_response = model.generate_content(contents)
        transcribed_question = transcribe_response.text.strip()
    except Exception as e:
        print(f" Transcription failed: {e}")
        return jsonify({'error': 'Vertex AI transcription failed'}), 500

    # Building the prompt combining the book text and the transcribed question
    try:
        prompt = f"""
        The following is the content of a book:
        BOOK CONTENT START:
        {book_text}
        BOOK CONTENT END.

        The user asked:
        "{transcribed_question}"

        Please provide an informative and concise answer based solely on the book's content.
        """
        prompt_part = Part.from_text(prompt)
        answer_response = model.generate_content([prompt_part])
        answer_text = answer_response.text.strip()
    except Exception as e:
        print(f"Book question processing failed: {e}")
        return jsonify({'error': 'Vertex AI book question failed'}), 500

    # Saving  the conversation (Q&A) to history
    save_conversation(transcribed_question, answer_text)

    # Converting the answer text to speech
    try:
        tts_path = text_to_speech(answer_text)
    except Exception as e:
        print(f"TTS failed: {e}")
        return jsonify({'error': 'Text-to-Speech conversion failed'}), 500

    return jsonify({
        'transcribed_question': transcribed_question,
        'answer_text': answer_text,
        'tts_file': os.path.basename(tts_path)
    }), 200

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    # Loading the conversation history from file (if exists) to display on the home page
    conversation_history = []
    if os.path.exists(CONVO_HISTORY_FILE):
        with open(CONVO_HISTORY_FILE, 'r') as f:
            raw_data = f.read().strip()
            if raw_data:
                # Spliting the entries based on the delimiter '--------'
                conversation_history = [entry.strip() for entry in raw_data.split("--------") if entry.strip()]
    return render_template('index.html', conversation_history=conversation_history)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
