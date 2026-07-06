"""
MallPilot RAG 知识库模块。

这个模块继续使用 ChromaDB 承担非结构化规则知识检索，并同步处理 MallPilot 默认演示文档与旧 EchoMind 演示文档迁移。
"""
import hashlib
import logging
from typing import Any, Dict, List

import chromadb

logger = logging.getLogger(__name__)


DEFAULT_DOC_SOURCE = "mallpilot_demo"
LEGACY_DEMO_TITLES = {
    "退款政策",
    "订单查询",
    "账户安全",
    "技术故障排查",
    "会员与积分",
    "配送说明",
}

DEFAULT_DOCS: List[Dict[str, str]] = [
    {
        "title": "商品选购建议原则",
        "content": (
            "MallPilot 商品选购建议原则。"
            "做商品推荐时，优先结合用户预算、使用场景、类目偏好和品牌倾向。"
            "如果预算不足以覆盖需求，要明确说明取舍，例如续航更强、拍照更强或价格更低。"
            "没有库存、活动或价格实时数据时，不能承诺一定有货或一定能享受优惠。"
            "做参数对比时，优先对比影响购买决策的核心项，例如性能、续航、尺寸、重量、清洁难度或材质。"
        ),
    },
    {
        "title": "配送与运费说明",
        "content": (
            "MallPilot 配送说明。"
            "标准配送通常 3 到 5 个工作日送达，订单满 99 元包邮。"
            "加急配送通常 1 到 2 个工作日送达，运费 15 元。"
            "同城配送通常支持次日达，部分城市可当日达，运费 10 元起。"
            "偏远地区或大型家居商品可能需要额外 2 到 4 天。"
            "物流信息一般在发货后 12 到 24 小时内更新。"
        ),
    },
    {
        "title": "支付与发票说明",
        "content": (
            "MallPilot 支付与发票说明。"
            "支持支付宝、微信支付和银行卡等常见支付方式。"
            "优惠券是否可用取决于类目、活动时间和订单金额门槛。"
            "电子发票通常在订单完成后 1 到 3 个工作日内开具。"
            "企业抬头、税号和开票金额需要核验后才能确认。"
            "没有订单号或支付记录时，不能直接承诺补开发票成功。"
        ),
    },
    {
        "title": "会员积分与优惠券规则",
        "content": (
            "MallPilot 会员与优惠规则。"
            "普通会员消费 1 元可累计 1 积分，部分活动商品积分规则可能不同。"
            "100 积分通常可抵扣 1 元，但不同活动可能存在抵扣上限。"
            "优惠券可能限制适用品类、适用门槛和有效期。"
            "退款后优惠券是否退回，需要以券类型和活动规则为准。"
            "积分和优惠券都不能在没有订单核验时直接补发或补偿。"
        ),
    },
    {
        "title": "退换货与退款政策",
        "content": (
            "MallPilot 售后规则。"
            "商品签收后 7 天内，符合条件的订单可以申请退货退款。"
            "质量问题、破损或错发通常需要上传照片或视频作为核验材料。"
            "退款申请提交后通常会在 1 到 3 个工作日内审核。"
            "审核通过后，款项通常在 3 到 7 个工作日内原路退回。"
            "已发货订单如果需要退款，通常要先走退货流程。"
        ),
    },
    {
        "title": "订单状态说明",
        "content": (
            "MallPilot 订单状态说明。"
            "待支付表示订单已创建但尚未完成支付。"
            "已支付表示支付成功，待仓库分配或等待发货。"
            "已发货表示仓库已出库，物流信息可能稍后同步。"
            "运输中表示承运商已揽收并正在派送途中。"
            "已签收表示物流反馈已送达。"
            "退款中或换货中表示售后流程已发起，但最终结果仍需审核确认。"
        ),
    },
]


