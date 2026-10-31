// Keeps the latest result so /output survives a page refresh.
const STORAGE_KEY = "linkedin-post-generator:last-result";

export function saveResult(result) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(result));
  } catch {
    // Storage can be unavailable (private mode, blocked site data); navigation state still works.
  }
}

export function loadResult() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
