#!/usr/bin/env python3
import os
import sys
import json
import base64
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

API_BASE = "https://app.fakturoid.cz/api/v3"


def die(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def http_json(url: str, method="GET", headers=None, body_obj=None):
    headers = headers or {}
    data = None
    if body_obj is not None:
        data = json.dumps(body_obj).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")
    req = urllib.request.Request(
        url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))


def oauth_token_client_credentials(
        client_id: str, client_secret: str, user_agent: str) -> str:
    token_url = f"{API_BASE}/oauth/token"
    basic = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    headers = {
        "User-Agent": user_agent,
        "Authorization": f"Basic {basic}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {"grant_type": "client_credentials"}
    resp = http_json(token_url, method="POST", headers=headers, body_obj=body)
    if not resp or "access_token" not in resp:
        die(f"Token error: {resp}")
    return resp["access_token"]


def get_account_slug(access_token: str, user_agent: str) -> str:
    url = f"{API_BASE}/user.json"
    headers = {
        "User-Agent": user_agent,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"}
    u = http_json(url, headers=headers)
    # prefer default_account if set, otherwise first account
    if u.get("default_account"):
        return u["default_account"]
    accounts = u.get("accounts") or []
    if not accounts:
        die("No accounts found on /user.json")
    return accounts[0]["slug"]


def month_range(target: date):
    start = target.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1)
    else:
        end = start.replace(month=start.month + 1, day=1)
    return start, end


def iso_z(dt: datetime) -> str:
    # Use UTC-like 'Z' timestamps for API query params; add padding so we
    # don't miss border cases.
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_invoices(access_token: str, user_agent: str,
                   slug: str, since_dt: datetime, until_dt: datetime):
    invoices = []
    page = 1
    headers = {
        "User-Agent": user_agent,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"}
    while True:
        qs = urllib.parse.urlencode({
            "since": iso_z(since_dt),
            "until": iso_z(until_dt),
            "page": str(page),
            # invoices + corrections + tax docs (we'll filter)
            "document_type": "regular",
        })
        url = f"{API_BASE}/accounts/{slug}/invoices.json?{qs}"
        batch = http_json(url, headers=headers)
        if not batch:
            break
        invoices.extend(batch)
        if len(batch) < 40:
            break
        page += 1
    return invoices


def parse_ym(s: str) -> date:
    # "YYYY-MM"
    y, m = s.split("-")
    return date(int(y), int(m), 1)


def dec_round_int(x: Decimal) -> int:
    # DPH/SH se obvykle uvádí v Kč bez haléřů -> standardní zaokrouhlení
    return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def main():
    client_id = os.environ.get("FAKTUROID_CLIENT_ID")
    client_secret = os.environ.get("FAKTUROID_CLIENT_SECRET")
    ua = os.environ.get("FAKTUROID_UA")
    slug_env = os.environ.get("FAKTUROID_ACCOUNT_SLUG")

    if not client_id or not client_secret or not ua:
        die("Set env: FAKTUROID_CLIENT_ID, FAKTUROID_CLIENT_SECRET, FAKTUROID_UA")

    # args
    # default: current month
    month_arg = None
    months_back = 0
    period_field = "taxable_fulfillment_due"  # or issued_on
    exclude_country = "CZ"

    i = 1
    while i < len(sys.argv):
        a = sys.argv[i]
        if a in ("--month", "-m"):
            month_arg = sys.argv[i + 1]
            i += 2
        elif a in ("--back", "-b"):
            months_back = int(sys.argv[i + 1])
            i += 2
        elif a == "--field":
            period_field = sys.argv[i + 1]
            i += 2
        elif a == "--exclude-country":
            exclude_country = sys.argv[i + 1].upper()
            i += 2
        else:
            die(f"Unknown arg: {a}")
    today = date.today()
    target0 = parse_ym(month_arg) if month_arg else today.replace(day=1)

    # build list of months to report: target0 and N months back
    months = []
    y, m = target0.year, target0.month
    for k in range(months_back + 1):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1

    # fetch wide range once (from oldest month start to newest month end) +
    # padding
    oldest = months[-1]
    newest = months[0]
    start, _ = month_range(oldest)
    _, end = month_range(newest)
    # padding: 2 days before/after to be safe with created_at boundary
    since_dt = datetime.combine(start, datetime.min.time()) - timedelta(days=2)
    until_dt = datetime.combine(end, datetime.min.time()) + timedelta(days=2)

    token = oauth_token_client_credentials(client_id, client_secret, ua)
    slug = slug_env or get_account_slug(token, ua)

    invs = fetch_invoices(token, ua, slug, since_dt, until_dt)

    # group
    wanted = {(d.year, d.month) for d in months}
    sums = {(d.year, d.month): Decimal("0") for d in months}
    counts = {(d.year, d.month): 0 for d in months}
    details = {(d.year, d.month): [] for d in months}

    for inv in invs:
        # keep only real invoices (not proforma, not tax docs, not corrections)
        if inv.get("document_type") != "invoice":
            continue
        if inv.get("cancelled_at"):
            continue

        cc = (inv.get("client_country") or "").upper()
        if exclude_country and cc == exclude_country:
            continue

        # choose period date
        dstr = inv.get(period_field)
        if not dstr:
            # fallback to issued_on
            dstr = inv.get("issued_on")
        if not dstr:
            continue

        try:
            d = datetime.strptime(dstr, "%Y-%m-%d").date()
        except ValueError:
            # sometimes might be datetime, try that
            try:
                d = datetime.fromisoformat(dstr.replace("Z", "+00:00")).date()
            except Exception:
                continue

        key = (d.year, d.month)
        if key not in wanted:
            continue

        # native_subtotal is "without VAT" in native currency (CZK if account
        # is CZK) :contentReference[oaicite:8]{index=8}
        ns = inv.get("native_subtotal")
        if ns is None:
            continue

        amount = Decimal(str(ns))
        sums[key] += amount
        counts[key] += 1
        details[key].append({
            "number": inv.get("number"),
            "issued_on": inv.get("issued_on"),
            "taxable_fulfillment_due": inv.get("taxable_fulfillment_due"),
            "client_country": inv.get("client_country"),
            "client_vat_no": inv.get("client_vat_no"),
            "native_subtotal": str(ns),
        })

    # print
    for d in months:
        key = (d.year, d.month)
        total = sums[key]
        total_int = dec_round_int(total)
        ym = f"{d.year}-{d.month:02d}"
        print(
            f"{ym}  count={
                counts[key]}  sum_native_subtotal={total}  sum_CZK_rounded={total_int}")
        for it in details[key]:
            print(
                f"   - {
                    it['number']}  native_subtotal={
                    it['native_subtotal']}  country={
                    it['client_country']}  vat={
                    it['client_vat_no']}  issued={
                        it['issued_on']}  taxable={
                            it['taxable_fulfillment_due']}")
        # handy one-liner for your XML patching
        if counts[key] > 0:
            print(
                f"   -> use for XML: DP3(pln_sluzby)={total_int}  SH(pln_hodnota)={total_int}  pln_pocet={counts[key]}")
        else:
            print("   -> no EU invoices for this month (likely no SH/DP3 line to fill)")
        print()


if __name__ == "__main__":
    main()
