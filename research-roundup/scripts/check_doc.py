#!/usr/bin/env python3
"""交付前自查：检查一份 research-roundup 风格的 Markdown 文档（只读，不执行文档里的任何内容）。

用法:
    python -I check_doc.py 文档.md [--root 证据目录 ...] [--verdicts 属实,大体属实,有误,无法核实,不判定]
                                   [--ignore 正则 ...] [--strict]

检查项:
  1. 表格:    同一张表的每一行列数必须一致（错位的表在渲染时会吞列）。          [错误]
  2. 占位符:  @@、TODO、TBD、XXX、【待补】；--strict 时还查 【填】、（填）。      [错误]
  3. § 引用:  "§1.4"、"§2.1" 这类引用能否在本文的标题里找到。                    [警告，可能引用别的文档]
  4. 编号:    首列为 # / 编号 / 序号 的表，编号在表内递增，同一个 "##" 节内不重复。 [警告]
  5. 行数与判定统计: 每个 "##" 节里带编号的行数；核对表里的判定词计数。            [信息，用来核对开头的计数行]
  6. 证据路径: 反引号里形如 目录/文件.扩展名 的相对路径，在 --root 下是否存在；
              仓库内路径（docs/x.md）也认固定副本的命名 来源_版本前缀_docs_x.md。      [警告]
  7. 链接:    [文字](相对路径) 指向的文件是否存在。                                [警告]

退出码: 有错误(1)才返回 1；警告和信息不影响。
"""
import argparse
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DEFAULT_VERDICTS = ["属实", "大体属实", "有误", "无法核实", "不判定"]
NUM_HEADERS = {"#", "编号", "序号", "no", "no.", "id"}
VERDICT_HEADER = re.compile(r"核对结果|判定|verdict", re.I)
PLACEHOLDERS = [r"@@", r"\bTODO\b", r"\bTBD\b", r"\bXXX\b", r"【待补】"]
STRICT_PLACEHOLDERS = [r"【填", r"（填"]
# "论文 §3.2"、"论文 impute-flow-demo：§3.2"、"`某文件` §1"、"1023 调研 §1.7" 这类 § 引用指向别的文档，不在本文找标题
EXTERNAL_REF = re.compile(
    r"(调研|号文档|号|档案|文档|论文|文章|文献|原文|报告|规则|附录|[Pp]aper|[Ss]ection|`|\.md)[\s:：（(]*[\w\-.]*[\s:：（(]*$"
)


def split_cells(line):
    """按未转义的竖线切分表格行，返回单元格文本列表。"""
    s = line.strip()
    s = s.replace("\\|", "\u0000")
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.replace("\u0000", "|").strip() for c in s.split("|")]


def is_separator(cells):
    return all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells if c != "") and any(cells)


