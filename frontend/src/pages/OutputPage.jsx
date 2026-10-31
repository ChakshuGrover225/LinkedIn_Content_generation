import { useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import Markdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import { loadResult } from "../lastResult.js";

// remark-breaks keeps the single line breaks LinkedIn-style posts rely on.
const remarkPlugins = [remarkGfm, remarkBreaks];

function MarkdownBlock({ children }) {
  return <Markdown remarkPlugins={remarkPlugins}>{children}</Markdown>;
}

export default function OutputPage() {
  const location = useLocation();
  const result = location.state?.result ?? loadResult();
  const postRef = useRef(null);
  const [copyState, setCopyState] = useState("idle");

  if (!result) {
    return (
      <section className="card empty-state">
        <h1>No post yet</h1>
        <p className="subtitle">Generate a post first and it will show up here.</p>
        <Link to="/home" className="button">
          Write a post
        </Link>
      </section>
    );
  }

  async function handleCopy() {
    try {
      // Copy the rendered text, not the markdown source: LinkedIn shows **asterisks** literally.
      await navigator.clipboard.writeText(postRef.current.innerText);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
    setTimeout(() => setCopyState("idle"), 2000);
  }

  const copyLabel = { idle: "Copy post", copied: "Copied!", failed: "Copy failed" }[copyState];

  return (
    <div className="output">
      <div className="output-header">
        <div>
          <p className="eyebrow">Topic</p>
          <h1 className="topic">{result.topic}</h1>
        </div>
        <div className="actions">
          <button type="button" className="button" onClick={handleCopy}>
            {copyLabel}
          </button>
          <Link to="/home" className="button secondary">
            New post
          </Link>
        </div>
      </div>

      <article className="card post">
        <p className="eyebrow">Final post</p>
        <div className="markdown" ref={postRef}>
          <MarkdownBlock>{result.revised}</MarkdownBlock>
        </div>
      </article>

      <details className="card collapsible">
        <summary>First draft</summary>
        <div className="markdown">
          <MarkdownBlock>{result.draft}</MarkdownBlock>
        </div>
      </details>

      <details className="card collapsible">
        <summary>Critic&apos;s feedback</summary>
        <div className="markdown">
          <MarkdownBlock>{result.critique}</MarkdownBlock>
        </div>
      </details>
    </div>
  );
}
