const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
export async function sendMessage(message, history = []) {
const res = await fetch(`${API_BASE}/chat`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ message, history }),
});
if (!res.ok) throw new Error(`HTTP ${res.status}`);
return res.json();
}
export async function getAuditLogs(limit = 50) {
const res = await fetch(`${API_BASE}/audit/logs?limit=${limit}`);
if (!res.ok) throw new Error(`HTTP ${res.status}`);
return res.json();
}
export async function getMetrics() {
const res = await fetch(`${API_BASE}/metrics`);
if (!res.ok) throw new Error(`HTTP ${res.status}`);
return res.json();
}
export async function getPendingRequests() {
const res = await fetch(`${API_BASE}/hitl/pending`);
if (!res.ok) throw new Error(`HTTP ${res.status}`);
return res.json();
}
export async function decideRequest(id, decision, reason = "") {
const res = await fetch(`${API_BASE}/hitl/decide`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ request_id: id, decision, reason }),
});
if (!res.ok) throw new Error(`HTTP ${res.status}`);
return res.json();
}