const container = document.querySelector(".container");
const chatsContainer = document.querySelector(".chats-container");
const promptForm = document.querySelector(".prompt-form");
const promptInput = promptForm.querySelector(".prompt-input");
const fileInput = promptForm.querySelector("#file-input");
const fileUploadWrapper = promptForm.querySelector(".file-upload-wrapper");
const useReportBtn = document.getElementById("use-report-btn");



const CHAT_API_URL = `${window.APP_CONFIG.API_BASE}/api/chat`;
const EMBED_API_URL = `${window.APP_CONFIG.API_BASE}/api/upload-pdf`;
const QUERY_API_URL = `${window.APP_CONFIG.API_BASE}/api/query`;

let controller, typingInterval;
const chatHistory = [];
const userData = { message: "", file: {} };


async function authorizedFetch(url, options = {}) {
  options.credentials = 'include';

  const response = await fetch(url, options);

  if (response.status === 401) {
    window.location.reload();
    throw new Error("Unauthorized");
  }
  return response;
}

// Function to create message elements
const createMessageElement = (content, ...classes) => {
  const div = document.createElement("div");
  div.classList.add("message", ...classes);
  div.innerHTML = content;
  return div;
};

// Scroll to the bottom of the container
const scrollToBottom = () =>
  container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });

// Simulate typing effect for bot responses
const typingEffect = (text, textElement, botMsgDiv) => {
  textElement.textContent = "";
  const words = text.split(" ");
  let wordIndex = 0;

  typingInterval = setInterval(() => {
    if (wordIndex < words.length) {
      textElement.textContent += (wordIndex === 0 ? "" : " ") + words[wordIndex++];
      scrollToBottom();
    } else {
      clearInterval(typingInterval);
      // Parse Markdown and sanitize HTML
      const rawMarkdown = textElement.textContent;
      const parsedHtml = marked.parse(rawMarkdown);
      const cleanHtml = DOMPurify.sanitize(parsedHtml);
      textElement.innerHTML = cleanHtml;
      hljs.highlightAll();
      botMsgDiv.classList.remove("loading");
      document.body.classList.remove("bot-responding");
    }
  }, 40);
};

// Make the API call and generate the bot's response (streaming from local)
const generateResponse = async (botMsgDiv) => {
  const textElement = botMsgDiv.querySelector(".message-text");
  controller = new AbortController();

  // Keep track of chat history in your UI, if desired
  chatHistory.push({
    role: "user",
    content: userData.message,
  });

  try {
    // Fetch the streaming response from the FastAPI backend
    let response = await authorizedFetch(CHAT_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt: userData.message }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = `Server error: ${response.status}`;
      throw new Error(errorText);
    }

    // Read the streamed response in chunks
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");

    let responseText = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      responseText += decoder.decode(value);
    }

    // Animate the fully assembled response
    typingEffect(responseText, textElement, botMsgDiv);

    // Add the bot response to chat history
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
    // Clear any file data after sending
    userData.file = {};
  }
};


// RAG Response Generator (when a PDF file is attached)
// This function calls the /query endpoint which retrieves context from the PDF.
const generateRAGResponse = async (botMsgDiv) => {
  const textElement = botMsgDiv.querySelector(".message-text");
  controller = new AbortController();

  try {
    // We assume the user message is the query for the PDF context.
    // Send the query as form data.
    const formData = new FormData();
    formData.append("query", userData.message);

    let response = await authorizedFetch(QUERY_API_URL, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    // The /query endpoint returns JSON with "answer" and (optionally) "context_used"
    const data = await response.json();
    const answer = data.answer;
    typingEffect(answer, textElement, botMsgDiv);
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
    // Clear file data after sending so subsequent queries use chat unless a new PDF is uploaded.
    userData.file = {};
  }
};



// Handle the form submission
const handleFormSubmit = (e) => {
  e.preventDefault();
  const userMessage = promptInput.value.trim();
  if (!userMessage || document.body.classList.contains("bot-responding")) return;

  userData.message = userMessage;
  promptInput.value = "";
  document.body.classList.add("chats-active", "bot-responding");
  fileUploadWrapper.classList.remove("file-attached", "img-attached", "active");

  // Generate user message HTML with optional file attachment
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
    // Generate bot message HTML and add in the chat container
    const botMsgHTML = `
      <img class="avatar" src="/static/chat-icon.svg" />
      <div class="message-text">Just a sec...</div>
    `;
    const botMsgDiv = createMessageElement(botMsgHTML, "bot-message", "loading");
    chatsContainer.appendChild(botMsgDiv);
    scrollToBottom();
    // If a PDF file has been attached, use RAG. Otherwise, use plain chat.
    if (userData.file && userData.file.fileName) {
      generateRAGResponse(botMsgDiv);
    } else {
      generateResponse(botMsgDiv);
    }
  }, 600);
};

