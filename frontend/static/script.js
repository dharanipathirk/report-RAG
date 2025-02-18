/**
 * This script manages the chat UI, file uploads, and communication with backend API endpoints.
 */

const container = document.querySelector(".container");
const chatsContainer = document.querySelector(".chats-container");
const promptForm = document.querySelector(".prompt-form");
const promptInput = promptForm.querySelector(".prompt-input");
const fileInput = promptForm.querySelector("#file-input");
const fileUploadWrapper = promptForm.querySelector(".file-upload-wrapper");
const useReportBtn = document.getElementById("use-report-btn");

const CHAT_API_URL = `${window.APP_CONFIG.API_BASE}/api/chat`;
const EMBED_API_URL = `${window.APP_CONFIG.API_BASE}/api/upload-pdf`;
const CUSTOM_PDF_QUERY_API_URL = `${window.APP_CONFIG.API_BASE}/api/custom-pdf-query`;
const REPORT_QUERY_API_URL = `${window.APP_CONFIG.API_BASE}/api/report-query`;

let controller, typingInterval;
const chatHistory = [];
const userData = { message: "", file: {} };
let chatStarted = false;

/**
 * Performs a fetch request with credentials and reloads the page if unauthorized.
 * @param {string} url - The URL to fetch.
 * @param {object} [options={}] - Fetch options.
 * @returns {Promise<Response>} The fetch response.
 * @throws Will throw an error if the response status is 401.
 */
async function authorizedFetch(url, options = {}) {
  options.credentials = 'include';
  const response = await fetch(url, options);
  if (response.status === 401) {
    window.location.reload();
    throw new Error("Unauthorized");
  }
  return response;
}

/**
 * Creates a new message element with specified content and CSS classes.
 * @param {string} content - The inner HTML content of the message.
 * @param {...string} classes - Additional CSS classes.
 * @returns {HTMLElement} The created message element.
 */
const createMessageElement = (content, ...classes) => {
  const div = document.createElement("div");
  div.classList.add("message", ...classes);
  div.innerHTML = content;
  return div;
};

/**
 * Scrolls the main container to the bottom smoothly.
 */
const scrollToBottom = () =>
  container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });

/**
 * Simulates typing effect and appends images after completion.
 * @param {string} text - Answer text.
 * @param {HTMLElement} textElement - Element to display text.
 * @param {HTMLElement} botMsgDiv - Bot message container.
 * @param {Function} [onComplete] - Callback after typing finishes.
 */
const typingEffect = (text, textElement, botMsgDiv, onComplete) => {
  textElement.textContent = "";
  const words = text.split(" ");
  let wordIndex = 0;

  typingInterval = setInterval(() => {
    if (wordIndex < words.length) {
      textElement.textContent += (wordIndex === 0 ? "" : " ") + words[wordIndex++];
      scrollToBottom();
    } else {
      clearInterval(typingInterval);
      const rawMarkdown = textElement.textContent;
      const parsedHtml = marked.parse(rawMarkdown);
      const cleanHtml = DOMPurify.sanitize(parsedHtml);
      textElement.innerHTML = cleanHtml;
      hljs.highlightAll();
      botMsgDiv.classList.remove("loading");
      document.body.classList.remove("bot-responding");
      if (onComplete) onComplete(); // Execute post-typing actions
    }
  }, 40);
};

/**
 * Opens a modal to view images with zoom capability.
 * @param {string} imageData - Base64 encoded image.
 */
const openImageViewer = (imageData) => {
  const modal = document.createElement("div");
  modal.className = "image-viewer-modal";

  const img = document.createElement("img");
  img.src = `data:image/png;base64,${imageData}`;
  img.className = "zooming-image";

  modal.appendChild(img);
  document.body.appendChild(modal);

  // Close modal on background click
  modal.addEventListener("click", (e) => {
    if (e.target === modal) document.body.removeChild(modal);
  });

  // Zoom with mouse wheel
  let scale = 1;
  img.addEventListener("wheel", (e) => {
    e.preventDefault();
    scale += e.deltaY * -0.01;
    scale = Math.min(Math.max(0.1, scale), 4);
    img.style.transform = `scale(${scale})`;
  });
};

/**
 * Generates a bot response by sending the chat history to the API.
 * Streams the response and displays it with a typing effect.
 * @param {HTMLElement} botMsgDiv - The bot message container element.
 */
const generateResponse = async (botMsgDiv) => {
  const textElement = botMsgDiv.querySelector(".message-text");
  controller = new AbortController();

  // Add user's message to the chat history.
  chatHistory.push({
    role: "user",
    content: userData.message,
  });

  try {
    // Fetch the streaming response from the backend.
    let response = await authorizedFetch(CHAT_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatHistory }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = `Server error: ${response.status}`;
      throw new Error(errorText);
    }

    // Read the streamed response in chunks.
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let responseText = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      responseText += decoder.decode(value);
    }

    // Animate the fully assembled response.
    typingEffect(responseText, textElement, botMsgDiv);

    // Add the bot response to chat history.
    chatHistory.push({
      role: "assistant",
      content: responseText,
    });
  } catch (error) {
    if (error.name === "AbortError") {
      textElement.textContent = "Response generation stopped.";
    } else {
      textElement.textContent = error.message;
    }
    textElement.style.color = "#d62939";
    botMsgDiv.classList.remove("loading");
    document.body.classList.remove("bot-responding");
    scrollToBottom();
  } finally {
    // Clear file data after sending.
    userData.file = {};
  }
};

