// Select DOM elements
const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const convertToTextButton = document.getElementById('convertToText');
const audioElement = document.getElementById('audio');
const textToSpeechButton = document.getElementById('textToSpeech');
const textInput = document.getElementById('textInput');
const progressBar = document.getElementById('progressBar');
const timerDisplay = document.getElementById('timer');

let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

// Format time for the timer
function formatTime(time) {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

// Request microphone permissions and start recording
async function startRecording() {
    try {
        // Request microphone permission
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);

        // Create and apply lowpass filter for noise reduction
        const filter = audioContext.createBiquadFilter();
        filter.type = "lowpass";
        filter.frequency.value = 5000;

        source.connect(filter);
        filter.connect(audioContext.destination);

        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.start();

        startTime = Date.now();
        let elapsedTime = 0;
        timerInterval = setInterval(() => {
            elapsedTime = Math.floor((Date.now() - startTime) / 1000);
            timerDisplay.textContent = formatTime(elapsedTime);

            // Update progress bar
            const progress = Math.min(elapsedTime / 60, 1); // 1 minute max recording
            progressBar.style.width = `${progress * 100}%`;
        }, 1000);

        mediaRecorder.ondataavailable = e => {
            audioChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            clearInterval(timerInterval); // Stop the timer
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const formData = new FormData();
            formData.append('audio_data', audioBlob, 'recorded_audio.wav');

            // Upload the audio file to the server
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                location.reload(); // Refresh to show updated files
            })
            .catch(error => {
                console.error('Error uploading audio:', error);
                alert('There was an issue uploading the audio. Please try again.');
            });
        };
    } catch (error) {
        // Handle errors, e.g., permission denied or microphone access issues
        if (error.name === 'PermissionDeniedError') {
            alert('Permission to access the microphone was denied. Please allow microphone access and try again.');
        } else {
            console.error('Error accessing microphone:', error);
            alert('Unable to access your microphone. Please check your permissions.');
        }
    }
}

// Start recording when the record button is clicked
recordButton.addEventListener('click', () => {
    startRecording();
    recordButton.disabled = true;
    stopButton.disabled = false;
    convertToTextButton.disabled = true;
});

// Stop recording when the stop button is clicked
stopButton.addEventListener('click', () => {
    if (mediaRecorder) {
        mediaRecorder.stop();
    }

    recordButton.disabled = false;
    stopButton.disabled = true;
    convertToTextButton.disabled = false;
});

// Handle text-to-speech conversion
textToSpeechButton.addEventListener('click', () => {
    const text = textInput.value.trim();
    if (!text) {
        alert("Please enter some text.");
        return;
    }

    // Show loading state
    textToSpeechButton.disabled = true;
    textToSpeechButton.textContent = 'Converting...';

    fetch('/text_to_speech', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: text })
    })
    .then(response => response.blob())
    .then(audioBlob => {
        // Play the generated audio
        const audioUrl = URL.createObjectURL(audioBlob);
        console.log('Audio URL:', audioUrl);
        audioElement.src = audioUrl;
        audioElement.play();
    })
    .catch(error => {
        console.error('Error during text-to-speech conversion:', error);
    })
    .finally(() => {
        // Reset button text and state
        textToSpeechButton.disabled = false;
        textToSpeechButton.textContent = 'Convert to Audio';
    });
});
// Handle convert to text (transcribe recorded audio)
convertToTextButton.addEventListener('click', () => {
    fetch('/convert_to_text', {
        method: 'POST',
    })
    .then(response => response.json())
    .then(data => {
        if (data.transcription) {
            alert('Transcription: ' + data.transcription);
        } else {
            alert('No transcription available.');
        }
    })
    .catch(error => {
        console.error('Error during transcription:', error);
        alert('There was an issue with transcription. Please try again.');
    });
});