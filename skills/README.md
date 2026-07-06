# MallPilot Skills 文档

MallPilot 启动时会从 `MALLPILOT_SKILLS_DIR` 读取 Skills，并在匹配用户请求时注入到对应 Agent 的 system prompt。Skills 适合维护导购策略、订单处理规范、售后边界、升级条件和禁止事项。

当前内置三类 Skills：

```text
skills/shopping_guide/SKILL.md  # 导购服务：推荐、对比、预算建议、活动说明、搭配建议
skills/order_service/SKILL.md   # 订单服务：订单状态、物流、支付、地址、发票、优惠券说明
skills/after_sales/SKILL.md     # 售后服务：退款、退货、换货、售后进度、投诉升级
```

## Skill 文件格式

推荐每个 Skill 使用独立目录，并将主文件命名为 `SKILL.md`：

```text
skills/<skill_name>/SKILL.md
```

文件顶部使用简易 front matter：

```markdown
---
name: 订单服务处理规范
description: 适用于 OrderAgent 的订单查询、物流说明和发票处理规则
keywords: 订单,物流,发货,签收,地址,发票,支付,优惠券
agents: order
enabled: true
---
```

字段说明：

- `name`：Skill 展示名称，会出现在注入给模型的 prompt 中。
- `description`：简短说明，便于 `/skills` 接口排查。
- `keywords`：触发关键词，用户消息命中后才注入；多个关键词用英文逗号分隔。
- `agents`：适用 Agent，可填 `guide`、`order`、`after_sales`，多个值用逗号分隔。
- `enabled`：是否启用，支持 `true/false`。

## 编写要求

- 重要规则放在文档前半部分，因为过长内容会被 prompt 预算截断。
- 一类 Skill 只描述一类职责，不要把导购、订单、售后规则混在一个文件里。
- 必须包含“角色定位”“处理流程”“升级条件”“禁止事项”等稳定章节。
- 对涉及价格、库存、优惠资格、物流时效、退款进度等不确定信息，使用保守措辞并提醒以查询结果为准。
- 对需要人工核验的场景，明确写出升级条件，不要让模型擅自承诺结果。
- 当前项目只支持只读查询和解释，不允许 Skill 引导模型伪造下单、退款、改地址等写操作成功。

## 热加载

修改 Skill 文件后，无需重启服务，调用：

```bash
curl -X POST http://localhost:8000/skills/reload
```

查看加载结果和解析错误：

```bash
curl http://localhost:8000/skills
```