/**
 * Generates a bot response using a custom PDF RAG endpoint.
 * Uses the uploaded PDF's context to generate an answer.
 * @param {HTMLElement} botMsgDiv - The bot message container element.
 */
const generateCustomPdfRAGResponse = async (botMsgDiv) => {
  const textElement = botMsgDiv.querySelector(".message-text");
  controller = new AbortController();

  chatHistory.push({
    role: "user",
    content: userData.message,
  });

  try {
    // Prepare payload for the custom PDF query.
    let response = await authorizedFetch(CUSTOM_PDF_QUERY_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages: chatHistory,
        file_name: userData.file.fileName
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    // Process the JSON response containing the answer.
    const data = await response.json();
    const { answer, highlighted_images } = data;
    chatHistory.push({
      role: "assistant",
      content: answer,
    });
    typingEffect(answer, textElement, botMsgDiv, () => {
      if (highlighted_images?.length) {
        highlighted_images.forEach((imgData) => {
          const imgWrapper = document.createElement("div");
          imgWrapper.className = "image-attachment";

          const img = document.createElement("img");
          img.src = `data:image/png;base64,${imgData}`;
          img.alt = "Highlighted section";
          img.className = "highlighted-image-thumbnail";

          img.addEventListener("click", () => openImageViewer(imgData));
          imgWrapper.appendChild(img);
          botMsgDiv.appendChild(imgWrapper);
        });
      }
    });
  } catch (error) {
    if (error.name === "AbortError") {
      textElement.textContent = "Response generation stopped.";
    } else {
      textElement.textContent = error.message;
    }
    textElement.style.color = "#d62939";
    botMsgDiv.classList.remove("loading");
    document.body.classList.remove("bot-responding");
    scrollToBottom();
  } finally {
    // Clear PDF file data after processing.
    userData.file = {};
  }
};

/**
 * Generates a bot response using the report RAG endpoint.
 * @param {HTMLElement} botMsgDiv - The bot message container element.
 */
const generateReportRAGResponse = async (botMsgDiv) => {
  const textElement = botMsgDiv.querySelector(".message-text");
  controller = new AbortController();

  chatHistory.push({
    role: "user",
    content: userData.message,
  });

  try {
    let response = await authorizedFetch(REPORT_QUERY_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatHistory }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const data = await response.json();
    const { answer, highlighted_images } = data;
    chatHistory.push({
      role: "assistant",
      content: answer,
    });
    typingEffect(answer, textElement, botMsgDiv, () => {
      if (highlighted_images?.length) {
        highlighted_images.forEach((imgData) => {
          const imgWrapper = document.createElement("div");
          imgWrapper.className = "image-attachment";

          const img = document.createElement("img");
          img.src = `data:image/png;base64,${imgData}`;
          img.alt = "Highlighted section";
          img.className = "highlighted-image-thumbnail";

          img.addEventListener("click", () => openImageViewer(imgData));
          imgWrapper.appendChild(img);
          botMsgDiv.appendChild(imgWrapper);
        });
      }
    });
  } catch (error) {
    if (error.name === "AbortError") {
      textElement.textContent = "Response generation stopped.";
    } else {
      textElement.textContent = error.message;
    }
    textElement.style.color = "#d62939";
    botMsgDiv.classList.remove("loading");
    document.body.classList.remove("bot-responding");
    scrollToBottom();
  } finally {
    userData.file = {};
  }
};

/**
 * Handles the chat prompt form submission.
 * Validates input, updates the UI, and triggers the appropriate bot response.
 * @param {Event} e - The form submission event.
 */
const handleFormSubmit = (e) => {
  e.preventDefault();
  const userMessage = promptInput.value.trim();
  if (!userMessage || document.body.classList.contains("bot-responding")) return;

  if (!chatStarted) {
    chatStarted = true;
    useReportBtn.disabled = true;
    fileInput.disabled = true;
    const addFileBtn = promptForm.querySelector("#add-file-btn");
    if (addFileBtn) addFileBtn.disabled = true;
  }

  userData.message = userMessage;
  promptInput.value = "";
  document.body.classList.add("chats-active", "bot-responding");
  fileUploadWrapper.classList.remove("file-attached", "img-attached", "active");

  // Generate user message HTML with optional file attachment.
  const userMsgHTML = `
    <p class="message-text"></p>
    ${userData.file.data
      ? userData.file.isImage
        ? `<img src="data:${userData.file.mime_type};base64,${userData.file.data}" class="img-attachment" />`
        : `<p class="file-attachment"><span class="material-symbols-rounded">description</span>${userData.file.fileName}</p>`
      : ""
    }
  `;

  const userMsgDiv = createMessageElement(userMsgHTML, "user-message");
  userMsgDiv.querySelector(".message-text").textContent = userData.message;
  chatsContainer.appendChild(userMsgDiv);
  scrollToBottom();

  setTimeout(() => {
    // Add a temporary bot message while waiting for the response.
    const botMsgHTML = `
      <img class="avatar" src="/static/chat-icon.svg" />
      <div class="message-text">Just a sec...</div>
    `;
    const botMsgDiv = createMessageElement(botMsgHTML, "bot-message", "loading");
    chatsContainer.appendChild(botMsgDiv);
    scrollToBottom();

    if (useReportBtn.classList.contains("active")) {
      generateReportRAGResponse(botMsgDiv);
    } else if (userData.file && userData.file.fileName) {
      generateCustomPdfRAGResponse(botMsgDiv);
    } else {
      generateResponse(botMsgDiv);
    }
  }, 600);
};

// File input change handler for PDF uploads.
fileInput.addEventListener("change", () => {
  if (chatStarted) return;
  const file = fileInput.files[0];
  if (!file) return;

  // Only allow PDF files.
  if (file.type !== "application/pdf") {
    alert("Only PDF files are allowed. Please select a PDF.");
    fileInput.value = "";
    return;
  }

  const reader = new FileReader();
  reader.readAsDataURL(file);

  reader.onload = async (e) => {
    fileInput.value = "";
    const base64String = e.target.result.split(",")[1];
    fileUploadWrapper.classList.add("active", "file-attached");
    // Store file data.
    userData.file = {
      fileName: file.name,
      data: base64String,
      mime_type: file.type,
      isImage: false,
    };

    useReportBtn.classList.remove("active");
    useReportBtn.disabled = true;

    // OPTIONAL: Immediately embed the PDF.
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await authorizedFetch(EMBED_API_URL, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        console.error("Embedding error:", err);
        return;
      }
      const data = await res.json();
      console.log("PDF embeddings:", data);
    } catch (err) {
      console.error("Error embedding PDF:", err);
    }
  };
});

