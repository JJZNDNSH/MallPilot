import type { OrderSearchFormState, ProductSearchFormState } from "../types/ui";

// 做什么：定义底部工具区组件参数。
// 为什么：把结构化商品查询和订单追踪入口聚合在一起。
interface StructuredToolsProps {
  /** 做什么：承载商品表单状态。为什么：工具区商品表单需要受控。 */
  productForm: ProductSearchFormState;
  /** 做什么：承载订单表单状态。为什么：工具区订单表单需要受控。 */
  orderForm: OrderSearchFormState;
  /** 做什么：标记商品请求是否进行中。为什么：提交期间要禁用按钮。 */
  productLoading: boolean;
  /** 做什么：标记订单请求是否进行中。为什么：避免重复提交。 */
  orderLoading: boolean;
  /** 做什么：用于更新商品表单。为什么：保持表单状态在上层统一管理。 */
  onProductFormChange: (next: ProductSearchFormState) => void;
  /** 做什么：用于更新订单表单。为什么：保持表单状态在上层统一管理。 */
  onOrderFormChange: (next: OrderSearchFormState) => void;
  /** 做什么：用于提交商品查询。为什么：结构化导购是页面主路径之一。 */
  onProductSubmit: () => void;
  /** 做什么：用于提交订单查询。为什么：订单追踪是页面主路径之一。 */
  onOrderSubmit: () => void;
}

// 做什么：渲染底部结构化工具区。
// 为什么：让用户在开放式聊天之外还能直接走商品和订单事实查询。
export function StructuredTools({
  productForm,
  orderForm,
  productLoading,
  orderLoading,
  onProductFormChange,
  onOrderFormChange,
  onProductSubmit,
  onOrderSubmit,
}: StructuredToolsProps) {
  return (
    <section className="structured-tools" aria-label="结构化工具区">
      <article className="tool-card">
        <div className="tool-card__header">
          <p className="tool-card__eyebrow">tool 01</p>
          <h2>按预算找商品</h2>
          <p>把需求收紧成品类 + 预算，直接拉取真实商品候选。</p>
        </div>

        <div className="tool-card__fields">
          <label>
            关键词
            <input
              type="text"
              value={productForm.query}
              placeholder="手机、耳机、吹风机..."
              onChange={(event) =>
                onProductFormChange({
                  ...productForm,
                  query: event.target.value,
                })
              }
            />
          </label>

          <label>
            类目
            <select
              value={productForm.category}
              onChange={(event) =>
                onProductFormChange({
                  ...productForm,
                  category: event.target.value,
                })
              }
            >
              <option value="">不限类目</option>
              <option value="数码">数码</option>
              <option value="家居">家居</option>
              <option value="小家电">小家电</option>
              <option value="个护">个护</option>
              <option value="日用">日用</option>
            </select>
          </label>

          <label>
            预算上限
            <input
              type="number"
              inputMode="numeric"
              value={productForm.maxPrice}
              placeholder="3000"
              onChange={(event) =>
                onProductFormChange({
                  ...productForm,
                  maxPrice: event.target.value,
                })
              }
            />
          </label>
        </div>

        <button type="button" className="secondary-button" disabled={productLoading} onClick={onProductSubmit}>
          {productLoading ? "检索中..." : "查询商品"}
        </button>
      </article>

      <article className="tool-card">
        <div className="tool-card__header">
          <p className="tool-card__eyebrow">tool 02</p>
          <h2>按订单号追踪</h2>
          <p>直接把物流、支付和售后状态固定到右侧面单，减少解释成本。</p>
        </div>

        <div className="tool-card__fields">
          <label>
            订单号
            <input
              type="text"
              value={orderForm.orderId}
              placeholder="例如 MP20260706001"
              onChange={(event) =>
                onOrderFormChange({
                  orderId: event.target.value,
                })
              }
            />
          </label>
        </div>

        <button type="button" className="secondary-button" disabled={orderLoading} onClick={onOrderSubmit}>
          {orderLoading ? "追踪中..." : "查询订单"}
        </button>
      </article>
    </section>
  );
}
