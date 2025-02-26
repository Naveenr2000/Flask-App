const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const audioElement = document.getElementById('audio');
const textToSpeechForm = document.getElementById('textToSpeechForm');
const textInput = document.getElementById('textInput');
const ttsAudio = document.getElementById('ttsAudio');
const timerDisplay = document.getElementById('timer');
const audioList = document.getElementById('audioList');
const transcriptionList = document.getElementById('transcriptionList');
const sentimentResultDisplay = document.getElementById('sentimentResult');  // New element to display sentiment

let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

// ✅ **Fixing Microphone Issue**: Use WebM format
recordButton.addEventListener('click', async () => {
    try {
        console.log("Requesting microphone access...");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" }); // ✅ WebM for better browser support

        audioChunks = [];
        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.start();
        startTime = Date.now();
        timerInterval = setInterval(() => {
            const elapsedTime = Math.floor((Date.now() - startTime) / 1000);
            timerDisplay.textContent = `Recording: ${formatTime(elapsedTime)}`;
        }, 1000);

        recordButton.disabled = true;
        stopButton.disabled = false;
        timerDisplay.textContent = "Recording...";

        console.log("Recording started...");
    } catch (error) {
        console.error('Microphone access denied:', error);
        alert('Microphone access denied. Please enable permissions.');
    }
});

// **Stop Recording & Upload**
stopButton.addEventListener('click', () => {
    if (!mediaRecorder) {
        console.error("No active mediaRecorder!");
        return;
    }

    mediaRecorder.stop();
    clearInterval(timerInterval);
    timerDisplay.textContent = "Processing...";

    mediaRecorder.onstop = async () => {
        console.log("Recording stopped, preparing upload...");

        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' }); // ✅ WebM format
        const formData = new FormData();
        formData.append('audio_data', audioBlob, 'recorded_audio.webm'); // ✅ WebM filename

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();

            if (data.file) {
                console.log("Upload successful:", data.file);

                // ✅ **Fix: Display Correct Converted MP3**
                const mp3File = data.file.replace('.wav', '.mp3').replace('.webm', '.mp3');
                const newAudioItem = document.createElement('li');
                newAudioItem.innerHTML = `
                    <audio controls>
                        <source src="/uploads/${mp3File}" type="audio/mp3">
                        Your browser does not support the audio element.
                    </audio>
                    <br>${mp3File}`;
                audioList.appendChild(newAudioItem);

                // ✅ **Fix: Display Transcription**
                if (data.transcription) {
                    const newTranscriptItem = document.createElement('li');
                    newTranscriptItem.innerHTML = `<a href="/uploads/${data.transcription}" target="_blank">${data.transcription}</a>`;
                    transcriptionList.appendChild(newTranscriptItem);
                }

                // ✅ **Display Sentiment**
                if (data.sentiment) {
                    sentimentResultDisplay.textContent = `Sentiment: ${data.sentiment}`;
                }

                // ✅ **Link to Download Sentiment Analysis File**
                const sentimentLink = document.createElement('a');
                sentimentLink.href = `/uploads/${data.sentiment_file}`;
                sentimentLink.target = '_blank';
                sentimentLink.textContent = 'Download Sentiment Analysis';
                sentimentResultDisplay.appendChild(sentimentLink);

                timerDisplay.textContent = "Recording saved!";
            } else {
                throw new Error('Upload failed');
            }
        } catch (error) {
            console.error('Error uploading audio:', error);
            alert('Failed to upload audio.');
        }
    };

    recordButton.disabled = false;
    stopButton.disabled = true;
});

// **Handle Text-to-Speech**
textToSpeechForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const text = textInput.value.trim();

    if (!text) {
        alert("Please enter text to convert to speech.");
        return;
    }

    try {
        const response = await fetch('/text_to_speech', {
            method: 'POST',
            body: new FormData(textToSpeechForm)
        });

        const data = await response.json();

        if (data.audio_file) {
            console.log("TTS success:", data.audio_file);
            ttsAudio.src = `/tts/${data.audio_file}`; // ✅ Fixed path to correct TTS folder
            ttsAudio.play();

            // ✅ **Display Sentiment from Text**
            if (data.sentiment) {
                sentimentResultDisplay.textContent = `Sentiment: ${data.sentiment}`;
            }

            // ✅ **Link to Download Sentiment Analysis File**
            const sentimentLink = document.createElement('a');
            sentimentLink.href = `/tts/${data.sentiment_file}`;
            sentimentLink.target = '_blank';
            sentimentLink.textContent = 'Download Sentiment Analysis';
            sentimentResultDisplay.appendChild(sentimentLink);

        } else {
            alert('Text-to-Speech conversion failed.');
        }
    } catch (error) {
        console.error('Text-to-Speech error:', error);
        alert('Failed to process Text-to-Speech.');
    }
});

// **Timer Format Helper**
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}
