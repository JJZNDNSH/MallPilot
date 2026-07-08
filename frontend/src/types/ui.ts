import type { ChatResponse, OrderLookupResponse, ProductItem } from "./api";

// 做什么：定义前端消息角色。
// 为什么：消息流需要根据角色切换视觉样式。
export type MessageRole = "user" | "assistant" | "system";

// 做什么：定义侧栏模式。
// 为什么：桌面和移动端都需要在商品与订单视图之间切换。
export type DecisionMode = "product" | "order";

// 做什么：描述单条消息卡片。
// 为什么：聊天流要同时承载文本和元数据。
export interface ConversationMessage {
  /** 做什么：承载消息唯一编号。为什么：React 渲染列表需要稳定 key。 */
  id: string;
  /** 做什么：承载消息角色。为什么：页面会按角色切换布局和颜色。 */
  role: MessageRole;
  /** 做什么：承载消息正文。为什么：它是卡片主内容。 */
  content: string;
  /** 做什么：承载可选聊天元数据。为什么：只有助手消息需要展示 Agent 信息。 */
  meta?: ChatResponse;
}

// 做什么：描述商品侧栏状态。
// 为什么：把商品结果、错误和加载状态统一管理。
export interface ProductPanelState {
  /** 做什么：记录最近一次查询词。为什么：侧栏标题需要回显当前检索语义。 */
  query: string;
  /** 做什么：承载商品结果列表。为什么：页面据此渲染候选商品。 */
  results: ProductItem[];
  /** 做什么：承载结果数量。为什么：用于提示返回规模。 */
  count: number;
  /** 做什么：标记是否正在查询。为什么：页面需要在请求期间给出反馈。 */
  loading: boolean;
  /** 做什么：承载错误信息。为什么：失败时要用中文直说。 */
  error: string;
}

// 做什么：描述订单侧栏状态。
// 为什么：统一管理订单追踪结果和异常反馈。
export interface OrderPanelState {
  /** 做什么：记录最近一次查询的订单号。为什么：侧栏标题需要回显当前追踪对象。 */
  orderId: string;
  /** 做什么：承载订单结果。为什么：命中后需要完整渲染面单内容。 */
  result: OrderLookupResponse | null;
  /** 做什么：标记是否正在查询。为什么：避免重复提交并给出加载反馈。 */
  loading: boolean;
  /** 做什么：承载错误信息。为什么：未命中或失败时要清晰提示。 */
  error: string;
}

// 做什么：描述商品搜索表单状态。
// 为什么：结构化导购工具需要受控表单。
export interface ProductSearchFormState {
  /** 做什么：承载搜索关键词。为什么：用户需要按品类或需求检索商品。 */
  query: string;
  /** 做什么：承载商品类目。为什么：帮助快速缩小范围。 */
  category: string;
  /** 做什么：承载预算上限。为什么：预算导购是页面重点能力。 */
  maxPrice: string;
}

// 做什么：描述订单表单状态。
// 为什么：订单追踪工具需要受控输入。
export interface OrderSearchFormState {
  /** 做什么：承载订单号。为什么：后端查询必须依赖它。 */
  orderId: string;
}
