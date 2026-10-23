# -*- coding: utf-8 -*-
"""三元组 → 剧本骨架。

入口是「单词 | 翻译 | 谐音」，不是题材。这个脚本只干一件事：
把三元组填进一个格式已经正确的骨架里，你只需补场景和台词。

用法：
    python make_skeleton.py "dangerous|危险的|单脚窝屎"
    python make_skeleton.py "dangerous|危险的|单脚窝屎" --mode card
    python make_skeleton.py "holiday，假日，耗了一天" --refs 3 --out draft.md

    --mode teach  授课式结尾（默认，语料主流）
    --mode card   三行字卡结尾
    --refs N      人物参考图张数，默认 3
"""
import argparse
import re
import sys

SEP = re.compile(r"\s*(?:\||｜|；|;|，|,|、|/)\s*|\s+-\s+")
CN2N = {"两": 2, "三": 3, "四": 4, "五": 5}

HEAD = (
    "对应这个视频使用{N}张人物参考图，角色为原创虚构的成年人物，"
    "不对应任何现实人物，不参考任何真人肖像，不复制任何名人的脸部特征：{maps}。"
    "专业摄像头拍摄，视线高度接近人物眼睛，以中近景、近景、面部特写为主，"
    "两人对话采用快速正反打，全部使用直接硬切，正片画面不出现任何字幕，文字只出现在结尾。"
)

MAP_ROLES = ("男主A", "女主B", "人物C", "人物D", "人物E")

BODY = (
    "【画面内容】【场景：空间 + 谁在哪 + 桌上/手边有什么，物件写具体数量】。"
    "【A的动作+语气】：“【台词1，15–25字，把冲突挑起来】。”"
    "切B近景，【B的动作+表情】：“【台词2，反驳或嘴硬】。”"
    "【引爆：一个可见动作 / 道具入画 / 声音传出】，【在场者反应一句】。"
    "切【谁】近景，【他】：“【台词3，把谐音句{lang}喊出口】。”"
)

TEACH = (
    "切{who}一个人在一片纯白的背景中，带着喜剧荒诞的表情和语调面对镜头走来，"
    "{who}像是老师在给学生上课一样说：{hook}，{en}，{cn}。"
    "说到{en}时{who}把右手伸出举向上空。"
)

CARD = (
    "切A和B从一片空白背景中的右侧走入画面，A边走边【回扣前文道具或动作】对着B说到："
    "“【回扣台词】。”说完以后，A和B站在屏幕中间，A和B一起说：“{cn}，{hook}。”"
    "随后硬切整个屏幕纯白背景，画面上方显示中文“{cn}”，正中显示英文“{en}”，"
    "下方显示中文“{hook}”，人物面部、发型与服装保持一致，避免肢体变形与多余物体。"
    "画外旁白用标准的播音讲解音，标准伦敦腔，把英文和中文各朗读一遍。"
)


def parse_triple(raw):
    """把各种分隔符写法的三元组切成 (单词, 翻译, 谐音)。"""
    parts = [p for p in SEP.split(raw.strip()) if p and p.strip()]
    if len(parts) < 3:
        raise ValueError(
            f"要三段（单词/翻译/谐音），只认到 {len(parts)} 段：{parts}\n"
            "例：dangerous | 危险的 | 单脚窝屎"
        )
    en, cn, hook = (p.strip() for p in parts[:3])
    if not re.fullmatch(r"[A-Za-z][A-Za-z\-' ]*", en):
        raise ValueError(f"第一段应该是英文单词，收到：{en!r}")
    return en, cn, hook


def build(en, cn, hook, mode="teach", refs=3, who="A"):
    maps = "，".join(f"参考图{'一二三四五'[i]}对应{MAP_ROLES[i]}" for i in range(refs))
    body = BODY.format(lang="「" + hook + "」")
    ending = (TEACH if mode == "teach" else CARD).format(who=who, en=en, cn=cn, hook=hook)
    return HEAD.format(N=refs, maps=maps) + body + ending


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("triple", help="单词 | 翻译 | 谐音")
    ap.add_argument("--mode", choices=("teach", "card"), default="teach")
    ap.add_argument("--refs", type=int, default=3, choices=(2, 3, 4, 5))
    ap.add_argument("--who", default="A", choices=("A", "B", "C"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    try:
        en, cn, hook = parse_triple(a.triple)
    except ValueError as e:
        print(e, file=sys.stderr)
        sys.exit(2)

    text = build(en, cn, hook, a.mode, a.refs, a.who)
    if a.out:
        import io
        io.open(a.out, "w", encoding="utf-8", newline="\n").write(text + "\n")
        print(f"已写入 {a.out}")
        print("把【】全部换成具体内容，再跑：python check_script.py " + a.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
