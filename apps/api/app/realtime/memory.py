"""Bounded, attributable conversation memory; never promotes model claims to facts."""

from html import escape

from app.models import VoiceSession

MEMORY_CHAR_BUDGET = 12000
RECENT_MESSAGES = 12


def build_memory(session: VoiceSession) -> dict:
    reliable = [
        item for item in session.utterances if item.is_final and item.transcript_status == "final"
    ]
    recent = reliable[-RECENT_MESSAGES:]
    earlier = reliable[:-RECENT_MESSAGES]
    # Extractive fallback avoids requiring another model/key or inventing a summary.
    # Keep attributable excerpts from each older connection segment.
    groups: dict[int, list] = {}
    for item in earlier:
        groups.setdefault(item.connection_epoch, []).append(item)
    excerpts = []
    for epoch, items in groups.items():
        user_items = [item for item in items if item.speaker == "user"]
        chosen = user_items[:2] + user_items[-2:]
        seen = set()
        for item in chosen:
            if item.id in seen:
                continue
            seen.add(item.id)
            excerpts.append(
                f"段{epoch} / 消息{item.sequence_no} / 用户原话摘录：{item.transcript[:400]}"
            )
    recent_text = []
    for item in recent:
        label = "用户原话" if item.speaker == "user" else "AI先前回答（未独立核实）"
        if item.speaker == "assistant" and item.playback_status != "completed":
            label += "（不能假定用户已听完）"
        recent_text.append(f"消息{item.sequence_no} / {label}：{item.transcript[:600]}")
    recent_block = "\n".join(recent_text)
    old_block = "\n".join(excerpts)
    remaining = max(0, MEMORY_CHAR_BUDGET - len(recent_block) - 120)
    omitted = len(old_block) > remaining or any(len(i.transcript) > 600 for i in recent)
    selected = []
    for line in excerpts[:2] + list(reversed(excerpts[2:])):
        if line not in selected and len(line) + 1 <= remaining:
            selected.append(line)
            remaining -= len(line) + 1
    old_block = "\n".join(selected)
    text = f"较早对话摘录（有省略，不能视为完整记忆）：\n{old_block}\n最近对话：\n{recent_block}"
    return {
        "strategy": "extractive-v2",
        "through_sequence": max((i.sequence_no for i in reliable), default=0),
        "reliable_messages": len(reliable),
        "has_omissions": bool(earlier) or omitted,
        "text": text[:MEMORY_CHAR_BUDGET],
    }


def render_markdown(session: VoiceSession) -> str:
    def literal(text: str) -> str:
        return (
            escape(text)
            .replace("\\", "\\\\")
            .replace("`", "\\`")
            .replace("[", "\\[")
            .replace("*", "\\*")
        )

    lines = [
        "# 中文对话记录",
        "",
        f"会话：{session.id}",
        f"目标：{literal(str(session.context_pack.get('objective', '')))}",
        "",
        "说明：AI 回答未经独立核实；部分内容可能未播放完成。",
        "",
    ]
    epoch = None
    for item in session.utterances:
        if epoch != item.connection_epoch:
            epoch = item.connection_epoch
            lines += [f"## 连接段 {epoch}", ""]
        label = "用户" if item.speaker == "user" else "AI"
        lines += [
            f"### {item.sequence_no}. {label}",
            f"转写：{item.transcript_status}；播放：{item.playback_status}",
            "",
        ]
        lines += ["> " + literal(line) for line in item.transcript.splitlines()]
        lines.append("")
    return "\n".join(lines)
