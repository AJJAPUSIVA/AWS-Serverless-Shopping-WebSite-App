/**
 * Assistant module - AI shopping assistant chat widget.
 */
const Assistant = (() => {
  let sessionId = null;
  let sending = false;

  const panel = () => document.getElementById("assistant-panel");
  const toggle = () => document.getElementById("assistant-toggle");
  const input = () => document.getElementById("assistant-input");
  const sendBtn = () => document.getElementById("assistant-send");
  const messagesEl = () => document.getElementById("assistant-messages");
  const notice = () => document.getElementById("assistant-signin-notice");

  function init() {
    // Enter key to send
    document.getElementById("assistant-input").addEventListener("keyup", (e) => {
      if (e.key === "Enter") send();
    });
    onAuthChange(Auth.isSignedIn());
  }

  function open() {
    panel().classList.remove("d-none");
    toggle().classList.add("d-none");
    input().focus();
  }

  function close() {
    panel().classList.add("d-none");
    toggle().classList.remove("d-none");
  }

  function onAuthChange(signedIn) {
    if (signedIn) {
      input().disabled = false;
      sendBtn().disabled = false;
      notice().classList.add("d-none");
    } else {
      input().disabled = true;
      sendBtn().disabled = true;
      notice().classList.remove("d-none");
      sessionId = null;
    }
  }

  function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `assistant-msg ${role}`;
    div.textContent = text;
    messagesEl().appendChild(div);
    messagesEl().scrollTop = messagesEl().scrollHeight;
  }

  async function send() {
    if (sending) return;
    const message = input().value.trim();
    if (!message || !Auth.isSignedIn()) return;

    appendMessage("user", message);
    input().value = "";
    sending = true;
    sendBtn().disabled = true;

    // Show typing indicator
    const typingEl = document.createElement("div");
    typingEl.className = "assistant-msg assistant text-muted";
    typingEl.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Thinking…';
    messagesEl().appendChild(typingEl);
    messagesEl().scrollTop = messagesEl().scrollHeight;

    try {
      const response = await Api.askAssistant(message, sessionId);
      sessionId = response.sessionId;
      typingEl.remove();
      appendMessage("assistant", response.message);

      // Refresh cart in case assistant modified it
      Cart.fetch();
    } catch (err) {
      typingEl.remove();
      appendMessage("assistant", "Sorry, the assistant is unavailable. Please try again.");
    } finally {
      sending = false;
      sendBtn().disabled = false;
      input().focus();
    }
  }

  return { init, open, close, send, onAuthChange };
})();
