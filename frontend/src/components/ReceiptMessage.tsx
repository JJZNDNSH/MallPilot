import type { ConversationMessage } from "../types/ui";

// 做什么：定义消息卡片组件参数。
// 为什么：把单条消息渲染职责从聊天面板中拆出来。
interface ReceiptMessageProps {
  /** 做什么：承载单条消息数据。为什么：消息卡片需要根据内容和角色渲染。 */
  message: ConversationMessage;
}

// 做什么：把布尔值转换成中文可读文本。
// 为什么：助手元数据需要用简洁自然的语言展示。
function formatBooleanLabel(value: boolean): string {
  return value ? "是" : "否";
}

// 做什么：渲染单条 receipt 风格消息。
// 为什么：让聊天记录像连续打印的小票，强化页面记忆点。
export function ReceiptMessage({ message }: ReceiptMessageProps) {
  return (
    <article className={`receipt-message receipt-message--${message.role}`}>
      <div className="receipt-message__header">
        <span className="receipt-message__role">
          {message.role === "user" ? "寄件人" : message.role === "assistant" ? "分拣员" : "系统提示"}
        </span>
      </div>

      <div className="receipt-message__content">
        {message.content.split("\n").map((line, index) => (
          <p key={`${message.id}-${index}`}>{line}</p>
        ))}
      </div>

      {message.meta ? (
        <dl className="receipt-message__meta">
          <div>
            <dt>intent</dt>
            <dd>{message.meta.intent}</dd>
          </div>
          <div>
            <dt>agent</dt>
            <dd>{message.meta.agent_type}</dd>
          </div>
          <div>
            <dt>knowledge</dt>
            <dd>{formatBooleanLabel(message.meta.knowledge_used)}</dd>
          </div>
          <div>
            <dt>latency</dt>
            <dd>{Math.round(message.meta.latency_ms)} ms</dd>
          </div>
        </dl>
      ) : null}
    </article>
  );
}
