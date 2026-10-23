# -*- coding: utf-8 -*-
"""从原始语料统计结构常量。

只做一件事：把"感觉"换成数字。写进 SKILL.md 的每个区间都必须由本脚本产出，
不允许凭印象填。

用法：
    python corpus_stats.py            # 打印 JSON
    python corpus_stats.py --table    # 打印人读表
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_corpus():
    """先找 skill 自带的语料（安装到任何地方都能跑），再回退到工作区的原始语料。"""
    bundled = os.path.join(HERE, "..", "assets", "corpus.txt")
    if os.path.exists(bundled):
        return os.path.normpath(bundled)
    d = HERE
    for _ in range(7):
        cand = os.path.join(d, "剧本学习", "raw", "学英语剧本.txt")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return ""


DEFAULT = _find_corpus()

BODY_MARK = "【画面内容】"
START_FALLBACK = "专业摄像机拍摄"

WORD_RE = re.compile(r"显示[：:]\s*([A-Za-z]+)")
WORD_RE_LONG = re.compile(r"中央显示英文[“\"]([A-Za-z]+)[”\"]")
QUOTE_CHARS = "“”\"「」"

WHITE_STARTS = (
    "切A和B从一片空白背景",
    "切A、B和C站在空白背景",
    "切B和C从一片空白背景",
    "切B从一片空白背景",
    "切C从一片空白背景",
    "切A从一片空白背景",
    "切A和B站在屏幕中间",
    "切B和C站在屏幕中间",
    "切A、B和C站在屏幕中间",
    "直接硬切至纯白色背景",
    "随后硬切整个屏幕纯白背景显示",
)


def is_garbage(text):
    """doc→txt 转换残留的二进制尾巴。"""
    weird = sum(1 for ch in text if ord(ch) < 9 or 0xE000 <= ord(ch) <= 0xF8FF)
    return weird > len(text) * 0.05


def load_scripts(path):
    raw = io.open(path, encoding="utf-8-sig", errors="replace").read()
    blocks = [b.replace("\n", "").strip() for b in re.split(r"\n\s*\n+", raw)]
    return [b for b in blocks if b and not is_garbage(b)]


def detect_format(text):
    if BODY_MARK in text:
        return "A_standard" if "上方写着中文" in text else "A_teacher"
    if "作为唯一角色外观依据" in text:
        return "A_detailed"
    return "unknown"


WHITE_KWS = ("从一片空白背景", "整个屏幕纯白背景", "纯白色背景", "纯白的背景",
             "空白背景屏幕中间", "切空白背景", "从画面右侧", "一片纯白的背景")


def _white_cut(body):
    """白底起点：第一个"空白背景/纯白背景"句的句首（回退到最近的"切"）。"""
    hits = [body.find(kw) for kw in WHITE_KWS]
    hits = [h for h in hits if h > 0]
    if not hits:
        return len(body)
    first = min(hits)
    back = body.rfind("切", max(0, first - 60), first)
    if back >= 0:
        return back
    dot = body.rfind("。", 0, first)
    return dot + 1 if dot >= 0 else first


def split_body(text):
    """返回（正片, 白底段）。正片 = 场景+对白；白底段 = 从入场句/揭底句到结尾。"""
    if BODY_MARK in text:
        start = text.index(BODY_MARK) + len(BODY_MARK)
    else:
        idx = text.find(START_FALLBACK)
        start = idx if idx >= 0 else 0
    body = text[start:]
    cut = _white_cut(body)
    return body[:cut], body[cut:]


def extract_quotes(text):
    """语料里的引号开闭混用（“ ... " ... ”），按出现顺序成对切，不依赖配对类型。"""
    out, buf, inside = [], [], False
    for ch in text:
        if ch in QUOTE_CHARS:
            if inside:
                seg = "".join(buf).strip()
                if seg and not seg.endswith(("：", ":", "说", "道")):
                    out.append(seg)
                buf, inside = [], False
            else:
                buf, inside = [], True
        elif inside:
            buf.append(ch)
    return out


def extract_dialogue(text):
    """抽台词，返回 (台词列表, 是否带引号)。

    第二批语料里有大量台词不加引号，直接写成「A说：台词。」。所以引号不够用时
    回退到冒号切分。这个回退是近似值，只用来估长度；结构判断以引号为准。
    """
    q = extract_quotes(text)
    if len(q) >= 2:
        return q, True
    out = []
    for seg in re.split(r"[：:]", text)[1:]:
        # 一段台词到句号、或者到下一个镜头标记（切A/切B/切C/硬切）为止。
        # 不能只看句号：台词常以「！」收尾，后面直接接下一个镜头。
        cut = len(seg)
        for m in re.finditer(r"。|切[A-C]|硬切", seg):
            if m.start() > 0:
                cut = m.start()
                break
        t = seg[:cut].strip("。！？ 　")
        if not t or t.startswith(("切", "硬切", "画")):
            continue
        out.append(t)
    return out, False


