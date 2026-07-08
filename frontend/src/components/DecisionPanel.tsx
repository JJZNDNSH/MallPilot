import { OrderTicket } from "./OrderTicket";
import { ProductCard } from "./ProductCard";
import type { DecisionMode, OrderPanelState, ProductPanelState } from "../types/ui";

// 做什么：定义决策侧栏组件参数。
// 为什么：让商品视图和订单视图共用一个稳定容器。
interface DecisionPanelProps {
  /** 做什么：承载当前侧栏模式。为什么：页面需要切换商品与订单视图。 */
  mode: DecisionMode;
  /** 做什么：承载商品面板状态。为什么：商品模式需要展示结果和错误。 */
  productState: ProductPanelState;
  /** 做什么：承载订单面板状态。为什么：订单模式需要展示结果和错误。 */
  orderState: OrderPanelState;
  /** 做什么：用于切换侧栏模式。为什么：桌面与移动端都要支持主动切换。 */
  onModeChange: (mode: DecisionMode) => void;
}

// 做什么：渲染右侧决策侧栏。
// 为什么：把开放式聊天和结构化事实分栏展示，降低信息混杂。
export function DecisionPanel({ mode, productState, orderState, onModeChange }: DecisionPanelProps) {
  return (
    <aside className="decision-panel" aria-label="决策侧栏">
      <div className="decision-panel__tabs" role="tablist" aria-label="侧栏模式切换">
        <button
          type="button"
          className={`decision-tab ${mode === "product" ? "is-active" : ""}`}
          onClick={() => onModeChange("product")}
        >
          商品直查
        </button>
        <button
          type="button"
          className={`decision-tab ${mode === "order" ? "is-active" : ""}`}
          onClick={() => onModeChange("order")}
        >
          订单追踪
        </button>
      </div>

      {mode === "product" ? (
        <section className="decision-panel__section">
          <div className="decision-panel__header">
            <p className="decision-panel__eyebrow">catalog strip</p>
            <h2>商品候选</h2>
            <p>
              {productState.query ? `当前关键词：${productState.query}` : "从底部工具区按预算找商品，结果会固定在这里。"}
            </p>
          </div>

          {productState.loading ? <p className="decision-panel__notice">正在匹配商品...</p> : null}
          {!productState.loading && productState.error ? (
            <p className="decision-panel__notice decision-panel__notice--error">{productState.error}</p>
          ) : null}
          {!productState.loading && !productState.error && productState.results.length === 0 ? (
            <p className="decision-panel__notice">当前还没有商品结果，先试试预算导购或输入一个具体品类。</p>
          ) : null}

          <div className="decision-panel__list">
            {productState.results.map((product) => (
              <ProductCard key={product.product_id} product={product} />
            ))}
          </div>

          {productState.results.length > 0 ? (
            <p className="decision-panel__footer-note">共返回 {productState.count} 条结果，只展示前几条更适合决策的候选。</p>
          ) : null}
        </section>
      ) : (
        <section className="decision-panel__section">
          <div className="decision-panel__header">
            <p className="decision-panel__eyebrow">parcel tracking</p>
            <h2>订单事实</h2>
            <p>
              {orderState.orderId ? `当前订单号：${orderState.orderId}` : "输入订单号后，这里会展示物流、支付和售后面单。"}
            </p>
          </div>

          {orderState.loading ? <p className="decision-panel__notice">正在追踪订单...</p> : null}
          {!orderState.loading && orderState.error ? (
            <p className="decision-panel__notice decision-panel__notice--error">{orderState.error}</p>
          ) : null}
          {!orderState.loading && !orderState.error && !orderState.result ? (
            <p className="decision-panel__notice">当前还没有订单结果，可以先查询示例订单 `MP20260706001`。</p>
          ) : null}

          {orderState.result ? <OrderTicket order={orderState.result} /> : null}
        </section>
      )}
    </aside>
  );
}
