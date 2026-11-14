#!/usr/bin/env python3
"""生成共享层简→繁转换表（OpenCC s2tw 字表 + 少量词组），写入 shared/ukcn-shared.js 的 HANT-TABLE 标记之间。
用法：pip install opencc-python-reimplemented；python design-system/gen-hant.py [--check]
改了页面文案后重跑一次；--check 只校验转换表与当前文案一致（覆盖页面里出现的全部可转换字）。"""
import re, sys, json, os
from opencc import OpenCC
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
FILES = ['prototype-x-style.html', 'prototype-collection-room.html', 'publish-content.html', 'shared/ukcn-shared.js']
cc = OpenCC('s2tw')
SKIP_CHARS = set('只台家')          # 只（只有）、台（平台）、家（家具）保持原字，靠词组处理例外
OVER = {'视频':'影片','举报':'檢舉','发布':'發佈','信息':'資訊','账号':'帳號','默认':'預設','网络':'網絡','审核':'審核',
        '一只':'一隻','多只':'多隻','台面':'檯面','面团':'麵糰','面粉':'麵粉'}
BAD = {'道里','天后','布会','布于','明复','家具','被发'}
def build(txt):
    chars = sorted(set(re.findall(r'[\u4e00-\u9fff]', txt)))
    cmap = {c: cc.convert(c) for c in chars if c not in SKIP_CHARS and cc.convert(c) != c and len(cc.convert(c)) == 1}
    conv = lambda s: ''.join(cmap.get(ch, ch) for ch in s)
    phr = {}
    for r in set(re.findall(r'[\u4e00-\u9fff]{2,}', txt)):
        for i in range(len(r) - 1):
            bg = r[i:i + 2]
            if bg in phr or bg in BAD: continue
            o = cc.convert(bg)
            if len(o) == 2 and o != conv(bg) and '覈' not in o: phr[bg] = o
    phr.update(OVER)
    return cmap, phr
def main():
    txt = ''.join(open(SRC + f, encoding='utf-8').read() for f in FILES)
    # 表本身不参与统计
    txt = re.sub(r'/\* HANT-TABLE:BEGIN \*/[\s\S]*?/\* HANT-TABLE:END \*/', '', txt)
    cmap, phr = build(txt)
    c = ''.join(k + v for k, v in sorted(cmap.items())); p = '|'.join(k + v for k, v in sorted(phr.items()))
    block = "/* HANT-TABLE:BEGIN */\n  var HANT_C = " + json.dumps(c, ensure_ascii=False) + ", HANT_P = " + json.dumps(p, ensure_ascii=False) + ";\n  /* HANT-TABLE:END */"
    path = SRC + 'shared/ukcn-shared.js'
    raw = open(path, encoding='utf-8', newline='').read()
    cur = re.search(r'/\* HANT-TABLE:BEGIN \*/[\s\S]*?/\* HANT-TABLE:END \*/', raw).group(0)
    if '--check' in sys.argv:
        ok = cur == block
        print(('PASS' if ok else 'FAIL') + f'  简繁转换表覆盖页面全部可转换字（{len(cmap)} 字 + {len(phr)} 词组）')
        sys.exit(0 if ok else 1)
    open(path, 'w', encoding='utf-8', newline='').write(raw.replace(cur, block))
    print(f'wrote {len(cmap)} chars + {len(phr)} phrases')
main()
