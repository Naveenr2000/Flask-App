const recordButton = document.getElementById('record');
const stopButton = document.getElementById('stop');
const timerDisplay = document.getElementById('timer');
const answerList = document.getElementById('answerList'); // List where answers will be appended

let mediaRecorder;
let audioChunks = [];
let startTime;
let timerInterval;

recordButton.addEventListener('click', async () => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
        audioChunks = [];
        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };
        mediaRecorder.start();
        startTime = Date.now();
        timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            timerDisplay.textContent = `Recording: ${formatTime(elapsed)}`;
        }, 1000);
        recordButton.disabled = true;
        stopButton.disabled = false;
        timerDisplay.textContent = "Recording...";
    } catch (error) {
        console.error("Microphone access denied:", error);
        alert("Microphone access denied. Please enable permissions.");
    }
});

stopButton.addEventListener('click', () => {
    if (!mediaRecorder) return;
    mediaRecorder.stop();
    clearInterval(timerInterval);
    timerDisplay.textContent = "Processing...";
    mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        const formData = new FormData();
        formData.append('audio_data', audioBlob, 'recorded_audio.webm');
        try {
            const response = await fetch('/ask_book', { method: 'POST', body: formData });
            const data = await response.json();
            if (data.tts_file) {
                const li = document.createElement('li');
                li.innerHTML = `
                    <p><strong>Your Question:</strong> ${data.transcribed_question}</p>
                    <p><strong>Answer:</strong> ${data.answer_text}</p>
                    <audio controls>
                        <source src="/uploads/${data.tts_file}" type="audio/mp3">
                        Your browser does not support the audio element.
                    </audio>
                `;
                answerList.appendChild(li);
                timerDisplay.textContent = "Question answered!";
            } else {
                throw new Error("No TTS file returned.");
            }
        } catch (error) {
            console.error("Error processing question:", error);
            alert("Failed to process book question.");
        }
    };
    recordButton.disabled = false;
    stopButton.disabled = true;
});

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}
