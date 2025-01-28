import os
from google.cloud import speech, texttospeech
import librosa
import soundfile as sf
import noisereduce as nr
from werkzeug.utils import secure_filename
from flask import request,Flask, session, request, render_template, send_from_directory, jsonify, redirect
from datetime import datetime
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

app = Flask(__name__)
app.secret_key = 'AbcdEfgh1234'

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav', 'mp3'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Google Cloud credentials and API clients - 
# from google.oauth2 import service_account
# credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./project1-speech-to-text.json")
# credentials = service_account.Credentials.from_service_account_file(credentials_path)
# using IAM for deployement
from google.auth import default
from google.cloud import speech

credentials, project = default()

client = speech.SpeechClient(credentials=credentials)
speech_client = speech.SpeechClient(credentials=credentials)
text_to_speech_client = texttospeech.TextToSpeechClient(credentials=credentials)

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Index route
@app.route('/')
def index():
    if 'audio_files' not in session:
        session['audio_files'] = []
    if 'text_files' not in session:
        session['text_files'] = []
    return render_template('index.html', audio_files=session['audio_files'], text_files=session['text_files'])

# Route to upload and transcribe audio
@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        return 'No file part', 400
    file = request.files['audio_data']
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d-%I%M%S%p')}.mp3")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Save uploaded file
        try:
            file.save(file_path)
        except Exception as e:
            return jsonify({'error': f'Failed to save file: {e}'}), 500

        # # Perform noise reduction using librosa
        # try:
        #     # Load the audio file using librosa
        #     audio, sample_rate = librosa.load(file_path, sr=None)
        #     noise_sample = audio[:sample_rate]
            
        #     # Apply noise reduction (simple example using Spectral Subtraction)
        #     noise_reduced_audio = nr.reduce_noise(y=audio, sr=sample_rate, y_noise=noise_sample)

        #     # Save the noise-reduced audio back to the file path
        #     sf.write(file_path, noise_reduced_audio, sample_rate)
        # except Exception as e:
        #     return jsonify({'error': f'Noise reduction failed: {e}'}), 500
        # Perform speech-to-text
        try:
            with open(file_path, 'rb') as audio_file:
                content = audio_file.read()
            audio = speech.RecognitionAudio(content=content)
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                language_code="en-US"
            )
            response = speech_client.recognize(config=config, audio=audio)
            
            # Save transcription
            transcription = "\n".join(result.alternatives[0].transcript for result in response.results)
            transcription_file = f"{os.path.splitext(filename)[0]}.txt"
            transcription_path = os.path.join(app.config['UPLOAD_FOLDER'], transcription_file)
            with open(transcription_path, 'w') as f:
                f.write(transcription)

            # Update session
            session['audio_files'].append(filename)
            session['text_files'].append(transcription_file)
            
            return render_template('index.html', audio_files=session['audio_files'], text_files=session['text_files'])
        except Exception as e:
            return jsonify({'error': f'Speech-to-text failed: {e}'}), 500

    return jsonify({'error': 'Invalid file type'}), 400

# Route to convert text to speech
@app.route('/text_to_speech', methods=['POST'])
def text_to_speech():
    text = request.form.get('text')
    if not text:
        return 'No text provided', 400

    # Convert text to speech
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)

    try:
        response = text_to_speech_client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
        filename = secure_filename(f"tts_{datetime.now().strftime('%Y%m%d-%I%M%S%p')}.wav")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(file_path, 'wb') as out:
            out.write(response.audio_content)

        # Generate  transcription (or extract any relevant info if needed)
        transcription_file = f"{os.path.splitext(filename)[0]}.txt"
        transcription_path = os.path.join(app.config['UPLOAD_FOLDER'], transcription_file)
        with open(transcription_path, 'w') as f:
            f.write(f"Text-to-speech transcription for file: {filename}\n")
            f.write(f"Original text: {text}")

        # Update session
        session['audio_files'].append(filename)
        session['text_files'].append(transcription_file)
        
        return render_template('index.html', audio_files=session['audio_files'], text_files=session['text_files'])
    except Exception as e:
        return jsonify({'error': f'Text-to-speech failed: {e}'}), 500

    return redirect('/')

# Route to serve uploaded files
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    if filename.endswith('.wav'):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False, mimetype='audio/wav')
    elif filename.endswith('.mp3'):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=False, mimetype='audio/mpeg')
    else:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/convert_to_text', methods=['POST'])
def convert_to_text():
    # Assuming the last uploaded file is the recorded audio
    if not session.get('audio_files'):
        return jsonify({'error': 'No audio file to transcribe'}), 400

    audio_file = session['audio_files'][-1]  # Get the last uploaded file

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], audio_file)
    try:
        with open(file_path, 'rb') as audio_file_data:
            content = audio_file_data.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            language_code="en-US"
        )
        response = speech_client.recognize(config=config, audio=audio)

        # Extract transcription from response
        transcription = "\n".join(result.alternatives[0].transcript for result in response.results)

                # Create transcription file
        transcription_file = f"{os.path.splitext(audio_file)[0]}.txt"
        transcription_path = os.path.join(app.config['UPLOAD_FOLDER'], transcription_file)
        with open(transcription_path, 'w') as f:
            f.write(transcription)

        # Update session
        session['text_files'].append(transcription_file)

        # Return transcription as JSON
        return jsonify({'transcription': transcription})

    except Exception as e:
        return jsonify({'error': f'Error processing audio: {e}'}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
