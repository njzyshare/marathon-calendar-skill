#!/usr/bin/env python3
"""
马拉松赛历采集工具 v3
=====================
主数据源：nowrun.cn（闹跑）- 从首页提取全部492场赛事的名称和详情ID
         选择性抓取近期赛事的详情页
替补数据源：gorunma.cn（去跑马）- 提供日期/地点/级别补充
备用数据源：mls.chinaath.com（田协）- 权威校验

输出：JSON + 交互式HTML
"""

import re
import json
import time
import os
import sys
from datetime import datetime
from typing import Optional

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
NOWRUN_BASE = "https://nowrun.cn"
REQUEST_DELAY = 1.0  # 详情页间隔

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def safe_get(url: str, max_retries=2) -> Optional[str]:
    import requests as req
    for attempt in range(1, max_retries + 1):
        try:
            time.sleep(REQUEST_DELAY)
            r = req.get(url, headers=HEADERS, timeout=25)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r.text
        except Exception as e:
            log(f"  ⚠ {e} (attempt {attempt})")
        if attempt < max_retries:
            time.sleep(2)
    return None


def extract_text(html: str) -> str:
    """从 HTML 提取纯文本"""
    text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '\n', text)
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


# ══════════════════════════════════════════════════════
# 闹跑 - 列表解析（从首页提取全部492场赛事）
# ══════════════════════════════════════════════════════

def scrape_nowrun_list() -> list[dict]:
    """从闹跑首页提取全部赛事列表（名称 + 时间/地点/等级 + ID）"""
    log("📄 获取闹跑首页...")
    html = safe_get(NOWRUN_BASE + "/")
    if not html:
        log("  ⚠ 获取失败")
        return []

    # 1. 提取所有 href="/race/XXX" 中的 ID 和对应的赛事名称
    # 先找到赛事列表区域的 a 标签
    # 格式: <a href="/race/77">2026东极佳木斯抚远新年马拉松</a>
    race_links = re.findall(r'href="(/race/(\d+))">([^<]+)</a>', html)
    log(f"  ✅ 找到 {len(race_links)} 个赛事链接")

    # 建立 ID->名称 映射，同时保留序号顺序
    id_to_name = {}
    name_to_id = {}
    id_order = []
    for href, rid, name in race_links:
        name = name.strip()
        id_to_name[rid] = name
        name_to_id[name] = rid
        if rid not in id_order:
            id_order.append(rid)

    # 2. 提取有详细信息的卡片区域（### 后面的结构化数据）
    text = extract_text(html)

    # 将文本按 ### 分割
    sections = re.split(r'\n(?=###\s)', text)

    card_races = {}
    for sec in sections:
        sec = sec.strip()
        if not sec or not sec.startswith('###'):
            continue
        name_m = re.search(r'###\s+(.+?)(?:\n|$)', sec)
        if not name_m:
            continue
        name = name_m.group(1).strip()

        race = {'name': name, 'source': 'nowrun'}

        # 日期时间地点行
        dl = re.search(
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})\s+(\d{1,2}:\d{2})\s*[|｜]\s*(.+?)(?:\n|$)',
            sec
        )
        if dl:
            race['date'] = f"{dl.group(1)}-{int(dl.group(2)):02d}-{int(dl.group(3)):02d}"
            race['start_time'] = dl.group(4)
            race['location'] = dl.group(5).strip()

        # 认证等级
        lm = re.search(r'\b(A类|B类|C类)\b', sec)
        if lm:
            race['level'] = lm.group(1)

        # 报名状态
        if re.search(r'\d+天后截止|明日', sec):
            race['registration_status'] = '报名中'
        elif '额满即止' in sec:
            race['registration_status'] = '额满即止'
        elif '已结束' in sec:
            race['registration_status'] = '已结束'

        card_races[name] = race

    # 3. 把这两部分合并
    # ID 列表中的每个赛事，如果能匹配到卡片数据就合并
    all_races = []
    for rid in id_order:
        name = id_to_name[rid]
        race = {'race_id': rid, 'name': name,
                'detail_url': f"https://www.nowrun.cn/race/{rid}",
                'source': 'nowrun',
                'name_from_list': True}  # 标记来源

        # 如果有卡片数据，合并
        if name in card_races:
            card = card_races[name]
            race.update(card)
            race['name_from_list'] = False
            race['has_detail_card'] = True

        all_races.append(race)

    log(f"  📊 共 {len(all_races)} 场赛事，其中 {sum(1 for r in all_races if r.get('has_detail_card'))} 场有详细卡片")
    return all_races


