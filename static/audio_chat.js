// static/js/audio_chat.js
document.addEventListener("DOMContentLoaded", function () {
  const messageHistory = document.getElementById("message-history");
  const textForm = document.getElementById("text-form");
  const textInput = document.getElementById("text-input");
  const recordButton = document.getElementById("record-button");
  const audioPlayer = document.getElementById("audio-player");
  const connectionStatus = document.getElementById("connection-status");

  let ws;
  let mediaRecorder;
  let audioChunks = [];
  let isRecording = false;

  // Initialize WebSocket
  function initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/audio_chat/${sessionId}/`;

    ws = new WebSocket(wsUrl);

    ws.onopen = function () {
      console.log("WebSocket connected");
      connectionStatus.textContent = "Connected";
      loadMessageHistory();
    };

    ws.onclose = function () {
      console.log("WebSocket disconnected");
      connectionStatus.textContent = "Disconnected";
      setTimeout(initWebSocket, 5000); // Reconnect after 5 seconds
    };

    ws.onmessage = function (event) {
      if (typeof event.data === "string") {
        const data = JSON.parse(event.data);
        handleTextMessage(data);
      } else {
        // Handle binary audio data if needed
      }
    };

    ws.onerror = function (error) {
      console.error("WebSocket error:", error);
    };
  }

  // Load message history via DRF API
  function loadMessageHistory() {
    fetch(`/api/conversations/${sessionId}/messages/`)
      .then((response) => response.json())
      .then((messages) => {
        messageHistory.innerHTML = "";
        messages.forEach((msg) => {
          appendMessage(msg);
        });
      })
      .catch((error) => console.error("Error loading messages:", error));
  }

  // Handle incoming text messages
  function handleTextMessage(data) {
    if (data.type === "text_chunk") {
      const lastMessage = messageHistory.lastElementChild;
      if (lastMessage && lastMessage.classList.contains("assistant-message")) {
        lastMessage.textContent += data.content;
      } else {
        appendMessage({ text_response: data.content });
      }
    }
  }

  // Append message to the history
  function appendMessage(msg) {
    if (msg.text_input) {
      const userMsg = document.createElement("div");
      userMsg.className = "user-message";
      userMsg.textContent = msg.text_input;
      messageHistory.appendChild(userMsg);
    }

    if (msg.text_response) {
      const assistantMsg = document.createElement("div");
      assistantMsg.className = "assistant-message";
      assistantMsg.textContent = msg.text_response;
      messageHistory.appendChild(assistantMsg);
    }

    messageHistory.scrollTop = messageHistory.scrollHeight;
  }

  // Handle text form submission
  textForm.addEventListener("submit", function (e) {
    e.preventDefault();
    const text = textInput.value.trim();
    if (!text) return;

    appendMessage({ text_input: text });

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: "text_input",
          content: text,
        })
      );
    }

    textInput.value = "";
  });

  // Handle audio recording
  recordButton.addEventListener("click", async function () {
    if (!isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = function (event) {
          audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async function () {
          const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
          sendAudioToServer(audioBlob);
          stream.getTracks().forEach((track) => track.stop());
        };

        mediaRecorder.start();
        isRecording = true;
        recordButton.textContent = "Stop Recording";
      } catch (error) {
        console.error("Error starting recording:", error);
      }
    } else {
      if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        recordButton.textContent = "Start Recording";
      }
    }
  });

  // Send audio to server
  function sendAudioToServer(audioBlob) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    // First send metadata
    ws.send(
      JSON.stringify({
        type: "start_audio",
        length: audioBlob.size,
      })
    );

    // Then send the audio data in chunks
    const reader = new FileReader();
    reader.onload = function () {
      ws.send(reader.result);
      ws.send(JSON.stringify({ type: "end_audio" }));
    };
    reader.readAsArrayBuffer(audioBlob);
  }

  // Initialize the WebSocket connection
  initWebSocket();
});