def analyse(text):
    fmt = detect_format(text)
    m = WORD_RE.search(text) or WORD_RE_LONG.search(text)
    en = m.group(1).lower() if m else ""
    body, white = split_body(text)
    if not en:
        # 授课式结尾没有文字卡，英文词藏在最后一句讲解里
        tail = re.findall(r"[A-Za-z]{3,}", white or text)
        en = tail[-1].lower() if tail else ""
    bq, quoted = extract_dialogue(body)
    wq = extract_quotes(white)
    quotes = bq + wq
    refs = None
    r = re.search(r"使用([两三四五])张人物参考图", text)
    if r:
        refs = {"两": 2, "三": 3, "四": 4, "五": 5}[r.group(1)]
    return {
        "fmt": fmt,
        "en": en,
        "refs": refs,
        "lines": len(quotes),
        "chars": sum(len(q) for q in quotes),
        "body_lines": len(bq),
        "body_chars": sum(len(q) for q in bq),
        "white_lines": len(wq),
        "avg": round(sum(len(q) for q in quotes) / len(quotes), 1) if quotes else 0,
        "longest": max((len(q) for q in quotes), default=0),
        "has_card": ("上方写着中文" in text) or ("上方显示清晰中文" in text),
        "has_broadcast": "标准伦敦腔" in text,
        "teach_mode": "像是老师在给学生上课一样" in text,
        "unison": "一起说" in text,
        "quoted": quoted,
    }


def band(values, name):
    v = sorted(values)
    n = len(v)
    p = lambda q: v[max(0, min(n - 1, int(round(q * (n - 1)))))]
    return {
        "name": name, "n": n, "min": v[0],
        "p25": p(0.25), "median": p(0.5), "p75": p(0.75), "max": v[-1],
        "mean": round(sum(v) / n, 1),
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else DEFAULT
    if not path or not os.path.exists(path):
        print("找不到语料。请把语料放到 assets/corpus.txt，或作为参数传入路径。")
        sys.exit(1)
    rows = [analyse(s) for s in load_scripts(path)]
    rows = [r for r in rows if r["en"]]
    std = [r for r in rows if r["fmt"] == "A_standard"]
    out = {
        "source": os.path.abspath(path),
        "count": len(rows),
        "by_format": {f: sum(1 for r in rows if r["fmt"] == f) for f in sorted({r["fmt"] for r in rows})},
        "STD_body_chars": band([r["body_chars"] for r in std], "正片台词字数"),
        "STD_body_lines": band([r["body_lines"] for r in std], "正片台词条数"),
        "STD_white_lines": band([r["white_lines"] for r in std], "白底台词条数"),
        "STD_longest": band([r["longest"] for r in std], "最长单句"),
        "ALL_body_chars": band([r["body_chars"] for r in rows], "全部正片台词字数"),
        "refs_2": sum(1 for r in rows if r["refs"] == 2),
        "refs_3": sum(1 for r in rows if r["refs"] == 3),
        "with_card": sum(1 for r in rows if r["has_card"]),
        "with_broadcast": sum(1 for r in rows if r["has_broadcast"]),
        "teach_mode": sum(1 for r in rows if r["teach_mode"]),
        "unison": sum(1 for r in rows if r["unison"]),
        "unquoted": sum(1 for r in rows if not r["quoted"]),
        "refs_4": sum(1 for r in rows if r["refs"] == 4),
        "rows": rows,
    }
    if "--table" in sys.argv:
        head = f"{'word':<12}{'fmt':<13}{'refs':>5}{'body':>6}{'bch':>6}{'wln':>5}{'max':>5}{'q':>3}"
        print(head)
        print("-" * len(head))
        for r in rows:
            print(f"{r['en']:<12}{r['fmt']:<13}{str(r['refs']):>5}{r['body_lines']:>6}"
                  f"{r['body_chars']:>6}{r['white_lines']:>5}{r['longest']:>5}"
                  f"{'Y' if r['quoted'] else 'n':>3}")
        print()
        for k in ("ALL_body_chars", "STD_body_chars", "STD_body_lines",
                  "STD_white_lines", "STD_longest"):
            print(k, out[k])
        print(f"refs2={out['refs_2']} refs3={out['refs_3']} refs4={out['refs_4']} "
              f"card={out['with_card']} broadcast={out['with_broadcast']} "
              f"teach={out['teach_mode']} unison={out['unison']} unquoted={out['unquoted']}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
