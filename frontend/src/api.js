// Empty in dev (Vite proxies /api). Set VITE_API_BASE_URL at build time when the API lives on another origin.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export async function generatePost(topic) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic }),
    });
  } catch {
    throw new Error("Could not reach the backend. Is the FastAPI server running?");
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(errorMessage(body) ?? `Request failed with status ${response.status}.`);
  }
  return body;
}

function errorMessage(body) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return null;
}
