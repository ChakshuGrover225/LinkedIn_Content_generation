import { useState } from "react";
import { useNavigate } from "react-router";
import { generatePost } from "../api.js";
import { saveResult } from "../lastResult.js";

// Mirrors MAX_TOPIC_LENGTH in backend/app/schemas.py.
const MAX_TOPIC_LENGTH = 2000;

export default function HomePage() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const canSubmit = topic.trim().length > 0 && !loading;

  async function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    setError(null);
    try {
      const result = await generatePost(topic.trim());
      saveResult(result);
      navigate("/output", { state: { result } });
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }

  function handleKeyDown(event) {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.currentTarget.form.requestSubmit();
    }
  }

  return (
    <section className="card">
      <h1>Turn an idea into a LinkedIn post</h1>
      <p className="subtitle">
        Describe a topic. A writer drafts it, a critic reviews it, and an editor polishes the final post.
      </p>

      <form onSubmit={handleSubmit} className="topic-form">
        <label htmlFor="topic" className="label">
          Topic
        </label>
        <textarea
          id="topic"
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={MAX_TOPIC_LENGTH}
          rows={5}
          placeholder="e.g. What I learned deploying my first FastAPI app on AWS EC2"
          disabled={loading}
          autoFocus
        />
        <div className="form-footer">
          <span className="hint">
            {topic.length}/{MAX_TOPIC_LENGTH} · Ctrl+Enter to submit
          </span>
          <button type="submit" className="button" disabled={!canSubmit}>
            {loading ? "Generating…" : "Generate post"}
          </button>
        </div>
      </form>

      {loading && (
        <p className="status" role="status">
          <span className="spinner" aria-hidden="true" />
          Drafting, critiquing and revising. This can take up to a minute.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