class KnowledgeBase:
    """基于 ChromaDB 的 MallPilot 规则知识库。"""

    COLLECTION_NAME = "knowledge_base"

    # 做什么：初始化 ChromaDB 客户端与知识库集合。
    # 为什么：为 RAG 检索、文档导入和默认演示数据同步提供统一入口。
    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_path: str = "./data/chroma",
    ):
        try:
            self._client = chromadb.HttpClient(
                host=chroma_host,
                port=chroma_port,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )
            self._client.heartbeat()
            logger.info("MallPilot 知识库已连接 ChromaDB 服务: %s:%s", chroma_host, chroma_port)
        except Exception:
            logger.info("MallPilot 知识库使用本地 ChromaDB 模式: %s", chroma_path)
            self._client = chromadb.PersistentClient(
                path=chroma_path,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )

        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "MallPilot RAG 知识库"},
        )
        self._sync_default_docs()

    # 做什么：批量导入知识文档。
    # 为什么：支持接口上传和演示文档批量写入。
    def add_documents(self, documents: List[Dict[str, str]], source: str = "user_upload") -> int:
        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []

        for document in documents:
            title = document.get("title", "").strip()
            content = document.get("content", "").strip()
            chunks = self._chunk_text(content, chunk_size=500)
            for index, chunk in enumerate(chunks):
                digest = hashlib.md5(f"{source}:{title}:{index}:{chunk[:80]}".encode("utf-8")).hexdigest()
                ids.append(digest)
                docs.append(chunk)
                metas.append(
                    {
                        "title": title,
                        "chunk_index": index,
                        "total_chunks": len(chunks),
                        "source": source,
                    }
                )

        if ids:
            self._collection.add(ids=ids, documents=docs, metadatas=metas)
            logger.info("MallPilot 知识库导入 %s 个文档片段，source=%s", len(ids), source)
        return len(ids)

    # 做什么：按语义检索知识片段。
    # 为什么：为规则、政策、活动说明等非结构化问题提供事实约束。
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        items: List[Dict[str, Any]] = []
        if results["documents"] and results["documents"][0]:
            for document, metadata, distance in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append(
                    {
                        "title": metadata.get("title", ""),
                        "content": document,
                        "score": round(1.0 - distance, 4),
                        "chunk": metadata.get("chunk_index", 0),
                        "source": metadata.get("source", ""),
                    }
                )
        return items

    # 做什么：返回知识库片段总量。
    # 为什么：供健康检查与调试接口读取。
    @property
    def doc_count(self) -> int:
        return self._collection.count()

    # 做什么：作为 MCP 工具处理函数暴露。
    # 为什么：让工具框架直接复用知识库检索能力。
    async def search_handler(self, params: Dict[str, Any], context: Any) -> List[Dict[str, Any]]:
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        return self.search(query, top_k=top_k)

    # 做什么：按句号与换行切分长文档。
    # 为什么：减少单片过长导致的检索噪声。
    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        if len(text) <= chunk_size:
            return [text] if text else []

        chunks: List[str] = []
        current = ""
        sentences = text.replace("\n", "。").split("。")
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(current) + len(sentence) + 1 > chunk_size:
                if current:
                    chunks.append(current)
                current = sentence
            else:
                current = f"{current}。{sentence}" if current else sentence
        if current:
            chunks.append(current)
        return chunks

    # 做什么：同步 MallPilot 默认演示文档，并清理旧客服演示文档。
    # 为什么：避免旧 EchoMind 默认知识残留，污染新的导购语义检索结果。
    def _sync_default_docs(self) -> None:
        self._remove_demo_documents()
        self.add_documents(DEFAULT_DOCS, source=DEFAULT_DOC_SOURCE)

    # 做什么：删除旧的 MallPilot 演示文档和已知 EchoMind 默认文档。
    # 为什么：让持久化 Chroma 库在升级后仍能保持干净的默认集合。
    def _remove_demo_documents(self) -> None:
        try:
            all_docs = self._collection.get(include=["metadatas"])
        except TypeError:
            all_docs = self._collection.get()
        except Exception as ex:
            logger.warning("清理默认知识文档失败: %s", ex)
            return

        ids_to_delete: List[str] = []
        ids = all_docs.get("ids", []) or []
        metadatas = all_docs.get("metadatas", []) or []
        for item_id, metadata in zip(ids, metadatas):
            title = ""
            source = ""
            if isinstance(metadata, dict):
                title = str(metadata.get("title", ""))
                source = str(metadata.get("source", ""))
            if source == DEFAULT_DOC_SOURCE or title in LEGACY_DEMO_TITLES or title in {doc["title"] for doc in DEFAULT_DOCS}:
                ids_to_delete.append(str(item_id))

        if ids_to_delete:
            self._collection.delete(ids=ids_to_delete)
            logger.info("清理默认知识文档 %s 条", len(ids_to_delete))
