"""把微信聊天记录导出文本里的真实身份换成化名（在本机跑，原文不出这台电脑）。

为什么要有这个脚本
------------------
B-04 需要 20 条真实记录，但真实记录里全是真名、群名、学校名。规范 3.3 与
AGENTS.md 都要求"不写真实人名/组织名"。手工替换几十个名字既慢又容易漏，
所以做成一张"替换表 + 一键执行"。

分工（重要）
------------
- 去真名（本脚本）：必须在你自己的电脑上跑。原文一旦发到模型服务，就等于
  已经离开这台机器了。
- 收拾格式、切分、编号：脱敏之后再做，这两步可以交给我。

用法
----
1) 先写一张替换表，一行一条 `真名=化名`，`#` 开头是注释：

    # map.txt
    张三=P01
    李四=P02
    某某大学辩论队=某校辩论队
    南门烧烤=某餐厅

2) 跑：

    python scripts/redact-chat.py --file data/raw/wx-debate.txt --map data/raw/map.txt

   默认输出 `data/raw/wx-debate.redacted.txt`，并打印"每个词替换了几次"和
   "还剩哪些可疑残留"（11 位数字、邮箱、@真名）。

3) 检查报告里"可疑残留"为空，再把脱敏版交给别人。

注意
----
本脚本只做字符串替换，不做语义判断。替换表没写进去的名字，它不会替你猜。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SUSPICIOUS = [
    ("11 位数字（疑似手机号）", re.compile(r"(?<!\d)1\d{10}(?!\d)")),
    ("邮箱", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("疑似身份证/学号（15–18 位数字）", re.compile(r"(?<!\d)\d{15,18}(?!\d)")),
    ("疑似未替换的 @提及", re.compile(r"@(?!P\d{2}\b)[^\s@]{1,12}")),
    ("疑似网址", re.compile(r"https?://\S+")),
]


def load_map(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"替换表这一行缺 '='：{line!r}")
        src, dst = line.split("=", 1)
        pairs.append((src.strip(), dst.strip()))
    if not pairs:
        raise SystemExit("替换表是空的")
    # 长的先替换，避免"张三丰"被"张三"截断
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)


def redact(text: str, pairs: list[tuple[str, str]]) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    for src, dst in pairs:
        n = text.count(src)
        if n:
            counts[src] = n
            text = text.replace(src, dst)
    return text, counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, required=True, help="原始导出文本")
    ap.add_argument("--map", type=Path, required=True, help="替换表（真名=化名）")
    ap.add_argument("--out", type=Path, default=None, help="默认 <file>.redacted.txt")
    args = ap.parse_args()

    pairs = load_map(args.map)
    text = args.file.read_text(encoding="utf-8", errors="replace")

    # 统一换行与全角空格，方便后续切分（不改变文字内容）
    text = text.replace("\r\n", "\n").replace("\u3000", " ")
    text = re.sub(r"\n{3,}", "\n\n", text)

    redacted, counts = redact(text, pairs)

    out = args.out or args.file.with_suffix(".redacted.txt")
    out.write_text(redacted, encoding="utf-8")

    print(f"已写出：{out}")
    print(f"替换 {len(counts)} 个词，共 {sum(counts.values())} 处：")
    for src, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {src} × {n}")

    leftovers: list[str] = []
    for name, pattern in SUSPICIOUS:
        hits = pattern.findall(redacted)
        if hits:
            uniq = sorted(set(hits))[:5]
            leftovers.append(f"{name}：{len(hits)} 处，例 {uniq}")
    if leftovers:
        print("\n可疑残留（请人工确认后再外发）：")
        for item in leftovers:
            print(f"  - {item}")
    else:
        print("\n未发现手机号/邮箱/学号/未替换的 @提及。")

    for src, dst in pairs:
        if src in counts and dst in redacted and len(dst) <= 6:
            pass  # 化名本身出现在文中是正常的
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