# ══════════════════════════════════════════════════════
# 闹跑 - 详情页解析
# ══════════════════════════════════════════════════════

def parse_nowrun_detail(html: str) -> dict:
    text = extract_text(html)
    info = {}

    # 日期 & 地点
    dm = re.search(r'📅\s*(\d{1,2})月(\d{1,2})日\s*(?:周\S+)?\s*(\d{1,2}:\d{2})?\s*·\s*📍\s*(.+?)(?:\s*·|\n)', text)
    if dm:
        info['date'] = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
        if dm.group(3):
            info['start_time'] = dm.group(3)
        info['location'] = dm.group(4).strip()

    # 报名时间线
    for label, key in [('报名开始', 'registration_start'), ('报名截止', 'registration_end'),
                       ('出签结果', 'lottery_date'), ('比赛日', 'race_date')]:
        m = re.search(rf'{re.escape(label)}\s*\n\s*(\d{{4}})\.(\d{{1,2}})\.(\d{{1,2}})\s*(\d{{1,2}}:\d{{2}})?', text)
        if m:
            ds = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            t = m.group(4) or ''
            info[key] = f"{ds} {t}".strip()

    # 认证等级
    lm = re.search(r'(A类|B类|C类)\s*(?:认证)?', text)
    if lm:
        info['level'] = lm.group(1)

    # 状态
    sm = re.search(r'(已结束|待比赛|报名中|即将开始|已取消)', text)
    if sm:
        info['status'] = sm.group(1)

    # 赛事设项
    es = re.search(r'赛事设项\s*\n([\s\S]*?)(?=\n###|\n##|\Z)', text)
    if es:
        events = []
        for m2 in re.finditer(
            r'(全程|半程|10公里|5公里|迷你跑|越野|接力)\s*[：:．.]?\s*'
            r'([\d.]+)?\s*(?:万人?|人)?\s*(?:[¥￥]?\s*(\d+(?:\.\d+)?)\s*元?)?',
            es.group(1)
        ):
            evt = {'type': m2.group(1), 'quota': None, 'fee': None}
            qs = (m2.group(2) or '').replace(',', '')
            if '万' in (m2.group(2) or ''):
                try:
                    evt['quota'] = int(float(qs) * 10000)
                except ValueError:
                    pass
            elif qs.replace('.', '').isdigit():
                evt['quota'] = int(float(qs))
            if m2.group(3):
                try:
                    evt['fee'] = int(float(m2.group(3)))
                except ValueError:
                    pass
            events.append(evt)
        if events:
            info['events'] = events

    # 起终点
    sm2 = re.search(r'起点\s*\n\s*(.+?)(?:\n|\[)', text)
    if sm2:
        info['start_point'] = sm2.group(1).strip()
    em = re.search(r'终点\s*(?:-\s*)?\s*\n\s*(.+?)(?:\n|\[)', text)
    if em:
        info['end_point'] = em.group(1).strip()

    # 爬升 & 海拔
    cm = re.search(r'累计爬升\s*约?\s*(\d+)\s*米', text)
    if cm:
        info['elevation_gain'] = int(cm.group(1))
    am = re.search(r'平均海拔\s*约?\s*(\d+)\s*米', text)
    if am:
        info['avg_altitude'] = int(am.group(1))

    # 官方公众号
    wm = re.search(r'官方公众号\s*(.+?)(?:\n|$)', text)
    if wm:
        info['wechat_account'] = wm.group(1).strip()

    return info


