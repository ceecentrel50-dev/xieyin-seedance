# -*- coding: utf-8 -*-
"""谐音梗 × Seedance 提示词自检器。

只验"能机器判定"的规则。谐音像不像、句子像不像人说的，机器判不了。

用法：
    python check_script.py 稿子.md
    python check_script.py 稿子.md --json
    python check_script.py --corpus      # 拿 19 条原始语料跑一遍，看它能抓出什么
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from corpus_stats import (  # noqa: E402
    BODY_MARK, DEFAULT, extract_dialogue, extract_quotes, load_scripts, split_body,
)

SOFT_TRANSITIONS = ("淡入", "淡出", "溶解", "叠化", "闪白", "转场", "推拉", "划像", "擦除")
NEGATION = ("不使用", "不得使用", "禁用", "禁止", "不许", "无")

CN_NUM = "0-9一二两三四五六七八九十百半几两"
DURATION_PATTERNS = [
    (re.compile(rf"[{CN_NUM}]+\s*(?:秒钟|秒)"), "秒"),
    (re.compile(rf"[{CN_NUM}]+\s*(?:分钟|小时)"), "分钟/小时"),
    (re.compile(rf"[{CN_NUM}]+\s*帧"), "帧"),
    (re.compile(r"\b\d+\s*(?:s|sec|secs|second|seconds|ms)\b", re.I), "s/second"),
    (re.compile(r"\b\d+\s*(?:min|mins|minute|minutes|hour|hours)\b", re.I), "min/hour"),
    (re.compile(r"\b\d+\s*(?:frames?)\b", re.I), "frame"),
    (re.compile(rf"第\s*[{CN_NUM}]+\s*秒"), "第N秒"),
]
TIMECODE_PATTERNS = [
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"\b\d+\s*[-~至]\s*\d+\s*s\b", re.I),
]
PLATFORM_WORDS = ("Seedance", "Dola", "即梦", "可灵", "海螺", "Sora", "Pika",
                  "Runway", "Veo", "Midjourney", "Kling", "Vidu", "Luma")


def _text(path):
    return io.open(path, encoding="utf-8-sig", errors="replace").read()


def _strip_negations(text):
    out = []
    for sent in re.split(r"(?<=[。；\n])", text):
        if any(n in sent for n in NEGATION) and any(t in sent for t in SOFT_TRANSITIONS):
            continue
        out.append(sent)
    return "".join(out)


def speaker_map(body):
    """谁开过口。中文主语追踪很难做准，这里只需要集合，取引号前 40 字窗口内的 A/B/C。

    第二批语料里大量台词不加引号，所以这里用 extract_dialogue 而不是只认引号，
    否则「谁说过话」会大面积漏判。
    """
    result = {}
    pos = 0
    for q in extract_dialogue(body)[0]:
        idx = body.find(q, pos)
        if idx < 0:
            continue
        pos = idx + len(q)
        for who in set(re.findall(r"[ABC]", body[max(0, idx - 40):idx])):
            result.setdefault(who, 0)
            result[who] += 1
    return result


def card_fields(text):
    """字卡三行：英文 / 谐音 / 本义。新旧两种句式都认。"""
    en = hook = meaning = None
    m = re.search(r"正中显示英文[“\"]([A-Za-z]+)[”\"]", text)
    if m:
        en = m.group(1)
    if not en:
        m = re.search(r"显示[：:]\s*([A-Za-z][A-Za-z(). ]*)", text)
        if m:
            en = m.group(1).strip().rstrip(".,").split("(")[0].strip()
    if not en:
        m = re.search(r"中央显示英文[“\"]([A-Za-z]+)[”\"]", text)
        if m:
            en = m.group(1)

    for pat in (r"下方显示中文[“\"]([^”\"]+)[”\"]", r"下方写着中文([^，。；]+)"):
        m = re.search(pat, text)
        if m:
            hook = m.group(1).strip()
            break
    for pat in (r"上方显示中文[“\"]([^”\"]+)[”\"]", r"上方显示清晰中文[“\"]([^”\"]+)[”\"]",
                r"上方写着中文([^，。；]+)"):
        m = re.search(pat, text)
        if m:
            meaning = m.group(1).strip()
            break
    return en, hook, meaning


def _quoted(text, s):
    if not s:
        return False
    return re.search(r"[“\"「]" + re.escape(s) + r"[”\"」]", text) is not None


def _strip_quotes(text):
    """去掉引号里的台词。

    角色嘴里说的"我排了两小时队"是剧情内容，不是给视频分配运行时长；
    叙述里的"空气安静两秒"才是违规。两者必须分开判。
    """
    return re.sub(r"[“\"「][^”\"」]*[”\"」]", "", text)


def check(text, name="draft"):
    issues = []

    def add(level, code, msg):
        issues.append({"level": level, "code": code, "msg": msg})

    clean = _strip_negations(text)

    # ============ Seedance 交付契约 ============
    # 只查叙述部分的时长；台词里说"排了两小时队"属于剧情，放行。
    narration = _strip_quotes(text)
    for pat, label in DURATION_PATTERNS:
        m = pat.search(narration)
        if m:
            add("FAIL", "DURATION",
                f"叙述里出现运行时长『{m.group(0)}』（{label}）。Seedance 禁止给动作/停顿/运镜分配时长，"
                f"改成『短暂』『一瞬』『随即』。")
            break
    for pat in TIMECODE_PATTERNS:
        m = pat.search(text)
        if m:
            add("FAIL", "TIMECODE", f"出现时间码『{m.group(0)}』，删掉，用动作顺序替代。")
            break
    for w in PLATFORM_WORDS:
        if w.lower() in text.lower():
            add("FAIL", "PLATFORM", f"出现平台名『{w}』，提示词里不写模型名。")
            break
    if re.search(r"--ar\b|\b\d{3,4}p\b|\b4K\b", text, re.I):
        add("FAIL", "PLATFORM", "出现分辨率/参数写法，改用构图语言表达画幅。")
    if re.search(r"\n\s*\n", text.strip()):
        add("FAIL", "SINGLE_BLOCK", "出现空行分段。交付必须是一整段，分段会被当成多次生成。")
    if re.search(r"(?m)^\s*(?:#{1,6}\s|[-*]\s|\d+[.、]\s|【[一二三四五六七八九十]】)", text):
        add("FAIL", "NO_STRUCTURE", "出现标题/项目符号/序号，提示词里不许有结构标记。")

    # ============ 合规头 ============
    for kw, code, msg in [
        ("原创虚构", "HEAD_FICTION", "缺『原创虚构』声明"),
        ("成年", "HEAD_ADULT", "缺『成年人物』声明"),
        ("现实人物", "HEAD_REAL", "缺『不对应任何现实人物』"),
        ("真人肖像", "HEAD_PORTRAIT", "缺『不参考任何真人肖像』"),
        ("名人", "HEAD_CELEB", "缺『不复制任何名人的脸部特征』"),
        ("视线高度接近人物眼睛", "HEAD_EYE", "缺『视线高度接近人物眼睛』"),
    ]:
        if kw not in text:
            add("FAIL", code, msg)

    if "文字只出现在" in text:
        pass
    elif re.search(r"(不生成|不出现|无|禁止)[^。；]{0,8}字幕", text):
        add("WARN", "HEAD_NOSUB",
            "用的是全局字幕禁令，可能把结尾字卡一起压掉。改成"
            "『正片画面不出现任何字幕，文字只出现在结尾的纯白字卡上』。")
    else:
        add("FAIL", "HEAD_NOSUB", "缺字幕声明")

    # ============ 参考图与角色 ============
    # 参考图分四类：人物 / 场景 / 道具 / 宠物。只有「人物」才对应说话的人。
    # 所以 "三张人物参考图 + 参考图四场景" 是自洽的，不是笔误。
    refs = None
    r = re.search(r"使用([两三四五])张人物参考图", text)
    if r:
        refs = {"两": 2, "三": 3, "四": 4, "五": 5}[r.group(1)]
    else:
        add("FAIL", "REF_MISSING", "没写使用几张人物参考图")

    header = text.split(BODY_MARK)[0] if BODY_MARK in text else text[:400]
    kinds = {"cast": 0, "scene": 0, "prop": 0, "pet": 0, "unknown": 0}
    for desc in re.findall(r"参考图[一二三四五]\s*(?:对应|为)([^。；，,]{1,24})", header):
        if "场景" in desc:
            kinds["scene"] += 1
        elif "宠物" in desc:
            kinds["pet"] += 1
        elif "道具" in desc or "玩具" in desc:
            kinds["prop"] += 1
        elif any(k in desc for k in ("人物", "男主", "女主", "男配", "女配", "相框")):
            kinds["cast"] += 1
        else:
            kinds["unknown"] += 1
    listed = set(re.findall(r"参考图([一二三四五])", header))
    if refs and listed:
        # 「N 张人物参考图」的 N 应该等于 人物 + 宠物（宠物也是要出镜的角色），
        # 场景图与道具图不计入 N。
        expected = kinds["cast"] + kinds["pet"]
        if kinds["unknown"] == 0 and expected and expected != refs:
            add("FAIL", "REF_MISMATCH",
                f"声明 {refs} 张人物参考图，实际映射 人物×{kinds['cast']} + 宠物×{kinds['pet']} "
                f"+ 场景×{kinds['scene']} + 道具×{kinds['prop']}，"
                f"按人物+宠物算应是 {expected} 张。")

    body, white = split_body(text)
    body = body.strip()
    if not body:
        add("FAIL", "BODY_MISSING", "找不到【画面内容】正文")
        body = text

    sp = speaker_map(body)
    for who in speaker_map(white):
        sp.setdefault(who, 0)
    if refs and not any(i["code"] == "REF_MISMATCH" for i in issues):
        cap = kinds["cast"] or refs
        if len(sp) > cap:
            add("FAIL", "CAST_OVER",
                f"人物参考图 {cap} 张，却有 {len(sp)} 人说话：{''.join(sorted(sp))}。"
                f"多出来的人没有外观依据，脸会漂。")
        elif len(sp) < cap:
            add("WARN", "CAST_UNDER",
                f"人物参考图 {cap} 张，只有 {len(sp)} 人说话：{'/'.join(sorted(sp))}。")
    if kinds["prop"] and not re.search(r"道具|玩具", text.split("参考图")[-1][:40]):
        add("WARN", "PROP_UNUSED", "声明了道具参考图，但正文没交代道具怎么入画。")

    # ============ 镜头 ============
    if "硬切" not in clean:
        add("FAIL", "CUT_MISSING", "全篇没提『硬切』")
    for t in SOFT_TRANSITIONS:
        if t in clean:
            add("FAIL", "SOFT_CUT", f"出现软转场『{t}』，只能用硬切")

    if not white.strip():
        add("FAIL", "WHITE_MISSING", "找不到白底揭底段")
    elif not (re.search(r"右侧[^。；]{0,12}走入画面", white)
              or "站在空白背景屏幕中间" in white or "纯白" in white):
        add("FAIL", "WHITE_FORM", "白底段格式不对：缺『从一片空白背景中的右侧走入画面』")

    mw = re.search(r"切([A-C、和]{2,8}?)从一片空白背景", white)
    if mw:
        walkers = set(re.findall(r"[ABC]", mw.group(1)))
        after = white[mw.end():]
        fq = re.search(r"[“\"]([^”\"]+)[”\"]", after)
        if fq:
            speakers = re.findall(r"[ABC]", after[:fq.start()])
            if speakers and speakers[0] not in walkers:
                add("FAIL", "WHITE_CAST",
                    f"走进去的是 {''.join(sorted(walkers))}，开口的却是 {speakers[0]}。")

    # ============ 字卡 ============
    en, hook, meaning = card_fields(text)
    has_marker = any(k in text for k in ("上方显示", "下方显示", "上方写着", "下方写着"))
    if has_marker:
        if not meaning:
            add("FAIL", "CARD_MEANING", "字卡缺『本义』（上方那行）")
        if not hook:
            add("FAIL", "CARD_HOOK", "字卡缺『谐音』（下方那行）")
        if not en:
            add("FAIL", "CARD_EN", "字卡缺英文")
        for label, val, limit in (("本义", meaning, 8), ("英文", en, 14), ("谐音", hook, 8)):
            if val and not _quoted(text, val):
                add("FAIL", "TEXT_QUOTE",
                    f"字卡{label}『{val}』没用引号包住，模型会自己改写。")
            if val and len(val) > limit:
                add("WARN", "TEXT_LONG", f"字卡{label}『{val}』有 {len(val)} 字，超过 {limit} 字易糊。")
    elif "像是老师在给学生上课一样" not in text:
        add("FAIL", "CARD_MISSING", "既没有三行字卡，也不是单人授课式结尾")

    # ============ 声音 ============
    teach_only = ("像是老师在给学生上课一样" in text) and not has_marker
    if "标准伦敦腔" not in text and not teach_only:
        add("FAIL", "VOICE_LONDON", "缺『标准伦敦腔』播报")
    if "旁白" not in text and "播音" not in text and not teach_only:
        add("WARN", "VOICE_ANCHOR", "缺画外旁白说明")
    if has_marker and "朗读" not in text:
        add("FAIL", "VOICE_OFF", "字卡后缺朗读说明")

    white_cast = set(re.findall(r"[ABC]", white))
    if "一起说" not in text and not teach_only and len(white_cast) > 1:
        add("WARN", "UNISON", "白底没有齐说句『[本义]，[谐音]』")

    # 授课式只能一个人出镜，而且必须有指词手势
    if teach_only:
        if re.search(r"[ABC]和[ABC]\s*一个人", text):
            add("FAIL", "TEACH_SOLO", "授课式写成两个人一起走：『A和B一个人』，只能出一个人。")
        if "说到" not in text:
            add("WARN", "GESTURE", "授课式缺『说到[EN]时[手势]』，动作落不了地。")

    # ============ 台词体检 ============
    bq, body_quoted = extract_dialogue(body)
    if len(bq) >= 3 and not body_quoted:
        add("WARN", "DIALOGUE_QUOTED",
            "台词没加引号（写成『A说：……。』）。第二批语料里 16/33 条这样写，"
            "模型容易把动作描写也当成台词念出来。建议全部用中文引号包住。")
    chars = sum(len(q) for q in bq)
    # 台词没加引号时，长度只能靠冒号启发式估，量不准，所以只提醒加引号，不拿它判字数。
    if body_quoted:
        if len(bq) < 3:
            add("FAIL", "LINE_FEW", f"正片只有 {len(bq)} 句台词（语料最少 3 句）")
        elif len(bq) > 9:
            add("WARN", "LINE_MANY", f"正片 {len(bq)} 句台词（语料最多 9 句）")
        if chars and chars < 53:
            add("WARN", "CHAR_FEW",
                f"正片台词 {chars} 字，低于语料下限 53（中位 84），冲突可能没铺开")
        if chars > 190:
            add("FAIL", "CHAR_MANY", f"正片台词 {chars} 字，超上限 159")
        longest = max((len(q) for q in bq), default=0)
        if longest > 45:
            add("FAIL", "LINE_LONG", f"最长单句 {longest} 字（语料上限 37）")
        elif longest > 37:
            add("WARN", "LINE_LONGISH", f"最长单句 {longest} 字，略超 37")
    else:
        longest = 0

    core = re.sub(r"[（(].*?[)）]", "", hook or "").strip("，。！？ ")
    if core and core not in body and core not in header:
        add("FAIL", "HOOK_UNPLANTED", f"谐音句『{core}』没在正片出现过。")

    if re.search(r"在一个?房间里|某处|某个房间", body):
        add("WARN", "SCENE_VAGUE", "场景太抽象，会拍成白墙")
    if len(body) < 120:
        add("WARN", "BODY_SHORT", f"正文 {len(body)} 字，空间关系可能没写够")

    fails = sum(1 for i in issues if i["level"] == "FAIL")
    warns = sum(1 for i in issues if i["level"] == "WARN")
    return {"name": name, "pass": fails == 0, "fails": fails, "warns": warns,
            "body_lines": len(bq), "body_chars": chars, "longest": longest,
            "refs": refs, "speakers": "".join(sorted(sp)), "issues": issues}


def report(res):
    flag = "PASS" if res["pass"] else "FAIL"
    print(f"[{flag}] {res['name']}  正片 {res['body_lines']} 句 / {res['body_chars']} 字 / "
          f"最长 {res['longest']} | 参考图 {res['refs']} | 说话人 {res['speakers'] or '-'}")
    for i in res["issues"]:
        mark = "  ✗" if i["level"] == "FAIL" else "  !"
        print(f"{mark} {i['code']}: {i['msg']}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--corpus" in sys.argv:
        from corpus_stats import analyse
        path = args[0] if args else DEFAULT
        if not os.path.exists(path):
            print(f"找不到语料：{path}")
            sys.exit(1)
        rows = [(analyse(b)["en"], b) for b in load_scripts(path)]
        rows = [(e, b) for e, b in rows if e]
        stats = {}
        for e, b in rows:
            for i in check(b, e)["issues"]:
                stats.setdefault(i["code"], []).append(e)
        print(f"语料 {len(rows)} 条，按规则统计触发次数：")
        for code, words in sorted(stats.items(), key=lambda kv: -len(kv[1])):
            print(f"  {code:<14} {len(words):>2} 条  例：{words[0]}")
        return
    if not args:
        print(__doc__)
        sys.exit(2)
    failed = False
    for p in args:
        res = check(_text(p), name=os.path.basename(p))
        if "--json" in sys.argv:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            report(res)
        failed = failed or not res["pass"]
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
