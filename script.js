const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const timerDisplay = document.getElementById('timer');
const audioList = document.getElementById('audioList');
const historyList = document.getElementById('historyList');

let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

// Start Recording Audio
recordButton.addEventListener('click', async () => {
    try {
        console.log("Requesting microphone access...");
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
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

// Stop Recording & Upload
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
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio_data', audioBlob, 'recorded_audio.webm');

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            const data = await response.json();

            if (data.file) {
                console.log("Upload successful:", data.file);

                // Use the returned file name to display the MP3 file
                const mp3File = data.file.replace('.wav', '.mp3').replace('.webm', '.mp3');
                const newAudioItem = document.createElement('li');
                newAudioItem.innerHTML = `
                    <audio controls>
                        <source src="/uploads/${mp3File}" type="audio/mp3">
                        Your browser does not support the audio element.
                    </audio>
                    <br>${mp3File}`;
                audioList.appendChild(newAudioItem);

                // Display the combined history file (transcription & sentiment)
                if (data.history_file) {
                    const newHistoryItem = document.createElement('li');
                    newHistoryItem.innerHTML = `<a href="/uploads/${data.history_file}" target="_blank">${data.history_file}</a>`;
                    historyList.appendChild(newHistoryItem);
                }

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

// Helper function to format elapsed time
function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}