def fetch_nowrun_details(races: list[dict], max_detail: int = 80):
    """批量获取赛事详情，优先近期/报名中的"""
    # 按ID倒序（最近的赛事ID大）
    with_detail = [r for r in races if r.get('race_id')]
    # 优先没有卡片信息+ID靠后（近期）
    to_fetch = sorted(with_detail,
                      key=lambda r: (0 if r.get('has_detail_card') else 1,
                                     -int(r.get('race_id', 0))))
    to_fetch = to_fetch[:max_detail]

    log(f"\n⏳ 获取详情（{len(to_fetch)} 场）...")
    for i, race in enumerate(to_fetch):
        url = race.get('detail_url')
        if not url:
            continue
        log(f"  [{i+1}/{len(to_fetch)}] ID={race['race_id']} {race['name'][:30]}...")
        html = safe_get(url)
        if html:
            race['detail'] = parse_nowrun_detail(html)


# ══════════════════════════════════════════════════════
# 替补：gorunma.cn
# ══════════════════════════════════════════════════════

def scrape_gorunma() -> list[dict]:
    log("📄 替补：去跑马 (gorunma.cn)")
    html = safe_get("https://www.gorunma.cn/")
    if not html:
        log("  ⚠ 获取失败")
        return []
    text = extract_text(html)
    races = []

    for section in re.split(r'\n(?=##\s+\d+月\d+日)', text):
        dm = re.search(r'##\s+(\d{1,2})月(\d{1,2})日', section)
        if not dm:
            continue
        race_date = f"2026-{int(dm.group(1)):02d}-{int(dm.group(2)):02d}"
        for card in re.finditer(
            r'(A类认证|B类认证|C类认证|A\s*级|B\s*级|C\s*级)\s*\n'
            r'###\s+(.+?)\s*\n'
            r'(\S+?)(?:\d{1,2})月(?:\d{1,2})日\s*\n'
            r'([\s\S]*?)(?=\nA类|\nB类|\nC类|\Z)',
            section
        ):
            level_raw, name, province, proj_raw = card.groups()
            level = 'A类' if 'A' in level_raw else ('B类' if 'B' in level_raw else 'C类')
            projects = [p for p in ['全程','半程','10公里','5公里'] if p in proj_raw]
            races.append({'name': name.strip(), 'date': race_date,
                         'province': province.strip(), 'level': level,
                         'projects': projects, 'source': 'gorunma'})

    pend = re.search(r'日期待定[\s\S]*?(?=\n##|\Z)', text)
    if pend:
        for card in re.finditer(
            r'(A\s*级|B\s*级|C\s*级)\s*\n###\s+(.+?)\s*\n(\S+?)\d{1,2}月\s*\n',
            pend.group(0)
        ):
            level_raw, name, province = card.groups()
            level = 'A类' if 'A' in level_raw else ('B类' if 'B' in level_raw else 'C类')
            races.append({'name': name.strip(), 'date': None, 'date_status': '待定',
                         'province': province.strip(), 'level': level,
                         'projects': [], 'source': 'gorunma'})

    log(f"  ✅ {len(races)} 场")
    return races


# ══════════════════════════════════════════════════════
# 备用：田协/MLS
# ══════════════════════════════════════════════════════

def scrape_runchina() -> list[dict]:
    log("📄 备用：田协 (mls.chinaath.com)")
    html = safe_get("https://mls.chinaath.com/")
    if not html:
        log("  ⚠ 获取失败")
        return []
    text = extract_text(html)
    found = re.findall(r'(\d{4}\.\d{1,2}\.\d{1,2})\s+(.+?)(?:\s|$)', text)
    if found:
        results = [{'name': r[1].strip(), 'date': r[0], 'source': 'runchina_html'} for r in found if '马拉松' in r[1]]
        log(f"  ✅ {len(results)} 条")
        return results
    log("  ⚠ 无数据")
    return []