def load(path):
    text = open(path, encoding="utf-8-sig", newline="").read()
    return text.replace("\r\n", "\n").split("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--root", action="append", default=[], help="证据目录；反引号里的相对路径在其下查找")
    ap.add_argument("--verdicts", default=",".join(DEFAULT_VERDICTS), help="判定词，逗号分隔")
    ap.add_argument("--ignore", action="append", default=[], help="忽略匹配此正则的证据路径（例如仓库内路径）")
    ap.add_argument("--strict", action="store_true", help="把 【填】/（填） 也当作未完成的占位符")
    args = ap.parse_args()

    lines = load(args.doc)
    doc_dir = os.path.dirname(os.path.abspath(args.doc))
    errors, warnings = [], []

    # ---------- 扫描: 代码围栏、标题、表格 ----------
    in_fence = False
    headings = []  # (line_no, level, text)
    tables = []  # dict(start, header, rows[(line_no, cells)], section)
    current_h2 = "(开头)"
    cur = None
    for i, raw in enumerate(lines, 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            cur = None
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", raw)
        if m:
            level = len(m.group(1))
            headings.append((i, level, m.group(2)))
            if level <= 2:
                current_h2 = m.group(2)
            cur = None
            continue
        if raw.lstrip().startswith("|"):
            cells = split_cells(raw)
            if cur is None:
                cur = {"start": i, "header": cells, "rows": [], "section": current_h2, "sep": False}
                tables.append(cur)
            elif not cur["sep"] and is_separator(cells):
                cur["sep"] = True
            else:
                cur["rows"].append((i, cells))
        else:
            cur = None

    # ---------- 1. 表格列数 ----------
    for t in tables:
        n = len(t["header"])
        for ln, cells in t["rows"]:
            if len(cells) != n:
                errors.append(f"表格列数不一致: 第 {ln} 行有 {len(cells)} 列，表头（第 {t['start']} 行）有 {n} 列")
                break

    # ---------- 2. 占位符 ----------
    pats = PLACEHOLDERS + (STRICT_PLACEHOLDERS if args.strict else [])
    in_fence = False
    for i, raw in enumerate(lines, 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for p in pats:
            if re.search(p, raw):
                errors.append(f"残留占位符 {p!r}: 第 {i} 行: {raw.strip()[:60]}")
                break

    # ---------- 3. § 引用 ----------
    head_ids = set()
    for _, _, text in headings:
        m = re.match(r"^(\d+(?:\.\d+)*)[.．、\s]", text + " ")
        if m:
            head_ids.add(m.group(1))
    refs = {}
    in_fence = False
    for i, raw in enumerate(lines, 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in re.finditer(r"§\s?(\d+(?:\.\d+)*)", raw):
            before = raw[max(0, m.start() - 40):m.start()]
            if EXTERNAL_REF.search(before):
                continue
            refs.setdefault(m.group(1), []).append(i)
    for r, where in sorted(refs.items()):
        if r not in head_ids:
            warnings.append(f"§{r} 在本文里找不到对应标题（第 {', '.join(map(str, where[:5]))} 行引用；若引的是别的文档可忽略）")

    # ---------- 4/5. 编号与行数、判定统计 ----------
    info = []
    per_section = {}
    verdict_vocab = sorted([v.strip() for v in args.verdicts.split(",") if v.strip()], key=len, reverse=True)
    tally, other_rows, tally_tables = {}, [], 0
    for t in tables:
        h0 = t["header"][0].strip("* ").lower() if t["header"] else ""
        nums = []
        if h0 in NUM_HEADERS:
            for ln, cells in t["rows"]:
                m = re.match(r"^\**\s*(\d+)\s*\**$", cells[0]) if cells else None
                if m:
                    nums.append((int(m.group(1)), ln))
            for a, b in zip(nums, nums[1:]):
                if b[0] <= a[0]:
                    warnings.append(f"编号未递增: 第 {b[1]} 行的 {b[0]} 不大于上一行的 {a[0]}")
                    break
            per_section.setdefault(t["section"], []).extend(nums)
        # 判定统计
        vi = next((k for k, h in enumerate(t["header"]) if VERDICT_HEADER.search(h)), None)
        if vi is not None:
            tally_tables += 1
            for ln, cells in t["rows"]:
                if vi >= len(cells):
                    continue
                cell = cells[vi].replace("*", "").strip()
                head = cell[:24]
                hit = None
                if "不判定" in head:
                    hit = "不判定" if "不判定" in verdict_vocab else None
                if hit is None:
                    for v in verdict_vocab:
                        if cell.lstrip("（(").startswith(v):
                            hit = v
                            break
                if hit is None:
                    other_rows.append((ln, cell[:20]))
                    hit = "(其他)"
                tally[hit] = tally.get(hit, 0) + 1
    for sec, nums in per_section.items():
        vals = [n for n, _ in nums]
        dup = sorted({n for n in vals if vals.count(n) > 1})
        if dup:
            warnings.append(f"节「{sec}」里编号重复: {dup[:10]}（若各表各自从 1 编起，这是预期的）")
        if vals:
            info.append(f"节「{sec[:30]}」: 带编号的行 {len(vals)} 行，编号 {min(vals)}–{max(vals)}")
    if tally_tables:
        order = verdict_vocab + ["(其他)"]
        parts = [f"{k} {tally[k]}" for k in order if k in tally]
        total_judged = sum(v for k, v in tally.items() if k not in ("不判定", "(其他)"))
        info.append(f"核对表（{tally_tables} 张）判定统计: " + "、".join(parts) + f"；做了判定的共 {total_judged} 条")
        if other_rows:
            info.append("  未识别判定词的行: " + "; ".join(f"第 {ln} 行「{c}」" for ln, c in other_rows[:8]))

    # ---------- 6. 证据路径 ----------
    if args.root:
        ignores = [re.compile(p) for p in args.ignore]
        file_names = set()
        budget = 20000  # 每个目录最多登记这么多文件名，防止 --root 指到很大的目录
        for r in args.root:
            n = 0
            for _, _, fs in os.walk(r):
                file_names.update(fs)
                n += len(fs)
                if n > budget:
                    break
        seen = set()
        in_fence = False
        for i, raw in enumerate(lines, 1):
            if raw.lstrip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in re.finditer(r"`([^`\n]+)`", raw):
                tok = m.group(1).strip()
                if tok in seen:
                    continue
                if not re.search(r"[/\\]", tok) or not re.search(r"\.[A-Za-z0-9]{1,8}$", tok):
                    continue
                if re.search(r"\s|https?://|[*…<>]", tok):
                    continue
                if any(p.search(tok) for p in ignores):
                    continue
                seen.add(tok)
                rel = tok.replace("\\", "/")
                if any(os.path.exists(os.path.join(r, rel)) for r in args.root):
                    continue
                flat = rel.strip("/").replace("/", "_")
                if any(name == flat or name.endswith("_" + flat) for name in file_names):
                    continue  # 仓库内路径，固定副本按"来源_版本前缀_路径"命名存在
                warnings.append(f"证据路径不存在: `{tok}`（第 {i} 行；仓库内路径若没存副本，可用 --ignore 过滤）")

    # ---------- 7. 链接 ----------
    in_fence = False
    for i, raw in enumerate(lines, 1):
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in re.finditer(r"\[[^\]\n]*\]\(([^)\s]+)\)", raw):
            target = m.group(1).split("#")[0]
            if not target or re.match(r"^(https?:|mailto:)", target) or "【" in target:
                continue  # 空链接、外链、模板里还没填的占位链接（占位符由第 2 项检查）
            if not os.path.exists(os.path.join(doc_dir, target)):
                warnings.append(f"链接目标不存在: {target}（第 {i} 行）")

    # ---------- 输出 ----------
    print(f"文件: {args.doc}  行数 {len(lines)}  表 {len(tables)} 张  标题 {len(headings)} 个")
    for s in info:
        print("信息:", s)
    for w in warnings:
        print("警告:", w)
    for e in errors:
        print("错误:", e)
    print(f"结果: 错误 {len(errors)}，警告 {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
