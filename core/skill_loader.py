"""
MallPilot Skill 加载器。
Skill 用来承载可热加载的业务规范，适合维护导购、订单、售后处理流程、
升级条件和禁止事项，并在运行时注入到对应 Agent 的 system prompt。
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """做什么：标准化表示一个 Skill；为什么：屏蔽 Markdown、JSON 等文件格式差异。"""

    name: str  # 做什么：保存 Skill 名称；为什么：展示和注入 prompt 时需要标题。
    description: str  # 做什么：保存 Skill 描述；为什么：方便排查加载结果。
    content: str  # 做什么：保存 Skill 正文；为什么：这是实际注入给模型的规则内容。
    path: str  # 做什么：保存源文件路径；为什么：方便定位和热加载排障。
    keywords: List[str] = field(default_factory=list)  # 做什么：保存触发关键词；为什么：按请求精确注入对应规则。
    agents: List[str] = field(default_factory=list)  # 做什么：保存适用 Agent；为什么：避免错误把规则注入到无关 Agent。
    enabled: bool = True  # 做什么：记录是否启用；为什么：支持运行时快速停用某套规则。

    def matches(self, message: str, agent_type: Optional[str] = None) -> bool:
        """做什么：判断请求是否命中当前 Skill；为什么：只给相关场景注入必要规则。"""
        if not self.enabled:
            return False
        if self.agents and agent_type and agent_type.lower() not in self.agents:
            return False
        if not self.keywords:
            return True
        lowered = (message or "").lower()
        return any(keyword.lower() in lowered for keyword in self.keywords)

    def to_prompt_block(self, max_chars: int = 3200) -> str:
        """做什么：把 Skill 格式化为 prompt 片段；为什么：供系统提示词直接拼接使用。"""
        body = self.content.strip()
        if len(body) > max_chars:
            body = body[:max_chars].rstrip() + "\n..."
        description = f"\n说明: {self.description}" if self.description else ""
        return f"### {self.name}{description}\n{body}"

    def to_summary(self) -> Dict[str, Any]:
        """做什么：返回可序列化摘要；为什么：避免 /skills 默认暴露全部长文本。"""
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "keywords": self.keywords,
            "agents": self.agents,
            "enabled": self.enabled,
            "content_chars": len(self.content),
        }


class SkillManager:
    """
    做什么：发现、解析并管理 Skills。
    为什么：让 MallPilot 的导购、订单、售后规则可以独立维护并支持热加载。
    """

    SUPPORTED_SUFFIXES = {".md", ".txt", ".json"}

    def __init__(self, root_dir: str, max_prompt_chars: int = 5000):
        """做什么：初始化 Skill 管理器；为什么：保存目录和 prompt 预算配置。"""
        self.root_dir = Path(root_dir).expanduser().resolve()
        self.max_prompt_chars = max_prompt_chars
        self._skills: List[Skill] = []
        self._errors: List[str] = []

    @property
    def skills(self) -> List[Skill]:
        """做什么：返回当前技能列表；为什么：防止外部直接修改内部状态。"""
        return list(self._skills)

    @property
    def errors(self) -> List[str]:
        """做什么：返回加载错误；为什么：便于 API 和日志展示。"""
        return list(self._errors)

    def load(self) -> List[Skill]:
        """做什么：扫描目录并加载 Skills；为什么：启动和热加载都需要同一套逻辑。"""
        loaded: List[Skill] = []
        errors: List[str] = []

        if not self.root_dir.exists():
            logger.info("Skill 目录不存在，跳过加载: %s", self.root_dir)
            self._skills = []
            self._errors = []
            return []

        for path in self._discover_files(self.root_dir):
            try:
                skill = self._load_file(path)
                if skill is not None:
                    loaded.append(skill)
            except Exception as ex:
                message = f"{path}: {ex}"
                errors.append(message)
                logger.warning("Skill 加载失败: %s", message)

        self._skills = loaded
        self._errors = errors
        self._log_loaded_skills()
        return self.skills

    def reload(self) -> List[Skill]:
        """做什么：提供热加载入口；为什么：让 /skills/reload 直接复用。"""
        return self.load()

    def prompt_for(self, message: str, agent_type: Optional[str] = None) -> str:
        """做什么：为请求构建 Skill prompt；为什么：把规则按需注入到对应 Agent。"""
        blocks: List[str] = []
        matched: List[tuple[Skill, List[str]]] = []
        remaining = self.max_prompt_chars
        lowered_message = (message or "").lower()

        for skill in self._skills:
            if not skill.matches(message, agent_type):
                continue

            matched_keywords = [keyword for keyword in skill.keywords if keyword.lower() in lowered_message]
            block = skill.to_prompt_block()
            if len(block) > remaining:
                block = block[:remaining].rstrip() + "\n..."
            blocks.append(block)
            matched.append((skill, matched_keywords))
            remaining -= len(block)
            if remaining <= 0:
                break

        if not blocks:
            logger.debug("Skills 未命中: agent=%s message=%r", agent_type or "all", (message or "")[:80])
            return ""

        detail = "; ".join(
            f"{skill.name}(keywords={', '.join(keywords) if keywords else 'all'})"
            for skill, keywords in matched
        )
        logger.info("Skills 已注入: agent=%s matched=%s message=%r", agent_type or "all", detail, (message or "")[:80])

        return (
            "以下是当前请求可用的 MallPilot Skills。\n"
            "请优先遵循这些业务规则；如果与系统角色或安全边界冲突，以系统角色和安全边界为准。\n\n"
            + "\n\n".join(blocks)
        )

    def summary(self) -> Dict[str, Any]:
        """做什么：返回 Skill 管理摘要；为什么：供 /skills 接口和日志排查使用。"""
        return {
            "root_dir": str(self.root_dir),
            "count": len(self._skills),
            "skills": [skill.to_summary() for skill in self._skills],
            "errors": self.errors,
        }

    def _log_loaded_skills(self) -> None:
        """做什么：输出加载结果日志；为什么：方便确认新 Skills 是否生效。"""
        lines = [
            "",
            "================ MallPilot Skills Loaded ================",
            f"目录: {self.root_dir}",
            f"数量: {len(self._skills)}",
        ]

        if self._skills:
            for index, skill in enumerate(self._skills, start=1):
                agents = ", ".join(skill.agents) if skill.agents else "all"
                keywords = ", ".join(skill.keywords[:8]) if skill.keywords else "all"
                if len(skill.keywords) > 8:
                    keywords += ", ..."
                lines.extend(
                    [
                        f"{index}. {skill.name}",
                        f"   agents: {agents}",
                        f"   keywords: {keywords}",
                        f"   path: {skill.path}",
                    ]
                )
        else:
            lines.append("未加载任何 Skill。")

        if self._errors:
            lines.append("解析错误:")
            lines.extend(f"  - {error}" for error in self._errors)

        lines.append("=========================================================")
        logger.info("\n".join(lines))

    def _discover_files(self, root_dir: Path) -> Iterable[Path]:
        """做什么：发现可加载文件；为什么：优先读取目录规范文件 SKILL.md。"""
        skill_md_files = sorted(root_dir.rglob("SKILL.md"))
        yielded = {path.resolve() for path in skill_md_files}
        for path in skill_md_files:
            yield path

        for path in sorted(root_dir.rglob("*")):
            resolved = path.resolve()
            if resolved in yielded or not path.is_file():
                continue
            if path.name.startswith(".") or path.name.upper() == "README.MD":
                continue
            if path.suffix.lower() in self.SUPPORTED_SUFFIXES:
                yield path

    def _load_file(self, path: Path) -> Optional[Skill]:
        """做什么：分派不同文件格式加载；为什么：保持外层调用逻辑简单。"""
        if path.suffix.lower() == ".json":
            return self._load_json(path)
        return self._load_text(path)

    def _load_json(self, path: Path) -> Optional[Skill]:
        """做什么：加载 JSON Skill；为什么：兼容结构化配置格式。"""
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("JSON Skill 必须是对象格式")

        content = str(raw.get("content") or raw.get("instructions") or "").strip()
        if not content:
            raise ValueError("缺少 content 或 instructions")

        return Skill(
            name=str(raw.get("name") or path.stem),
            description=str(raw.get("description") or ""),
            content=content,
            path=str(path),
            keywords=self._as_list(raw.get("keywords")),
            agents=[item.lower() for item in self._as_list(raw.get("agents"))],
            enabled=self._as_bool(raw.get("enabled"), default=True),
        )

    def _load_text(self, path: Path) -> Optional[Skill]:
        """做什么：加载文本或 Markdown Skill；为什么：SKILL.md 是主流维护方式。"""
        raw = path.read_text(encoding="utf-8")
        meta, body = self._split_front_matter(raw)
        body = body.strip()
        if not body:
            return None

        default_name = path.parent.name if path.name == "SKILL.md" else path.stem
        name = str(meta.get("name") or self._first_heading(body) or default_name)
        body = self._strip_first_heading(body, name)

        return Skill(
            name=name,
            description=str(meta.get("description") or ""),
            content=body,
            path=str(path),
            keywords=self._as_list(meta.get("keywords")),
            agents=[item.lower() for item in self._as_list(meta.get("agents"))],
            enabled=self._as_bool(meta.get("enabled"), default=True),
        )

    def _split_front_matter(self, raw: str) -> tuple[Dict[str, Any], str]:
        """做什么：解析简易 front matter；为什么：不引入额外 YAML 依赖。"""
        text = raw.lstrip()
        if not text.startswith("---"):
            return {}, raw

        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return {}, raw

        meta: Dict[str, Any] = {}
        end_index: Optional[int] = None
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                end_index = index
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip("\"'")

        if end_index is None:
            return {}, raw
        return meta, "\n".join(lines[end_index + 1 :])

    @staticmethod
    def _first_heading(body: str) -> Optional[str]:
        """做什么：读取首个 Markdown 标题；为什么：在未配置 name 时提供默认值。"""
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip() or None
        return None

    @staticmethod
    def _strip_first_heading(body: str, name: str) -> str:
        """做什么：移除重复标题；为什么：避免 prompt 中同一标题出现两次。"""
        lines = body.splitlines()
        if not lines:
            return body
        first = lines[0].strip()
        if first.startswith("#") and first.lstrip("#").strip() == name:
            return "\n".join(lines[1:]).strip()
        return body

    @staticmethod
    def _as_list(value: Any) -> List[str]:
        """做什么：把字段转成字符串列表；为什么：兼容逗号文本和原生数组。"""
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _as_bool(value: Any, default: bool = False) -> bool:
        """做什么：把字段转成布尔值；为什么：兼容文本化配置。"""
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}
