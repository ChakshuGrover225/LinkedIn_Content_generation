import { Link, Navigate, Route, Routes } from "react-router";
import HomePage from "./pages/HomePage.jsx";
import OutputPage from "./pages/OutputPage.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/home" className="brand">
          <span className="brand-dot" aria-hidden="true" />
          LinkedIn Post Generator
        </Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/output" element={<OutputPage />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </main>
    </div>
  );
}