# ══════════════════════════════════════════════════════
# 整合
# ══════════════════════════════════════════════════════

def merge_sources(main: list, *backups: list[list]) -> list:
    def norm(name):
        return re.sub(r'[\s·•\-—\'"＂（）()【】\[\]《》<>、，,。.：:]', '', name).lower()
    idx = {}
    for r in main:
        k = norm(r.get('name', ''))
        if k:
            idx[k] = r
    for bk_list in backups:
        for br in bk_list:
            bk = norm(br.get('name', ''))
            mr = idx.get(bk)
            if not mr:
                for mk, mv in idx.items():
                    if bk and mk and (bk in mk or mk in bk):
                        mr = mv
                        break
            if mr:
                for f in ['level', 'location', 'date']:
                    if not mr.get(f) and br.get(f):
                        mr[f] = br[f]
                        mr[f'{f}_from'] = br.get('source', 'backup')
            else:
                extra = dict(br)
                extra['extra_source'] = 'backup_only'
                main.append(extra)
                log(f"  ℹ 替补新增：{br.get('name', '?')}")
    return main


# ══════════════════════════════════════════════════════
# 导出
# ══════════════════════════════════════════════════════

def export_json(races: list, path: str):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(races, f, ensure_ascii=False, indent=2)
    log(f"  ✅ JSON: {path}")


def export_html(races: list, path: str):
    now = datetime.now()

    def sort_key(r):
        d = (r.get('detail') or {}).get('date') or r.get('date')
        return (0, d) if d else (1, r.get('name', ''))

    sorted_races = sorted(races, key=sort_key)

    def fmt_evt(e):
        parts = [e["type"]]
        if e.get("quota"):
            parts.append(f" {e['quota']}人")
        if e.get("fee"):
            parts.append(f" ¥{e['fee']}")
        return f'<span class="evt">{"".join(parts)}</span>'

    cards = []
    for r in sorted_races:
        d = r.get('detail', {})
        name = r.get('name', '')
        rdate = d.get('date') or r.get('date') or '待定'
        loc = d.get('location') or r.get('location') or ''
        lv = d.get('level') or r.get('level') or ''
        st = d.get('status') or r.get('registration_status') or r.get('date_status') or ''
        stim = d.get('start_time') or ''
        sp = d.get('start_point', '')
        ep = d.get('end_point', '')
        climb = d.get('elevation_gain')
        alt = d.get('avg_altitude')
        rs = d.get('registration_start', '')
        re_ = d.get('registration_end', '')
        lot = d.get('lottery_date', '')
        events = d.get('events', [])
        wx = d.get('wechat_account', '')

        et = ''.join(fmt_evt(e) for e in events)
        src_tag = '<span class="tag bk">替补</span>' if r.get('extra_source') else ''
        lv_cls = {'A类': 'a', 'B类': 'b', 'C类': 'c'}.get(lv, '')
        lv_tag = f'<span class="lv {lv_cls}">{lv}</span>' if lv else ''
        st_cls = {'已结束': 'end', '已取消': 'cancel', '待比赛': 'pend',
                  '待定': 'pend', '报名中': 'open'}.get(st, '')
        st_tag = f'<span class="st {st_cls}">{st}</span>' if st else ''
        cl_h = f'<div class="ir"><span class="l">累计爬升</span><span>{climb}m</span></div>' if climb else ''
        al_h = f'<div class="ir"><span class="l">平均海拔</span><span>{alt}m</span></div>' if alt else ''
        reg_h = ''
        if rs or re_:
            reg_h += f'<div class="ir"><span class="l">报名</span><span>{"开始 " + rs if rs else ""} {"截止 " + re_ if re_ else ""}</span></div>'
        if lot:
            reg_h += f'<div class="ir"><span class="l">出签</span><span>{lot}</span></div>'

        cards.append(f'''
<div class="card" onclick="this.classList.toggle('x')">
  <div class="ch">
    <div class="ct"><h3>{name}{src_tag}</h3></div>
    <div class="cm"><span class="md">📅 {rdate}{f" {stim}" if stim else ""}</span><span class="ml">📍 {loc}</span>{lv_tag}{st_tag}</div>
  </div>
  <div class="cb">
    <div class="ig">{f'<div class="ir"><span class="l">起点</span><span>{sp}</span></div>' if sp else ''}{f'<div class="ir"><span class="l">终点</span><span>{ep}</span></div>' if ep else ''}{cl_h}{al_h}{reg_h}</div>
    {f'<div class="ev">{et}</div>' if et else ''}
    {f'<div class="wx">📱 {wx}</div>' if wx else ''}
    <div class="dn">▼ 收起</div>
  </div>
  <div class="ch-hint">▼ 点击展开详情</div>
</div>''')

    total = len(sorted_races)
    a_cnt = sum(1 for r in sorted_races
                if r.get('level') == 'A类' or (r.get('detail') or {}).get('level') == 'A类')
    has_date = sum(1 for r in sorted_races
                   if (r.get('detail') or {}).get('date') or r.get('date'))

    html_out = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>2026 中国马拉松赛历</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans SC",sans-serif;background:#f0f2f5;color:#1a1a2e}}
