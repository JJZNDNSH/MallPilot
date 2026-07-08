import type { KeyboardEvent } from "react";
import { ReceiptMessage } from "./ReceiptMessage";
import type { ConversationMessage } from "../types/ui";

// 做什么：定义聊天面板组件参数。
// 为什么：集中描述消息流、输入区和快捷示例所需数据。
interface ChatPanelProps {
  /** 做什么：承载消息列表。为什么：面板需要按顺序渲染会话内容。 */
  messages: ConversationMessage[];
  /** 做什么：承载输入框当前文本。为什么：聊天输入需要受控。 */
  draft: string;
  /** 做什么：标记是否正在发送消息。为什么：发送期间需要禁用按钮并提示状态。 */
  loading: boolean;
  /** 做什么：承载快捷示例。为什么：帮助用户快速进入真实演示场景。 */
  quickPrompts: string[];
  /** 做什么：用于更新输入框。为什么：保持输入状态由上层统一管理。 */
  onDraftChange: (value: string) => void;
  /** 做什么：用于发送聊天内容。为什么：把核心业务逻辑放回上层执行。 */
  onSend: () => void;
  /** 做什么：用于点击快捷示例即发送。为什么：让首次体验更顺滑。 */
  onQuickPrompt: (prompt: string) => void;
}

// 做什么：渲染聊天主工作台。
// 为什么：它承载了页面最核心的导购对话链路。
export function ChatPanel({
  messages,
  draft,
  loading,
  quickPrompts,
  onDraftChange,
  onSend,
  onQuickPrompt,
}: ChatPanelProps) {
  // 做什么：处理输入框回车发送。
  // 为什么：让桌面端输入体验更接近常见聊天工具。
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  return (
    <section className="chat-panel" aria-label="导购对话工作台">
      <div className="chat-panel__intro">
        <p className="chat-panel__eyebrow">receipt ribbon</p>
        <h2 className="chat-panel__title">把模糊需求打印成可执行判断</h2>
        <p className="chat-panel__desc">
          这里优先处理开放式导购问题，右侧则固定展示商品事实或订单事实，避免回答漂浮。
        </p>
      </div>

      <div className="chat-panel__prompts" aria-label="快捷示例">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="prompt-pill"
            onClick={() => onQuickPrompt(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>

      <div className="chat-panel__stream" role="log" aria-live="polite">
        {messages.map((message) => (
          <ReceiptMessage key={message.id} message={message} />
        ))}
      </div>

      <div className="chat-panel__composer">
        <label className="chat-panel__label" htmlFor="chat-input">
          对话输入
        </label>
        <textarea
          id="chat-input"
          className="chat-panel__textarea"
          value={draft}
          rows={4}
          placeholder="例如：预算 3000，想买续航好的手机，顺便看看耳机怎么选。"
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />
        <div className="chat-panel__actions">
          <p className="chat-panel__helper">Enter 发送，Shift + Enter 换行</p>
          <button type="button" className="primary-button" disabled={loading} onClick={onSend}>
            {loading ? "分拣中..." : "发送导购请求"}
          </button>
        </div>
      </div>
    </section>
  );
}
