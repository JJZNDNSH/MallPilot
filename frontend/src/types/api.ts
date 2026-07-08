// 做什么：定义与后端接口一一对应的类型。
// 为什么：让页面在联调时直接复用真实字段，减少手写字段名出错。

// 做什么：描述聊天请求体。
// 为什么：统一 /chat 请求入参，避免不同组件各自拼接字段。
export interface ChatRequest {
  /** 做什么：承载用户输入内容。为什么：后端用它驱动意图识别与回复生成。 */
  message: string;
  /** 做什么：标记当前前端用户。为什么：后端会用它关联记忆与订单上下文。 */
  user_id: string;
  /** 做什么：标记当前会话编号。为什么：后端依赖它延续多轮对话。 */
  conv_id: string;
}

// 做什么：描述聊天响应体。
// 为什么：把回复文本和 Agent 元数据一起暴露给页面。
export interface ChatResponse {
  /** 做什么：返回当前会话编号。为什么：前端要继续复用同一会话。 */
  conv_id: string;
  /** 做什么：承载助手最终回复。为什么：这是消息流的核心展示内容。 */
  response: string;
  /** 做什么：返回识别出的意图。为什么：页面要可视化本轮判断结果。 */
  intent: string;
  /** 做什么：返回处理该轮消息的 Agent 类型。为什么：帮助用户理解系统分流。 */
  agent_type: string;
  /** 做什么：标记是否触发升级。为什么：页面需要提示本轮是否进入人工/升级流程。 */
  escalated: boolean;
  /** 做什么：返回处理耗时。为什么：页面要展示响应速度元数据。 */
  latency_ms: number;
  /** 做什么：标记是否命中知识库。为什么：页面要展示规则知识是否参与回答。 */
  knowledge_used: boolean;
}

// 做什么：描述商品搜索请求体。
// 为什么：统一结构化商品查询字段，方便表单和 API 复用。
export interface CatalogSearchRequest {
  /** 做什么：承载商品搜索关键词。为什么：后端依赖它检索相关商品。 */
  query: string;
  /** 做什么：承载可选商品类目。为什么：用户按场景缩小检索范围时会使用。 */
  category?: string;
  /** 做什么：承载可选最低价格。为什么：保留价格下限扩展能力。 */
  min_price?: number;
  /** 做什么：承载可选最高价格。为什么：预算导购会优先使用这个字段。 */
  max_price?: number;
  /** 做什么：限制结果数量。为什么：侧栏只需要展示有限候选，避免信息过载。 */
  limit: number;
}

// 做什么：描述订单查询请求体。
// 为什么：统一订单追踪表单与 API 请求结构。
export interface OrderLookupRequest {
  /** 做什么：承载订单号。为什么：后端用它命中具体订单。 */
  order_id: string;
  /** 做什么：承载可选用户标识。为什么：后端可据此做订单归属校验。 */
  user_id?: string;
}

// 做什么：描述商品规格对象。
// 为什么：后端会把 specs_json 解析成对象返回给前端。
export interface ProductSpecs {
  /** 做什么：承载动态规格字段。为什么：不同商品规格结构并不完全一致。 */
  [key: string]: string | number | boolean;
}

// 做什么：描述单个商品结果。
// 为什么：商品卡片需要稳定消费这些字段。
export interface ProductItem {
  /** 做什么：承载商品编号。为什么：用于区分和标记具体商品。 */
  product_id: string;
  /** 做什么：承载商品名称。为什么：它是卡片主标题。 */
  name: string;
  /** 做什么：承载商品类目。为什么：用于快速说明商品归属场景。 */
  category: string;
  /** 做什么：承载商品品牌。为什么：帮助用户做品牌层面的判断。 */
  brand: string;
  /** 做什么：承载当前售价。为什么：价格是导购决策的核心信息。 */
  price: number;
  /** 做什么：承载原价。为什么：页面可展示让利幅度和对比关系。 */
  original_price: number;
  /** 做什么：承载库存数量。为什么：页面只展示真实库存事实，不做推测。 */
  stock: number;
  /** 做什么：承载评分。为什么：用户需要快速判断口碑表现。 */
  rating: number;
  /** 做什么：承载销量。为什么：为推荐排序和信心提示提供背景。 */
  sales_count: number;
  /** 做什么：承载标签文本。为什么：页面会把它拆成标签组。 */
  tags: string;
  /** 做什么：承载商品摘要。为什么：用简短语言说明适用场景。 */
  summary: string;
  /** 做什么：承载结构化规格。为什么：页面可按需补充关键信息。 */
  specs: ProductSpecs;
  /** 做什么：标记是否精选。为什么：页面会用它强化推荐理由。 */
  is_featured: boolean;
}

