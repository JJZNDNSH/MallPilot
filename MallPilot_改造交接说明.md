# MallPilot 改造交接说明

## 改造目标

本次改造已将 EchoMind 智能客服项目切换为 MallPilot 综合电商导购助手，保留原项目的核心亮点能力：

- 三路意图识别
- RAG 知识库
- 三级记忆
- 多 Agent 路由与并行协作
- 动态 Skills
- Monitor 闭环降权
- 端到端评测

## 已完成范围

### 1. 业务与品牌切换

- 主品牌改为 `MallPilot`
- 主 Agent 语义改为 `guide / order / after_sales / escalation`
- 意图集改为导购、订单、售后、投诉、问候、反馈、升级、其他

### 2. 结构化数据链路

- 新增 SQLite 数据层：[core/commerce_store.py](D:/code/super_agent/core/commerce_store.py)
- 数据库路径默认改为 `data/sqlite/mallpilot.db`
- 已落地 `products / orders / order_items` 三张表
- 已灌入 12 个商品、11 个订单、12 条订单明细
- 演示订单号重点包含：
  - `MP20260706001`
  - `MP20260706004`
  - `MP20260706005`
  - `MP20260706006`

### 3. 主链路接入

- `/chat` 已接入商品库与订单库上下文注入
- 已新增只读演示接口：
  - `POST /catalog/search`
  - `POST /orders/lookup`
- 已注册新工具：
  - `product_search`
  - `order_lookup`

### 4. 规则、记忆、评测、监控

- Skills 已替换为：
  - [skills/shopping_guide/SKILL.md](D:/code/super_agent/skills/shopping_guide/SKILL.md)
  - [skills/order_service/SKILL.md](D:/code/super_agent/skills/order_service/SKILL.md)
  - [skills/after_sales/SKILL.md](D:/code/super_agent/skills/after_sales/SKILL.md)
- 用户画像提炼语义已改为品牌偏好、价格敏感度、类目兴趣、售后关注点
- 评测默认样例与基线已改为 MallPilot 场景
- Monitor 展示和建议文案已切到 `guide / order / after_sales`

### 5. 配置与示例文档

- 已更新：
  - [docker-compose.yml](D:/code/super_agent/docker-compose.yml)
  - [config/prometheus.yml](D:/code/super_agent/config/prometheus.yml)
  - [config/nginx/nginx.conf](D:/code/super_agent/config/nginx/nginx.conf)
  - [.env](D:/code/super_agent/.env)
  - [.env.example](D:/code/super_agent/.env.example)
  - [.env.example.env](D:/code/super_agent/.env.example.env)
- 已替换示例知识文档：
  - [data/demo_docs/sample_knowledge.json](D:/code/super_agent/data/demo_docs/sample_knowledge.json)
  - [data/demo_docs/troubleshooting.md](D:/code/super_agent/data/demo_docs/troubleshooting.md)

## 本地验证结论

- 已通过 `py_compile` 编译检查：
  - `api/main.py`
  - `agents/agent_orchestrator.py`
  - `core/intent_recognizer.py`
  - `core/commerce_store.py`
  - `core/skill_loader.py`
  - `memory/conversation_memory.py`
  - `evaluation/evaluator.py`
  - `monitor/performance_monitor.py`
  - `mcp/knowledge_base.py`
- SQLite 探针结果：
  - 商品数 `12`
  - 订单数 `11`
  - 明细数 `12`
- 技能加载探针结果：
  - `3` 套新 Skills 已可加载
- 商品检索已修复自然语言整句过严的问题，类目过滤和订单上下文探针正常

## 已知说明

- `api/main.py` 仍保留对旧环境变量 `ECHOMIND_*` 的兼容回退，这是为了平滑迁移，不影响 MallPilot 主配置名。
- `data/chroma` 目录中的历史持久化文件可能仍包含旧 EchoMind 文本，但 `mcp/knowledge_base.py` 已加入启动清理与 MallPilot demo 文档替换逻辑。
- 当前环境未完成一次真实 FastAPI 启动联调，因为本机命令行测试环境缺少运行时依赖镜像；已完成源码级编译校验与 SQLite/Skills 级功能探针。

## 建议的下一步验收

1. 启动服务后访问 `/health`、`/skills`、`/monitor`、`/knowledge/stats`
2. 调用 `POST /catalog/search` 验证商品库演示数据
3. 调用 `POST /orders/lookup` 验证订单和明细
4. 用以下问题回归 `/chat`
   - `预算 3000 想买续航好的手机`
   - `订单 MP20260706001 到哪了`
   - `这笔订单想退货换个颜色`
   - `我想买一个 500 元内的电动牙刷，对了订单 MP20260706005 什么时候到`
