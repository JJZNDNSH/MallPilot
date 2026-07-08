// 做什么：定义前端会话存储键。
// 为什么：集中管理 localStorage 键名，避免不同文件写错。
const STORAGE_KEY = "mallpilot-web-conv-id";

// 做什么：读取或生成会话编号。
// 为什么：让用户刷新页面后还能延续同一轮导购上下文。
export function getOrCreateConversationId(): string {
  const storedId = window.localStorage.getItem(STORAGE_KEY);
  if (storedId) {
    return storedId;
  }

  const nextId = window.crypto.randomUUID();
  window.localStorage.setItem(STORAGE_KEY, nextId);
  return nextId;
}
