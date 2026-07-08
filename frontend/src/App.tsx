import { useEffect, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { DecisionPanel } from "./components/DecisionPanel";
import { StatusBar } from "./components/StatusBar";
import { StructuredTools } from "./components/StructuredTools";
import { fetchHealth, lookupOrder, searchCatalog, sendChat } from "./lib/api";
import { getOrCreateConversationId } from "./lib/session";
import type { HealthResponse } from "./types/api";
import type {
  ConversationMessage,
  DecisionMode,
  OrderPanelState,
  OrderSearchFormState,
  ProductPanelState,
  ProductSearchFormState,
} from "./types/ui";

// 做什么：定义默认用户标识。
// 为什么：后端需要稳定 user_id 才能关联会话和上下文。
const DEFAULT_USER_ID = "web_user";

// 做什么：提供首批快捷示例。
// 为什么：让用户一进页面就能触发仓库里的真实导购和订单场景。
const QUICK_PROMPTS = [
  "预算 3000，想买续航好的手机",
  "耳机怎么选，通勤和降噪优先",
  "订单 MP20260706001 到哪了",
  "订单 MP20260706005 现在是什么售后状态",
];

// 做什么：创建欢迎消息。
// 为什么：避免页面初始为空，让用户一进来就理解系统职责。
function createWelcomeMessage(): ConversationMessage {
  return {
    id: window.crypto.randomUUID(),
    role: "system",
    content: "欢迎来到 MallPilot。左边聊需求，右边看事实；商品和订单结果都会固定显示，避免回答跑偏。",
  };
}

// 做什么：创建默认商品侧栏状态。
// 为什么：让状态初始化保持集中且可复用。
function createInitialProductState(): ProductPanelState {
  return {
    query: "",
    results: [],
    count: 0,
    loading: false,
    error: "",
  };
}

// 做什么：创建默认订单侧栏状态。
// 为什么：让状态初始化保持集中且可复用。
function createInitialOrderState(): OrderPanelState {
  return {
    orderId: "",
    result: null,
    loading: false,
    error: "",
  };
}

// 做什么：创建默认商品表单状态。
// 为什么：避免组件内散落默认值。
function createInitialProductForm(): ProductSearchFormState {
  return {
    query: "",
    category: "",
    maxPrice: "",
  };
}

// 做什么：创建默认订单表单状态。
// 为什么：避免组件内散落默认值。
function createInitialOrderForm(): OrderSearchFormState {
  return {
    orderId: "",
  };
}

// 做什么：创建用户消息对象。
// 为什么：统一消息对象结构，避免多处手写字段。
function createUserMessage(content: string): ConversationMessage {
  return {
    id: window.crypto.randomUUID(),
    role: "user",
    content,
  };
}

// 做什么：创建助手消息对象。
// 为什么：把回复正文与元数据一起收进消息流。
function createAssistantMessage(meta: Awaited<ReturnType<typeof sendChat>>): ConversationMessage {
  return {
    id: window.crypto.randomUUID(),
    role: "assistant",
    content: meta.response,
    meta,
  };
}

// 做什么：创建系统错误消息。
// 为什么：当请求失败时，也要把反馈写进消息时间线里。
function createSystemMessage(content: string): ConversationMessage {
  return {
    id: window.crypto.randomUUID(),
    role: "system",
    content,
  };
}

// 做什么：渲染 MallPilot 导购台。
// 为什么：它把聊天、商品直查和订单追踪三条路径收束到一个工作台中。
export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>(() => [createWelcomeMessage()]);
  const [draft, setDraft] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [decisionMode, setDecisionMode] = useState<DecisionMode>("product");
  const [productState, setProductState] = useState<ProductPanelState>(() => createInitialProductState());
  const [orderState, setOrderState] = useState<OrderPanelState>(() => createInitialOrderState());
  const [productForm, setProductForm] = useState<ProductSearchFormState>(() => createInitialProductForm());
  const [orderForm, setOrderForm] = useState<OrderSearchFormState>(() => createInitialOrderForm());

  useEffect(() => {
    const convId = getOrCreateConversationId();
    setConversationId(convId);
  }, []);

  useEffect(() => {
    let active = true;

    // 做什么：首次加载时读取服务健康信息。
    // 为什么：顶部品牌条需要尽快展示在线状态和数据规模。
    const loadHealth = async () => {
      try {
        const data = await fetchHealth();
        if (!active) {
          return;
        }
        setHealth(data);
        setHealthError("");
      } catch (_error) {
        if (!active) {
          return;
        }
        setHealthError("当前未连上 MallPilot 服务，请先启动后端。");
      }
    };

    void loadHealth();

    return () => {
      active = false;
    };
  }, []);

  // 做什么：统一提交聊天请求。
  // 为什么：让输入框发送和快捷示例发送都走同一条主链路。
  const handleSendChat = async (nextMessage?: string) => {
    const messageText = (nextMessage ?? draft).trim();
    if (!messageText || chatLoading || !conversationId) {
      return;
    }

    setChatLoading(true);
    setDraft("");

    // 做什么：先把用户消息写入时间线。
    // 为什么：让页面反馈更即时，不必等接口返回才看到输入生效。
    setMessages((prev) => [...prev, createUserMessage(messageText)]);

    try {
      const response = await sendChat({
        message: messageText,
        user_id: DEFAULT_USER_ID,
        conv_id: conversationId,
      });

      // 做什么：把助手回复连同元数据写回时间线。
      // 为什么：页面需要同步展示回答内容与意图判断结果。
      setMessages((prev) => [...prev, createAssistantMessage(response)]);
    } catch (_error) {
      setMessages((prev) => [...prev, createSystemMessage("导购助手暂时不可用，请稍后重试。")]);
    } finally {
      setChatLoading(false);
    }
  };

  // 做什么：提交商品结构化查询。
  // 为什么：把预算导购结果固定到右侧，减少聊天信息噪声。
  const handleProductSearch = async () => {
    const query = productForm.query.trim();
    if (!query) {
      setProductState((prev) => ({
        ...prev,
        error: "请先输入要找的商品关键词。",
      }));
      return;
    }

    setDecisionMode("product");
    setProductState((prev) => ({
      ...prev,
      query,
      loading: true,
      error: "",
    }));

    try {
      const response = await searchCatalog({
        query,
        category: productForm.category || undefined,
        max_price: productForm.maxPrice ? Number(productForm.maxPrice) : undefined,
        limit: 4,
      });

      // 做什么：根据是否命中结果返回不同中文提示。
      // 为什么：空状态要能直接指导用户调整条件。
      setProductState({
        query,
        results: response.results,
        count: response.count,
        loading: false,
        error: response.count === 0 ? "当前条件下没有匹配商品，建议放宽预算或换一个关键词。" : "",
      });
    } catch (_error) {
      setProductState({
        query,
        results: [],
        count: 0,
        loading: false,
        error: "商品检索暂时不可用，请稍后重试。",
      });
    }
  };

  // 做什么：提交订单查询。
  // 为什么：把订单事实固定到右侧面单，避免用户在聊天里反复追问状态。
  const handleOrderSearch = async () => {
    const orderId = orderForm.orderId.trim();
    if (!orderId) {
      setOrderState((prev) => ({
        ...prev,
        error: "请先输入订单号。",
      }));
      return;
    }

    setDecisionMode("order");
    setOrderState({
      orderId,
      result: null,
      loading: true,
      error: "",
    });

    try {
      const response = await lookupOrder({
        order_id: orderId,
        user_id: DEFAULT_USER_ID,
      });

      setOrderState({
        orderId,
        result: response,
        loading: false,
        error: "",
      });
    } catch (_error) {
      setOrderState({
        orderId,
        result: null,
        loading: false,
        error: "没有找到这个订单号，请核对后再查。",
      });
    }
  };

  return (
    <div className="app-shell">
      <div className="app-shell__backdrop" aria-hidden="true" />

      <main className="workspace">
        <StatusBar health={health} error={healthError} />

        <div className="workspace__main">
          <ChatPanel
            messages={messages}
            draft={draft}
            loading={chatLoading}
            quickPrompts={QUICK_PROMPTS}
            onDraftChange={setDraft}
            onSend={() => void handleSendChat()}
            onQuickPrompt={(prompt) => void handleSendChat(prompt)}
          />

          <DecisionPanel
            mode={decisionMode}
            productState={productState}
            orderState={orderState}
            onModeChange={setDecisionMode}
          />
        </div>

        <StructuredTools
          productForm={productForm}
          orderForm={orderForm}
          productLoading={productState.loading}
          orderLoading={orderState.loading}
          onProductFormChange={setProductForm}
          onOrderFormChange={setOrderForm}
          onProductSubmit={() => void handleProductSearch()}
          onOrderSubmit={() => void handleOrderSearch()}
        />
      </main>
    </div>
  );
}
