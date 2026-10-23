# -*- coding: utf-8 -*-
"""检查器自测。

原则：一个永远通过的检查器，比没有更糟。每加一条规则，必须构造一个反例，
证明它真的会报错。

用法：python selftest.py
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from check_script import check                       # noqa: E402
from corpus_stats import DEFAULT, analyse, load_scripts  # noqa: E402

DEMO = os.path.normpath(os.path.join(HERE, "..", "examples", "umbrella-俺不来了.md"))
TEACH = os.path.normpath(os.path.join(HERE, "..", "examples", "holiday-耗了一天.md"))
FAILED = []
N = 0


def expect(name, text, code, should_fire=True):
    global N
    N += 1
    res = check(text, name=name)
    codes = {i["code"] for i in res["issues"]}
    hit = code in codes
    ok = hit == should_fire
    print(f"[{'ok' if ok else 'BAD'}] {name}: {code} "
          f"{'应报' if should_fire else '不应报'} → {'报了' if hit else '没报'}")
    if not ok:
        FAILED.append(f"{name}/{code}")
        print("      实际:", sorted(codes))


def mut(base, old, new):
    assert old in base, f"替换失败，找不到：{old[:30]}"
    return base.replace(old, new, 1)


def main():
    demo = io.open(DEMO, encoding="utf-8-sig").read()

    # 0 基线
    res = check(demo, "demo")
    print(f"[{'ok' if res['pass'] else 'BAD'}] 基线：合格稿应为 PASS")
    if not res["pass"]:
        FAILED.append("demo-should-pass")
        for i in res["issues"]:
            print("      ", i)

    # ---------- Seedance 交付契约 ----------
    expect("时长泄漏", mut(demo, "A愣在原地，抹了一把", "A停顿两秒，抹了一把"), "DURATION")
    expect("时长泄漏-阿拉伯数字", mut(demo, "A愣在原地，", "A愣了3秒，"), "DURATION")
    expect("时间码", mut(demo, "A愣在原地，", "A愣在原地，00:03 抬头，"), "TIMECODE")
    expect("平台名", mut(demo, "画外旁白用标准", "Seedance 画外旁白用标准"), "PLATFORM")
    expect("分段", mut(demo, "【画面内容】", "\n\n【画面内容】"), "SINGLE_BLOCK")
    expect("结构标记", "1. " + demo, "NO_STRUCTURE")
    # 旧式无引号字卡：既该报 TEXT_QUOTE，也说明老写法为什么不能用
    legacy_card = demo.replace(
        "画面上方显示中文“雨伞”，正中显示英文“umbrella”，下方显示中文“俺不来了”",
        "显示：umbrella,umbrella下方写着中文俺不来了，umbrella上方写着中文雨伞")
    expect("字卡无引号", legacy_card, "TEXT_QUOTE")
    expect("字卡过长", mut(demo, "中文“雨伞”，正中", "中文“独自一个人待着的时候”，正中"), "TEXT_LONG")

    # ---------- 结构 ----------
    expect("白底换人", mut(demo, "切A和B从一片空白背景中的右侧走入画面，A边走边",
                           "切B和C从一片空白背景中的右侧走入画面，A边走边"), "WHITE_CAST")
    broken = mut(demo, "：“俺不来了。”", "：“马上。”")
    broken = mut(broken, "：“俺不来了，伞来了。”", "：“伞来了。”")
    expect("谐音未埋", broken, "HOOK_UNPLANTED")
    expect("软转场", mut(demo, "全部使用直接硬切", "全部使用淡入淡出"), "SOFT_CUT")

    # ---------- 参考图 / 人数 ----------
    expect("悬空角色", mut(demo, "B没接话，把窗户关上了",
                           "C在楼道探出头插了一句：“那我先走了啊。”B没接话，把窗户关上了"),
           "CAST_OVER")
    expect("声明与映射不符",
           mut(demo, "使用两张人物参考图", "使用两张人物参考图") .replace("参考图二为人物B。", "参考图二为人物B。参考图三为人物C。"),
           "REF_MISMATCH")

    # ---------- 合规头 ----------
    expect("字幕声明缺失",
           mut(demo, "正片画面不出现任何字幕，文字只出现在结尾的纯白字卡上", "画面干净"),
           "HEAD_NOSUB")
    expect("缺原创虚构", mut(demo, "角色为原创虚构的成年人物，", ""), "HEAD_FICTION")

    # ---------- 字卡 ----------
    expect("字卡缺本义", mut(demo, "画面上方显示中文“雨伞”，", ""), "CARD_MEANING")

    # ---------- 台词体检 ----------
    expect("单句过长", mut(demo, "：“俺不来了。”",
                           "：“我跟你说这雨下得这么大你还让我站在楼下等你你知不知道我今天穿的是新鞋新裤子刚买的你要是赔不起就别让我等。”"),
           "LINE_LONG")
    filler = ("你倒是快点下来啊我这都站了快二十分钟了腿都麻了你知不知道楼下风多大啊"
              "我这伞也没带手机快没电了你再磨蹭一会儿我就要冻感冒了明天还得上班呢")
    broken = demo
    for old in ("：“B！下来接我一下，我没带伞，这雨一时半会儿停不了！”",
                "：“俺不来了。”",
                "：“你不来我咋回去啊，我总不能在这儿站到天亮吧！”"):
        broken = mut(broken, old, f"：“{filler}”")
    expect("台词超量", broken, "CHAR_MANY")

    # ---------- 第二批语料带来的规则 ----------
    teach = io.open(TEACH, encoding="utf-8-sig").read()
    expect("场景图不计入张数", teach, "REF_MISMATCH", should_fire=False)

    pet = mut(teach, "使用三张人物参考图", "使用四张人物参考图")
    pet = mut(pet, "参考图三对应人物C；参考图四对应场景参考图",
              "参考图三对应人物C，参考图四对应宠物D")
    expect("宠物计入张数", pet, "REF_MISMATCH", should_fire=False)

    unquoted = re.sub(r"“([^”]*)”", r"\1", teach)
    expect("台词无引号", unquoted, "DIALOGUE_QUOTED")

    in_dialogue = mut(teach, "：“两万三千步，一个景点没进去。”",
                      "：“我排了两小时队，两万三千步，一个景点没进去。”")
    expect("台词里的时长放行", in_dialogue, "DURATION", should_fire=False)

    expect("授课式两个人出镜",
           mut(teach, "切A一个人在一片纯白的背景中",
               "切A和B一个人在一片纯白的背景中"), "TEACH_SOLO")

    # ---------- 三元组入口 ----------
    from make_skeleton import build, parse_triple
    for raw, want in [
        ("dangerous | 危险的 | 单脚窝屎", ("dangerous", "危险的", "单脚窝屎")),
        ("holiday，假日，耗了一天", ("holiday", "假日", "耗了一天")),
        ("gangster - 流氓 - 干死他", ("gangster", "流氓", "干死他")),
    ]:
        got = parse_triple(raw)
        ok = got == want
        print(f"[{'ok' if ok else 'BAD'}] 三元组解析：{raw} → {got}")
        if not ok:
            FAILED.append(f"parse:{raw}")
    try:
        parse_triple("dangerous | 危险的")
        ok = False
    except ValueError:
        ok = True
    print(f"[{'ok' if ok else 'BAD'}] 三元组缺格应报错")
    if not ok:
        FAILED.append("parse-missing")

    sk = build("dangerous", "危险的", "单脚窝屎", mode="teach")
    ok = ("像是老师在给学生上课" in sk and "单脚窝屎" in sk and "硬切" in sk
          and "【场景" in sk)
    print(f"[{'ok' if ok else 'BAD'}] 骨架生成（授课式）")
    if not ok:
        FAILED.append("skeleton-teach")
    ck = build("newbie", "新手", "牛哔", mode="card", refs=2)
    ok = ("上方显示中文“新手”" in ck and "牛哔" in ck and "一起说" in ck)
    print(f"[{'ok' if ok else 'BAD'}] 骨架生成（字卡式）")
    if not ok:
        FAILED.append("skeleton-card")

    # ---------- 语料信号：必须真的抓出问题 ----------
    rows = [(analyse(b)["en"], b) for b in load_scripts(DEFAULT)]
    rows = [(e, b) for e, b in rows if e]
    ref_bug = [e for e, b in rows
               if any(i["code"] == "REF_MISMATCH" for i in check(b, e)["issues"])]
    ok = len(ref_bug) >= 5
    print(f"[{'ok' if ok else 'BAD'}] 语料信号：{len(rows)} 条里有 {len(ref_bug)} 条"
          f"『声明张数与映射不符』→ {ref_bug}")
    if not ok:
        FAILED.append("corpus-signal")

    print()
    print(f"用例 {N} 个，失败 {len(FAILED)} 个。")
    if FAILED:
        print("自测未通过：", FAILED)
        sys.exit(1)
    print("自测全部通过。")


if __name__ == "__main__":
    main()