// 做什么：描述商品搜索响应体。
// 为什么：统一处理结果列表与数量信息。
export interface CatalogSearchResponse {
  /** 做什么：承载商品结果列表。为什么：页面据此渲染商品卡片。 */
  results: ProductItem[];
  /** 做什么：承载命中数量。为什么：页面要提示当前返回规模。 */
  count: number;
}

// 做什么：描述订单中的单个商品明细。
// 为什么：订单面单需要逐条展示真实购买内容。
export interface OrderItem {
  /** 做什么：承载商品编号。为什么：保持和商品数据层的一致性。 */
  product_id: string;
  /** 做什么：承载下单时的商品名称快照。为什么：避免商品改名影响历史订单展示。 */
  product_name_snapshot: string;
  /** 做什么：承载下单时的规格快照。为什么：这是售后和收货判断的重要依据。 */
  sku_snapshot: string;
  /** 做什么：承载购买数量。为什么：帮助用户核对订单内容。 */
  quantity: number;
  /** 做什么：承载下单单价。为什么：页面需要展示订单事实而不是重新计算。 */
  unit_price: number;
}

// 做什么：描述订单查询响应体。
// 为什么：订单追踪面单要稳定消费这些字段。
export interface OrderLookupResponse {
  /** 做什么：承载订单号。为什么：它是订单追踪的主标识。 */
  order_id: string;
  /** 做什么：承载订单所属用户。为什么：便于联调和对齐会话身份。 */
  user_id: string;
  /** 做什么：承载订单总体状态。为什么：用户最先关心当前进展。 */
  status: string;
  /** 做什么：承载订单总金额。为什么：用于展示结算背景信息。 */
  total_amount: number;
  /** 做什么：承载实付金额。为什么：用户需要核对最终支付事实。 */
  payment_amount: number;
  /** 做什么：承载支付方式。为什么：帮助解释支付相关问题。 */
  payment_method: string;
  /** 做什么：承载物流状态。为什么：物流问题需要首先展示这个字段。 */
  shipping_status: string;
  /** 做什么：承载物流公司。为什么：用户追踪订单时需要知道承运方。 */
  shipping_company: string;
  /** 做什么：承载运单号。为什么：方便用户继续外部追踪。 */
  tracking_no: string;
  /** 做什么：承载下单时间。为什么：帮助用户校对订单时间线。 */
  created_at: string;
  /** 做什么：承载支付时间。为什么：有助于解释支付与发货顺序。 */
  paid_at: string;
  /** 做什么：承载发货时间。为什么：用户会据此理解当前物流阶段。 */
  shipped_at: string;
  /** 做什么：承载签收时间。为什么：订单完成场景需要展示此事实。 */
  delivered_at: string;
  /** 做什么：承载优惠券信息。为什么：订单金额解释需要这个字段。 */
  coupon_code: string;
  /** 做什么：承载地址摘要。为什么：既能核对去向，又避免展示过细隐私。 */
  address_summary: string;
  /** 做什么：承载发票抬头。为什么：发票咨询场景会直接使用。 */
  invoice_title: string;
  /** 做什么：承载售后状态。为什么：退换货问题首先要看这里。 */
  after_sales_status: string;
  /** 做什么：承载订单商品列表。为什么：页面要渲染真实购买明细。 */
  items: OrderItem[];
}

// 做什么：描述健康检查中的商品统计。
// 为什么：顶部状态条需要展示真实数据量。
export interface HealthCommerce {
  /** 做什么：承载商品总数。为什么：说明导购库当前规模。 */
  products: number;
  /** 做什么：承载订单总数。为什么：说明订单演示数据规模。 */
  orders: number;
  /** 做什么：承载订单明细总数。为什么：帮助说明订单数据完整度。 */
  order_items: number;
}

// 做什么：描述健康检查响应体。
// 为什么：顶部品牌条需要用它判断服务状态。
export interface HealthResponse {
  /** 做什么：承载服务健康状态。为什么：页面要据此显示在线与否。 */
  status: string;
  /** 做什么：承载 Agent 统计信息。为什么：页面可用它提示当前服务能力已加载。 */
  agents: Record<string, unknown>;
  /** 做什么：承载商品与订单统计。为什么：页面顶部要展示真实业务数据规模。 */
  commerce: HealthCommerce;
}
