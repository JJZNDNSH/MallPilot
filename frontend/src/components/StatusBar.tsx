import type { HealthResponse } from "../types/api";

// 做什么：定义顶部状态条组件参数。
// 为什么：让品牌信息与状态展示职责明确。
interface StatusBarProps {
  /** 做什么：承载健康检查结果。为什么：顶部需要展示服务在线状态与数据规模。 */
  health: HealthResponse | null;
  /** 做什么：承载健康检查错误。为什么：服务离线时要清晰告知用户。 */
  error: string;
}

// 做什么：渲染顶部品牌状态条。
// 为什么：让用户一进页面就知道导购台是否可用、当前数据规模如何。
export function StatusBar({ health, error }: StatusBarProps) {
  const isHealthy = health?.status === "ok" && !error;
  const agentCount = health ? Object.keys(health.agents || {}).length : 0;

  return (
    <header className="status-bar" aria-label="MallPilot 服务状态">
      <div className="status-bar__brand">
        <p className="status-bar__eyebrow">电商导购 agent</p>
        <h1 className="status-bar__title">MallPilot</h1>
        <p className="status-bar__subtitle">像快递面单一样，把问题送到正确的商品和订单事实上。</p>
      </div>

      <div className="status-bar__metrics">
        <article className="status-chip">
          <span className={`status-chip__dot ${isHealthy ? "is-online" : "is-offline"}`} />
          <div>
            <p className="status-chip__label">服务状态</p>
            <p className="status-chip__value">{isHealthy ? "在线" : "离线"}</p>
          </div>
        </article>

        <article className="status-chip">
          <div>
            <p className="status-chip__label">商品 / 订单</p>
            <p className="status-chip__value">
              {health ? `${health.commerce.products} / ${health.commerce.orders}` : "-- / --"}
            </p>
          </div>
        </article>

        <article className="status-chip">
          <div>
            <p className="status-chip__label">已加载能力</p>
            <p className="status-chip__value">{health ? `${agentCount} 组 Agent` : "--"}</p>
          </div>
        </article>
      </div>

      <p className="status-bar__hint">{error || "支持导购对话、商品直查、订单追踪三条主路径。"}</p>
    </header>
  );
}
