import type {
  CatalogSearchRequest,
  CatalogSearchResponse,
  ChatRequest,
  ChatResponse,
  HealthResponse,
  OrderLookupRequest,
  OrderLookupResponse,
} from "../types/api";

// 做什么：统一前端请求的 API 根地址。
// 为什么：让本地开发和后续环境切换都只改一处配置。
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");

// 做什么：统一发起 HTTP 请求并处理错误。
// 为什么：避免每个接口都重复写状态判断与 JSON 解析逻辑。
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  // 做什么：优先返回后端错误文本。
  // 为什么：让页面提示更接近真实失败原因，而不是笼统的请求异常。
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `请求失败: ${response.status}`);
  }

  return (await response.json()) as T;
}

// 做什么：获取服务健康信息。
// 为什么：顶部状态条需要确认后端是否在线以及数据规模。
export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

// 做什么：发送聊天请求。
// 为什么：这是导购台的核心交互入口。
export function sendChat(body: ChatRequest): Promise<ChatResponse> {
  return requestJson<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// 做什么：发起商品结构化搜索。
// 为什么：侧栏和工具区都需要直接检索商品事实。
export function searchCatalog(body: CatalogSearchRequest): Promise<CatalogSearchResponse> {
  return requestJson<CatalogSearchResponse>("/catalog/search", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// 做什么：发起订单查询。
// 为什么：订单追踪工具需要直接获取订单事实。
export function lookupOrder(body: OrderLookupRequest): Promise<OrderLookupResponse> {
  return requestJson<OrderLookupResponse>("/orders/lookup", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