// Handle file input change (file upload)
fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  if (!file) return;

  // Simple check for PDF
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
    // Show a PDF icon or something as a preview, if you like:
    fileUploadWrapper.classList.add("active", "file-attached");
    // Store file data in userData
    userData.file = {
      fileName: file.name,
      data: base64String,
      mime_type: file.type,
      isImage: false,  // Not an image
    };

    useReportBtn.classList.remove("active");
    useReportBtn.disabled = true;

    // OPTIONAL: Immediately call the embedding endpoint
    //           to demonstrate usage.
    try {
      const formData = new FormData();
      formData.append("file", file);

      // Call the /embed-pdf endpoint
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
      console.log("PDF embeddings:", data.embeddings);
      // You can store or process the embeddings as needed.

    } catch (err) {
      console.error("Error embedding PDF:", err);
    }
  };
});


// Cancel file upload
document.querySelector("#cancel-file-btn").addEventListener("click", () => {
  userData.file = {};
  fileUploadWrapper.classList.remove("file-attached", "img-attached", "active");
  useReportBtn.disabled = false;
});

// Stop Bot Response
document.querySelector("#stop-response-btn").addEventListener("click", () => {
  controller?.abort();
  userData.file = {};
  clearInterval(typingInterval);
  const loadingBotMsg = chatsContainer.querySelector(".bot-message.loading");
  if (loadingBotMsg) loadingBotMsg.classList.remove("loading");
  document.body.classList.remove("bot-responding");
});

// Delete all chats
document.querySelector("#delete-chats-btn").addEventListener("click", () => {
  chatHistory.length = 0;
  chatsContainer.innerHTML = "";
  document.body.classList.remove("chats-active", "bot-responding");
});

// Handle suggestions click
document.querySelectorAll(".suggestions-item").forEach((suggestion) => {
  suggestion.addEventListener("click", () => {
    promptInput.value = suggestion.querySelector(".text").textContent;
    promptForm.dispatchEvent(new Event("submit"));
  });
});

// Show/hide controls for mobile on prompt input focus
document.addEventListener("click", ({ target }) => {
  const wrapper = document.querySelector(".prompt-wrapper");
  const shouldHide =
    target.classList.contains("prompt-input") ||
    (wrapper.classList.contains("hide-controls") &&
      (target.id === "add-file-btn" || target.id === "stop-response-btn"));
  wrapper.classList.toggle("hide-controls", shouldHide);
});

// Add event listeners for form submission and file input click
promptForm.addEventListener("submit", handleFormSubmit);
promptForm.querySelector("#add-file-btn").addEventListener("click", () => fileInput.click());

if (useReportBtn) {
  useReportBtn.addEventListener("click", () => {
    // Toggle an "active" state on the button
    useReportBtn.classList.toggle("active");

    // Check if the button is now "on" (active)
    if (useReportBtn.classList.contains("active")) {
      // Placeholder: Execute functionality for when the button is turned on
      console.log("use-report-btn is ON.");
    } else {
      // Placeholder: Execute functionality for when the button is turned off
      console.log("use-report-btn is OFF.");
    }
  });
}
