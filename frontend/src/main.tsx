import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/noto-sans-sc/400.css";
import "@fontsource/noto-sans-sc/500.css";
import "@fontsource/noto-sans-sc/700.css";
import "@fontsource/barlow-condensed/400.css";
import "@fontsource/barlow-condensed/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import App from "./App";
import "./styles/index.css";

// 做什么：挂载 React 应用。
// 为什么：把 /frontend 页面入口稳定绑定到 root 节点。
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
