const API_BASE = "http://127.0.0.1:8000";

const chatLog = document.getElementById("chatLog");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");

const diffBox = document.getElementById("diffBox");
const testBox = document.getElementById("testBox");

const modalBackdrop = document.getElementById("modalBackdrop");
const permissionModal = document.getElementById("permissionModal");
const commandBox = document.getElementById("commandBox");
const approveBtn = document.getElementById("approveBtn");
const denyBtn = document.getElementById("denyBtn");

let sessionId = null;
let pendingPermission = null; // { request_id, command }

function addMsg(role, text) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showPermissionModal(command, requestId) {
  pendingPermission = { request_id: requestId, command };
  commandBox.textContent = command;
  modalBackdrop.classList.remove("hidden");
  permissionModal.classList.remove("hidden");
}

function hidePermissionModal() {
  pendingPermission = null;
  modalBackdrop.classList.add("hidden");
  permissionModal.classList.add("hidden");
}

async function ensureSession() {
  if (sessionId) return sessionId;
  const res = await fetch(`${API_BASE}/session`, { method: "POST" });
  const data = await res.json();
  sessionId = data.session_id;
  addMsg("agent", "Session started. Describe a bug to begin.");
  return sessionId;
}

async function sendChat(text) {
  await ensureSession();
  addMsg("user", text);

  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message: text })
  });

  const data = await res.json();

  if (data.type === "permission_request") {
    addMsg("agent", data.agent_message);
    if (data.diff) diffBox.textContent = data.diff;
    if (data.test_output) testBox.textContent = data.test_output;
    showPermissionModal(data.command, data.request_id);
    return;
  }

  addMsg("agent", data.agent_message);

  if (data.diff) diffBox.textContent = data.diff;
  if (data.test_output) testBox.textContent = data.test_output;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = "";
  await sendChat(text);
});

approveBtn.addEventListener("click", async () => {
  if (!pendingPermission) return;
  const { request_id } = pendingPermission;
  hidePermissionModal();

  const res = await fetch(`${API_BASE}/permission/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, request_id, approved: true })
  });
  const data = await res.json();

  addMsg("agent", data.agent_message);
  if (data.diff) diffBox.textContent = data.diff;
  if (data.test_output) testBox.textContent = data.test_output;
});

denyBtn.addEventListener("click", async () => {
  if (!pendingPermission) return;
  const { request_id } = pendingPermission;
  hidePermissionModal();

  const res = await fetch(`${API_BASE}/permission/respond`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, request_id, approved: false })
  });
  const data = await res.json();

  addMsg("agent", data.agent_message);
  if (data.diff) diffBox.textContent = data.diff;
  if (data.test_output) testBox.textContent = data.test_output;
});

// Auto-start
ensureSession().catch((e) => {
  addMsg("agent", "Failed to start session. Is backend running on :8000?");
  console.error(e);
});
