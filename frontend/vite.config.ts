import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 做什么：导出 Vite 配置。
// 为什么：让 /frontend 目录可以作为独立前端工程直接运行和构建。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
  },
});
