#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端每日股票收盘推送脚本（配合 GitHub Actions 定时运行）。
抓腾讯行情 -> 调 Server 酱推送到微信。
配置通过环境变量传入：SENDKEY(密钥) / STOCK_MARKET / STOCK_CODE / STOCK_NAME
"""
import os
import re
import sys
import json
from datetime import datetime

try:
    import requests
except ImportError:
    sys.exit("❌ 未安装 requests，请先执行: pip install requests")

# 腾讯接口字段索引（与 ~ 分割顺序对应）
F = {
    "name": 1, "code": 2, "price": 3, "prev_close": 4, "open": 5,
    "high": 33, "low": 34, "change": 31, "pct": 32, "time": 30,
}


def parse_time(t):
    m = re.match(r"^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$", t or "")
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]))
    m = re.match(r"^(\d{4})[/-](\d{2})[/-](\d{2}) (\d{2}):(\d{2}):(\d{2})$", t or "")
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]))
    return None


def fetch_quote(market, code):
    """抓取腾讯行情，返回标准 dict。"""
    symbol = market + code  # 腾讯接口区分大小写，保持原样（如 usBABA）
    url = "https://qt.gtimg.cn/q=" + symbol
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.encoding = "gbk"
    m = re.search(r'="(.*)";', r.text)
    if not m:
        raise RuntimeError("行情返回为空，请检查代码/市场：" + symbol)
    parts = m.group(1).split("~")
    if len(parts) < 35 or not parts[1]:
        raise RuntimeError("行情字段异常，请检查代码/市场：" + symbol)
    g = lambda k: parts[F[k]]
    dt = parse_time(g("time"))
    price = float(g("price"))
    chg = float(g("change")) if g("change") else 0.0
    pct = float(g("pct")) if g("pct") else 0.0
    return {
        "name": g("name"),
        "code": g("code") or code,
        "price": price,
        "change": chg,
        "pct": pct,
        "high": float(g("high")) if g("high") else 0.0,
        "low": float(g("low")) if g("low") else 0.0,
        "date": dt.strftime("%Y-%m-%d") if dt else "",
        "time": dt.strftime("%H:%M:%S") if dt else "",
    }


def push_serverchan(sendkey, title, content):
    url = "https://sctapi.ftqq.com/" + sendkey + ".send"
    resp = requests.post(url, data={"title": title, "desp": content}, timeout=15)
    return resp.json()


def main():
    sendkey = os.environ.get("SENDKEY")
    if not sendkey:
        sys.exit("❌ 未设置环境变量 SENDKEY（请在 GitHub 仓库 Settings -> Secrets 中配置）")
    market = os.environ.get("STOCK_MARKET", "sh")
    code = os.environ.get("STOCK_CODE", "600519")
    name = os.environ.get("STOCK_NAME", "")

    q = fetch_quote(market, code)
    if name:
        q["name"] = name

    sign = "+" if q["change"] >= 0 else ""
    content = "\n".join([
        "📈 股票价格播报（实时）",
        f"名称：{q['name']} ({q['code']})",
        f"时间：{q['date']} {q['time']}",
        f"当前价：¥{q['price']}",
        f"涨跌：{sign}{q['change']} ({sign}{q['pct']}%)",
        f"最高：¥{q['high']}　最低：¥{q['low']}",
    ])
    title = f"价格播报 {q['name']} {q['price']}"

    res = push_serverchan(sendkey, title, content)
    if res.get("code") != 0:
        sys.exit("❌ 推送失败：" + json.dumps(res, ensure_ascii=False))

    print("✅ 已推送：" + title)
    print(content)


if __name__ == "__main__":
    main()
