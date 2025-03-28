import os
import subprocess
import soundfile as sf
import noisereduce as nr
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

# Vertex AI imports (for single-call transcription & sentiment analysis)
import vertexai
from vertexai.generative_models import GenerativeModel, Part

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Set up directories (TTS folder removed as it's not needed)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize Vertex AI with your project details.
# This project_id must match the "project_id" in your credentials JSON.
project_id = 'project1-speech-to-text'
vertexai.init(project=project_id, location="us-central1")
# Use the Gemini model for transcription & sentiment analysis
model = GenerativeModel("gemini-1.5-flash-001")

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'webm'}

def allowed_file(filename):
    """Return True if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Convert WebM to WAV using FFmpeg
def convert_webm_to_wav(input_path):
    output_path = input_path.replace('.webm', '.wav')
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-ac', '1', '-ar', '16000', output_path], check=True)
        os.remove(input_path)  # Remove original WebM after conversion
        return output_path
    except Exception as e:
        print(f"❌ WebM to WAV conversion failed: {e}")
        return None

# Convert WAV to MP3 using FFmpeg
def convert_wav_to_mp3(input_path):
    output_path = input_path.replace('.wav', '.mp3')
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-ac', '1', '-ar', '16000', '-b:a', '128k', output_path], check=True)
        return output_path
    except Exception as e:
        print(f"❌ WAV to MP3 conversion failed: {e}")
        return None

# Apply noise reduction using noisereduce
def reduce_noise(file_path):
    try:
        audio, sr = sf.read(file_path, dtype='float32')
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)  # Convert stereo to mono
        denoised_audio = nr.reduce_noise(y=audio, sr=sr, y_noise=audio[:sr])  # Use first second for noise sample
        sf.write(file_path, denoised_audio, sr)
    except Exception as e:
        print(f"❌ Noise reduction failed: {e}")

# Upload & Process Audio with Vertex AI (Single-call Transcription + Sentiment Analysis)
@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio file found'}), 400

    file = request.files['audio_data']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type or no file selected'}), 400

    # Save uploaded file as WebM
    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d-%I%M%S%p')}.webm")
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Convert WebM -> WAV
    wav_path = convert_webm_to_wav(file_path)
    if not wav_path:
        return jsonify({'error': 'WebM to WAV conversion failed'}), 500

    # Apply noise reduction (optional)
    reduce_noise(wav_path)

    # Convert WAV -> MP3 (for playback)
    mp3_path = convert_wav_to_mp3(wav_path)
    if not mp3_path:
        return jsonify({'error': 'WAV to MP3 conversion failed'}), 500

    # --- Single-call Vertex AI LLM API ---
    try:
        with open(wav_path, 'rb') as f:
            audio_bytes = f.read()

        # Define the prompt instructing the model to return transcript and sentiment
        prompt = """
Please provide an exact transcript for the audio, followed by sentiment analysis.

Your response should follow the format:

Text: USERS SPEECH TRANSCRIPTION

Sentiment Analysis: positive|neutral|negative
"""
        # Create a Part from the audio bytes
        audio_part = Part.from_data(audio_bytes, mime_type="audio/wav")
        contents = [audio_part, prompt]

        # Call the Vertex AI Gemini model (single API call)
        response = model.generate_content(contents)
        print("[INFO] LLM response:", response.text)

        # Parse the response to extract the transcript and sentiment
        transcript_line, sentiment_line = "", ""
        for line in response.text.splitlines():
            if line.startswith("Text:"):
                transcript_line = line.replace("Text:", "").strip()
            elif line.startswith("Sentiment Analysis:"):
                sentiment_line = line.replace("Sentiment Analysis:", "").strip()

        # Combine transcription and sentiment into one history file
        history_file = wav_path.replace('.wav', '_history.txt')
        with open(history_file, 'w') as f:
            f.write("Transcript:\n" + transcript_line + "\n\n")
            f.write("Sentiment Analysis:\n" + sentiment_line + "\n")

        return jsonify({
            'file': os.path.basename(mp3_path),
            'history_file': os.path.basename(history_file)
        }), 200

    except Exception as e:
        print(f"❌ Vertex AI processing failed: {e}")
        return jsonify({'error': 'Vertex AI processing failed'}), 500

# Serve files (audio & history) from the uploads folder
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Home Page: Lists recorded audio files and history files
@app.route('/')
def index():
    audio_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('.mp3')]
    history_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('_history.txt')]
    return render_template('index.html', audio_files=audio_files, history_files=history_files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
