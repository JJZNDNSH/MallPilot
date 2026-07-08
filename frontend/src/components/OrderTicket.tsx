import type { OrderLookupResponse } from "../types/api";

// 做什么：定义订单面单组件参数。
// 为什么：让订单展示逻辑和侧栏容器解耦。
interface OrderTicketProps {
  /** 做什么：承载订单查询结果。为什么：面单需要按真实字段呈现订单事实。 */
  order: OrderLookupResponse;
}

// 做什么：渲染订单追踪面单。
// 为什么：把物流、支付和售后信息组织成接近快递面单的阅读顺序。
export function OrderTicket({ order }: OrderTicketProps) {
  return (
    <article className="order-ticket">
      <div className="order-ticket__header">
        <p className="order-ticket__eyebrow">tracking slip</p>
        <h3 className="order-ticket__order-id">{order.order_id}</h3>
      </div>

      <dl className="order-ticket__facts">
        <div>
          <dt>订单状态</dt>
          <dd>{order.status}</dd>
        </div>
        <div>
          <dt>物流状态</dt>
          <dd>{order.shipping_status}</dd>
        </div>
        <div>
          <dt>物流公司</dt>
          <dd>{order.shipping_company || "待分配"}</dd>
        </div>
        <div>
          <dt>运单号</dt>
          <dd>{order.tracking_no || "待生成"}</dd>
        </div>
        <div>
          <dt>实付金额</dt>
          <dd>¥{order.payment_amount.toFixed(0)}</dd>
        </div>
        <div>
          <dt>支付方式</dt>
          <dd>{order.payment_method}</dd>
        </div>
        <div>
          <dt>发票抬头</dt>
          <dd>{order.invoice_title}</dd>
        </div>
        <div>
          <dt>售后状态</dt>
          <dd>{order.after_sales_status}</dd>
        </div>
      </dl>

      <div className="order-ticket__timeline">
        <p>下单：{order.created_at || "暂无"}</p>
        <p>支付：{order.paid_at || "暂无"}</p>
        <p>发货：{order.shipped_at || "暂无"}</p>
        <p>签收：{order.delivered_at || "暂无"}</p>
      </div>

      <div className="order-ticket__address">
        <p className="order-ticket__label">收货地址摘要</p>
        <p>{order.address_summary}</p>
      </div>

      <div className="order-ticket__items">
        <p className="order-ticket__label">订单商品</p>
        {order.items.map((item) => (
          <div key={`${order.order_id}-${item.product_id}-${item.sku_snapshot}`} className="order-ticket__item-row">
            <div>
              <p>{item.product_name_snapshot}</p>
              <p className="order-ticket__sku">{item.sku_snapshot}</p>
            </div>
            <div className="order-ticket__item-meta">
              <span>x{item.quantity}</span>
              <span>¥{item.unit_price.toFixed(0)}</span>
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}