// Cancel file upload.
document.querySelector("#cancel-file-btn").addEventListener("click", () => {
  if (chatStarted) return;
  userData.file = {};
  fileUploadWrapper.classList.remove("file-attached", "img-attached", "active");
  useReportBtn.disabled = false;
});

// Stop the bot response.
document.querySelector("#stop-response-btn").addEventListener("click", () => {
  controller?.abort();
  userData.file = {};
  clearInterval(typingInterval);
  const loadingBotMsg = chatsContainer.querySelector(".bot-message.loading");
  if (loadingBotMsg) loadingBotMsg.classList.remove("loading");
  document.body.classList.remove("bot-responding");
});

// Delete all chats and reset the UI.
document.querySelector("#delete-chats-btn").addEventListener("click", () => {
  chatHistory.length = 0;
  chatsContainer.innerHTML = "";
  document.body.classList.remove("chats-active", "bot-responding");
  chatStarted = false;
  fileInput.disabled = false;
  useReportBtn.disabled = false;
  const addFileBtn = promptForm.querySelector("#add-file-btn");
  if (addFileBtn) addFileBtn.disabled = false;
});

/**
 * Handles suggestion item clicks by setting the prompt input and triggering form submission.
 */
document.querySelectorAll(".suggestions-item").forEach((suggestion) => {
  suggestion.addEventListener("click", () => {
    promptInput.value = suggestion.querySelector(".text").textContent;
    promptForm.dispatchEvent(new Event("submit"));
  });
});

/**
 * Toggles mobile prompt controls based on user clicks.
 */
document.addEventListener("click", ({ target }) => {
  const wrapper = document.querySelector(".prompt-wrapper");
  const shouldHide =
    target.classList.contains("prompt-input") ||
    (wrapper.classList.contains("hide-controls") &&
      (target.id === "add-file-btn" || target.id === "stop-response-btn"));
  wrapper.classList.toggle("hide-controls", shouldHide);
});

// Attach event listeners for form submission and file input activation.
promptForm.addEventListener("submit", handleFormSubmit);
promptForm.querySelector("#add-file-btn").addEventListener("click", () => {
  if (!chatStarted) fileInput.click();
});

if (useReportBtn) {
  useReportBtn.addEventListener("click", () => {
    if (chatStarted) return;
    useReportBtn.classList.toggle("active");
    // If "Use Report" is enabled, clear any PDF file data.
    if (useReportBtn.classList.contains("active")) {
      userData.file = {};
      fileUploadWrapper.classList.remove("file-attached", "img-attached", "active");
      fileInput.value = "";
      useReportBtn.disabled = false;
    }
  });
}
