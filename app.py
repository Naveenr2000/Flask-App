import os
import subprocess
import soundfile as sf
import noisereduce as nr
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, flash
from werkzeug.utils import secure_filename
from google.cloud import speech, texttospeech, language_v1
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ✅ Correctly set directories
UPLOAD_FOLDER = 'uploads'
TTS_FOLDER = 'tts'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TTS_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['TTS_FOLDER'] = TTS_FOLDER

# ✅ Initialize Google Cloud Clients
speech_client = speech.SpeechClient()
tts_client = texttospeech.TextToSpeechClient()
language_client = language_v1.LanguageServiceClient()

ALLOWED_EXTENSIONS = {'wav', 'mp3', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ✅ Convert WebM to WAV
def convert_webm_to_wav(input_path):
    output_path = input_path.replace('.webm', '.wav')
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-ac', '1', '-ar', '16000', output_path], check=True)
        os.remove(input_path)  # Remove WebM after conversion
        return output_path
    except Exception as e:
        print(f"❌ WebM to WAV conversion failed: {e}")
        return None

# ✅ Convert WAV to MP3
def convert_wav_to_mp3(input_path):
    output_path = input_path.replace('.wav', '.mp3')
    try:
        subprocess.run(['ffmpeg', '-i', input_path, '-ac', '1', '-ar', '16000', '-b:a', '128k', output_path], check=True)
        return output_path
    except Exception as e:
        print(f"❌ WAV to MP3 conversion failed: {e}")
        return None

# ✅ Noise Reduction Function
def reduce_noise(file_path):
    try:
        audio, sr = sf.read(file_path, dtype='float32')
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)  # Convert to mono
        denoised_audio = nr.reduce_noise(y=audio, sr=sr, y_noise=audio[:sr])  # First sec noise sample
        sf.write(file_path, denoised_audio, sr)
    except Exception as e:
        print(f"❌ Noise reduction failed: {e}")

# ✅ Sentiment Analysis Function
def analyze_sentiment(text):
    client = language_v1.LanguageServiceClient()

    # Construct the document
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)

    # Perform sentiment analysis
    sentiment = client.analyze_sentiment(request={'document': document})

    score = sentiment.document_sentiment.score
    magnitude = sentiment.document_sentiment.magnitude

    # Classify the sentiment based on score
    if score > 0.25:
        sentiment_label = "Positive"
    elif score < -0.25:
        sentiment_label = "Negative"
    else:
        sentiment_label = "Neutral"

    return sentiment_label, score, magnitude

# ✅ Upload & Convert Audio
@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return jsonify({'error': 'No audio file found'}), 400

    file = request.files['audio_data']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type or no file selected'}), 400

    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d-%I%M%S%p')}.webm")
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Convert WebM → WAV → MP3
    file_path = convert_webm_to_wav(file_path)
    if not file_path:
        return jsonify({'error': 'Failed to process audio'}), 500

    reduce_noise(file_path)
    mp3_path = convert_wav_to_mp3(file_path)
    if not mp3_path:
        return jsonify({'error': 'MP3 conversion failed'}), 500

    # Perform Speech-to-Text
    with open(file_path, 'rb') as audio_file:
        content = audio_file.read()
    audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US"
    )
    response = speech_client.recognize(config=config, audio=audio)

    if not response.results:
        return jsonify({'error': 'No speech detected'}), 500

    transcript = "\n".join(result.alternatives[0].transcript for result in response.results)
    transcript_file = file_path.replace('.wav', '.txt')
    with open(transcript_file, 'w') as f:
        f.write(transcript)

    # Perform Sentiment Analysis on the transcript
    sentiment_label, score, magnitude = analyze_sentiment(transcript)

    # Save the sentiment result
    sentiment_file = transcript_file.replace('.txt', '_sentiment.txt')
    with open(sentiment_file, 'w') as f:
        f.write(f"Text: {transcript}\n")
        f.write(f"Sentiment: {sentiment_label}\n")
        f.write(f"Score: {score}\n")
        f.write(f"Magnitude: {magnitude}\n")

    return jsonify({
        'file': os.path.basename(mp3_path),
        'transcription': os.path.basename(transcript_file),
        'sentiment': sentiment_label,
        'sentiment_file': os.path.basename(sentiment_file)
    }), 200

# ✅ Text-to-Speech (Fix Upload & Serve)
@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    text = request.form.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    # Perform Sentiment Analysis on the text
    sentiment_label, score, magnitude = analyze_sentiment(text)

    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

    response = tts_client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)

    output_filename = f"tts_{datetime.now().strftime('%Y%m%d-%I%M%S%p')}.mp3"
    output_path = os.path.join(TTS_FOLDER, output_filename)

    with open(output_path, 'wb') as output_file:
        output_file.write(response.audio_content)

    # Save the sentiment result
    sentiment_file = output_filename.replace('.mp3', '_sentiment.txt')
    with open(os.path.join(TTS_FOLDER, sentiment_file), 'w') as f:
        f.write(f"Text: {text}\n")
        f.write(f"Sentiment: {sentiment_label}\n")
        f.write(f"Score: {score}\n")
        f.write(f"Magnitude: {magnitude}\n")

    return jsonify({'audio_file': output_filename, 'sentiment_file': sentiment_file})

# ✅ Serve Audio from Correct Paths
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/tts/<filename>')
def tts_file(filename):
    return send_from_directory(TTS_FOLDER, filename)

# ✅ Home Page
@app.route('/')
def index():
    audio_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('.mp3')]
    text_files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith('.txt')]
    tts_files = [f for f in os.listdir(TTS_FOLDER) if f.endswith('.mp3')]
    return render_template('index.html', audio_files=audio_files, text_files=text_files, tts_files=tts_files)

if __name__ == '__main__':
    app.run(debug=True)