.hd{{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:36px 20px;text-align:center}}
.hd h1{{font-size:26px;margin-bottom:4px}}
.hd p{{color:#a0aec0;font-size:13px}}
.hd .st{{margin-top:14px;display:flex;justify-content:center;gap:28px;flex-wrap:wrap}}
.hd .si{{text-align:center}}
.hd .sn{{font-size:26px;font-weight:700;color:#ecc94b}}
.hd .sl{{font-size:12px;color:#a0aec0}}
.ct{{max-width:820px;margin:0 auto;padding:16px}}
.fb{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;padding:10px 14px;background:#fff;border-radius:10px;box-shadow:0 1px 3px rgba(0,0,0,.06);align-items:center}}
.fb input,.fb select{{padding:6px 10px;border:1px solid #d1d5db;border-radius:6px;font-size:13px;outline:0;background:#fff}}
.fb input:focus,.fb select:focus{{border-color:#6366f1}}
.card{{background:#fff;border-radius:10px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.06);overflow:hidden;cursor:pointer;transition:box-shadow .15s}}
.card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.1)}}
.ch{{padding:14px 16px}}
.ct h3{{font-size:16px;font-weight:600;display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.cm{{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;align-items:center;font-size:13px;color:#6b7280}}
.tag,.lv,.st{{display:inline-block;font-size:11px;padding:1px 7px;border-radius:4px;font-weight:500}}
.tag.bk{{background:#fef3c7;color:#92400e}}
.lv.a{{background:#dbeafe;color:#1e40af}}
.lv.b{{background:#e0e7ff;color:#3730a3}}
.lv.c{{background:#f3e8ff;color:#6b21a8}}
.st{{background:#f3f4f6;color:#4b5563}}
.st.open{{background:#d1fae5;color:#065f46}}
.st.end{{background:#e5e7eb;color:#6b7280}}
.st.cancel{{background:#fee2e2;color:#991b1b}}
.st.pend{{background:#fef3c7;color:#92400e}}
.cb{{padding:0 16px 14px;display:none}}
.card.x .cb{{display:block}}
.card.x .ch-hint{{display:none}}
.ch-hint{{padding:2px 16px 10px;font-size:12px;color:#9ca3af}}
.ig{{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;margin-bottom:8px}}
.ir{{font-size:13px;display:flex;gap:4px}}
.ir .l{{color:#6b7280;min-width:60px;flex-shrink:0}}
.ev{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
.evt{{display:inline-block;font-size:12px;background:#f3f4f6;padding:2px 8px;border-radius:4px;color:#374151}}
.wx{{font-size:12px;color:#6b7280;margin-top:6px}}
.dn{{font-size:11px;color:#9ca3af;text-align:right;margin-top:8px}}
.emp{{text-align:center;padding:40px 16px;color:#9ca3af;font-size:14px}}
</style>
</head>
<body>
<div class="hd">
  <h1>🏃 2026 中国马拉松赛历</h1>
  <p>主数据: nowrun.cn（492场）| 替补: gorunma.cn | 备用: mls.chinaath.com</p>
  <p style="color:#6b7280;font-size:12px;margin-top:4px">数据自动采集，请以官方公告为准。点击卡片展开详情。</p>
  <div class="st">
    <div class="si"><div class="sn">{total}</div><div class="sl">总赛事</div></div>
    <div class="si"><div class="sn">{has_date}</div><div class="sl">已定档</div></div>
    <div class="si"><div class="sn">{a_cnt}</div><div class="sl">A类</div></div>
    <div class="si"><div class="sn">{now.strftime("%Y-%m-%d")}</div><div class="sl">更新</div></div>
  </div>
</div>
<div class="ct">
  <div class="fb">
    <input type="text" id="q" placeholder="搜索赛事名称/城市..." oninput="f()" style="flex:1;min-width:150px">
    <select id="fl" onchange="f()"><option value="">全部级别</option><option value="A类">A类</option><option value="B类">B类</option><option value="C类">C类</option></select>
    <select id="fs" onchange="f()"><option value="">全部状态</option><option value="报名中">报名中</option><option value="待比赛">待比赛</option><option value="已结束">已结束</option><option value="已取消">已取消</option></select>
  </div>
  <div id="cs">{"".join(cards)}</div>
  <div id="em" class="emp" style="display:none">🔎 没有匹配的赛事</div>
</div>
<script>
function f(){{
  var q=document.getElementById('q').value.trim().toLowerCase();
  var l=document.getElementById('fl').value;
  var s=document.getElementById('fs').value;
  var cs=document.querySelectorAll('.card');
  var ok=false;
  cs.forEach(function(c){{
    var t=c.textContent.toLowerCase();
    var m=true;
    if(q&&!t.includes(q))m=false;
    if(m&&l&&!t.includes(l))m=false;
    if(m&&s&&!t.includes(s))m=false;
    c.style.display=m?'':'none';
    if(m)ok=true;
  }});
  document.getElementById('em').style.display=ok?'none':'block';
}}
</script>
</body>
</html>'''

    with open(path, 'w', encoding='utf-8') as f:
        f.write(html_out)
    log(f"  ✅ HTML: {path}")


# ══════════════════════════════════════════════════════
# main
# ══════════════════════════════════════════════════════

def main():
    log("=" * 50)
    log("  2026 马拉松赛历采集工具 v3")
    log("=" * 50)

    # 1. 闹跑列表（全部492场）
    log("\n阶段一：主数据源 - nowrun.cn（闹跑）")
    main_races = scrape_nowrun_list()
    if not main_races:
        log("  ❌ 闹跑列表为空")
        return

    # 2. 闹跑详情（近期&报名中赛事）
    fetch_nowrun_details(main_races, max_detail=60)

    # 3. 替补
    log("\n阶段二：替补 - gorunma.cn（去跑马）")
    bk1 = scrape_gorunma()

    # 4. 备用
    log("\n阶段三：备用 - mls.chinaath.com（田协）")
    bk2 = scrape_runchina()

    # 5. 整合
    log("\n阶段四：整合")
    merged = merge_sources(main_races, bk1, bk2)

    # 6. 导出
    log("\n阶段五：导出")
    jp = os.path.join(OUTPUT_DIR, "marathon_calendar_2026.json")
    hp = os.path.join(OUTPUT_DIR, "marathon_calendar_2026.html")
    export_json(merged, jp)
    export_html(merged, hp)

    log("\n" + "=" * 50)
    log(f"  完成！总赛事: {len(merged)}")
    log("=" * 50)


if __name__ == "__main__":
    main()
