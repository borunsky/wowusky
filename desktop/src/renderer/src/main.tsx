import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/theme.css";
import "./styles/screens.css";
import "./styles/responsive.css";

// Apply stored theme before first paint to avoid flash
const stored = localStorage.getItem("wowusky:theme") ?? "dark";
const resolved =
  stored === "system"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
    : stored;
document.documentElement.setAttribute("data-theme", resolved);
document.documentElement.setAttribute(
  "data-density",
  localStorage.getItem("wowusky:density") ?? "comfortable",
);

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");
createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
