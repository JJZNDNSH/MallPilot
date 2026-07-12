from pathlib import Path


OBSERVABILITY_ROOT = Path("mallpilot/app/web/observability")


# 验证观测页提供轮次下拉容器。
def test_observability_page_has_turn_selector():
    html = (OBSERVABILITY_ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="turnSelect"' in html
    assert 'id="refreshTurns"' in html
    assert 'id="summary"' in html
    assert 'id="userInput"' in html
    assert 'id="groups"' in html


# 验证观测页脚本调用 turns 和 summary API。
def test_observability_script_uses_turns_and_summary_api():
    script = (OBSERVABILITY_ROOT / "app.js").read_text(encoding="utf-8")

    assert "fetch('/api/trace/turns')" in script
    assert "fetch(`/api/trace/turns/${turnId}/summary`)" in script
    assert "renderTurnOptions" in script
    assert "renderUserInput" in script
    assert "renderGroups" in script
    assert "renderTimeline" in script
    assert "renderDetail" in script


# 验证样式包含错误和慢事件状态。
def test_observability_styles_include_error_and_slow_states():
    css = (OBSERVABILITY_ROOT / "style.css").read_text(encoding="utf-8")

    assert ".timeline-item.is-error" in css
    assert ".timeline-item.is-slow" in css
    assert ".group-card.is-error" in css
