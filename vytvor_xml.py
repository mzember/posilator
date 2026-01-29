#!/usr/bin/env python3
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
import xml.etree.ElementTree as ET

from faktury_stahovator import (
    oauth_token_client_credentials,
    get_account_slug,
    fetch_invoices,
    month_range,
    parse_ym,
    dec_round_int,
)


def die(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def env_required(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        die(f"Missing env var: {name}")
    return v


def month_list(target0: date, months_back: int):
    months = []
    y, m = target0.year, target0.month
    for _ in range(months_back + 1):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return months


def parse_args():
    month_arg = None
    months_back = 0
    period_field = "taxable_fulfillment_due"
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

    return month_arg, months_back, period_field, exclude_country


def parse_date_field(inv: dict, period_field: str):
    dstr = inv.get(period_field) or inv.get("issued_on")
    if not dstr:
        return None
    try:
        return datetime.strptime(dstr, "%Y-%m-%d").date()
    except ValueError:
        try:
            return datetime.fromisoformat(dstr.replace("Z", "+00:00")).date()
        except Exception:
            return None


def collect_month_data(invoices, months, period_field, exclude_country):
    wanted = {(d.year, d.month) for d in months}
    data = {}
    for d in months:
        key = (d.year, d.month)
        data[key] = {
            "total": Decimal("0"),
            "count": 0,
            "vat_country_set": set(),
            "details": [],
        }

    for inv in invoices:
        if inv.get("document_type") != "invoice":
            continue
        if inv.get("cancelled_at"):
            continue

        cc = (inv.get("client_country") or "").upper()
        if exclude_country and cc == exclude_country:
            continue

        d = parse_date_field(inv, period_field)
        if not d:
            continue

        key = (d.year, d.month)
        if key not in wanted:
            continue

        ns = inv.get("native_subtotal")
        if ns is None:
            continue

        vat = (inv.get("client_vat_no") or "").strip().replace(" ", "").upper()
        country = (inv.get("client_country") or "").strip().upper()
        if vat or country:
            data[key]["vat_country_set"].add((country, vat))

        amount = Decimal(str(ns))
        data[key]["total"] += amount
        data[key]["count"] += 1
        data[key]["details"].append(
            {
                "number": inv.get("number"),
                "issued_on": inv.get("issued_on"),
                "taxable_fulfillment_due": inv.get("taxable_fulfillment_due"),
                "client_country": inv.get("client_country"),
                "client_vat_no": inv.get("client_vat_no"),
                "native_subtotal": str(ns),
            }
        )

    return data


def set_attr(elem, name, value):
    if elem is None:
        return
    if value is None or value == "":
        return
    elem.set(name, value)


def load_template(path: str):
    if not os.path.exists(path):
        die(f"Template not found: {path}")
    return ET.parse(path)


def write_tree(tree: ET.ElementTree, path: str):
    try:
        ET.indent(tree, space="  ")
    except Exception:
        pass
    tree.write(path, encoding="utf-8", xml_declaration=True)


def update_dp3(tree: ET.ElementTree, year: int, month: int, submit_date: str,
               pln_sluzby_int: int, c_ufo: str, c_pracufo: str):
    root = tree.getroot()
    dp3 = root.find("DPHDP3")
    if dp3 is None:
        die("DPHDP3 element not found in DP3 template")

    veta_d = dp3.find("VetaD")
    veta_p = dp3.find("VetaP")
    veta_2 = dp3.find("Veta2")

    set_attr(veta_d, "rok", str(year))
    set_attr(veta_d, "mesic", str(month))
    set_attr(veta_d, "d_poddp", submit_date)
    set_attr(veta_p, "c_ufo", c_ufo)
    set_attr(veta_p, "c_pracufo", c_pracufo)
    set_attr(veta_2, "pln_sluzby", f"{pln_sluzby_int}.0")


def update_sh(tree: ET.ElementTree, year: int, month: int, submit_date: str,
              pln_hodnota_int: int, pln_pocet: int,
              c_ufo: str, c_pracufo: str, country: str, vat: str):
    root = tree.getroot()
    sh = root.find("DPHSHV")
    if sh is None:
        die("DPHSHV element not found in SH template")

    veta_d = sh.find("VetaD")
    veta_p = sh.find("VetaP")
    veta_r = sh.find("VetaR")

    set_attr(veta_d, "rok", str(year))
    set_attr(veta_d, "mesic", str(month))
    set_attr(veta_d, "d_poddp", submit_date)
    set_attr(veta_p, "c_ufo", c_ufo)
    set_attr(veta_p, "c_pracufo", c_pracufo)

    if veta_r is None:
        die("VetaR element not found in SH template")

    set_attr(veta_r, "pln_hodnota", str(pln_hodnota_int))
    set_attr(veta_r, "pln_pocet", str(pln_pocet))

    if country:
        set_attr(veta_r, "k_stat", country)
    if vat:
        set_attr(veta_r, "c_vat", vat)


def main():
    client_id = env_required("FAKTUROID_CLIENT_ID")
    client_secret = env_required("FAKTUROID_CLIENT_SECRET")
    ua = env_required("FAKTUROID_UA")
    slug_env = os.environ.get("FAKTUROID_ACCOUNT_SLUG")

    c_ufo = os.environ.get("C_UFO")
    c_pracufo = os.environ.get("C_PRACUFO")
    name_prefix = env_required("XML_NAME_PREFIX")

    tmpl_dp3 = os.environ.get("XML_TEMPLATE_DP3", "templates/dphdp3.xml")
    tmpl_sh = os.environ.get("XML_TEMPLATE_SH", "templates/dphshv.xml")
    out_dir = os.environ.get("XML_OUT_DIR", "xml_vygenerovane")
    submit_date = os.environ.get(
        "DPH_SUBMIT_DATE") or date.today().strftime("%d.%m.%Y")

    month_arg, months_back, period_field, exclude_country = parse_args()
    today = date.today()
    target0 = parse_ym(month_arg) if month_arg else today.replace(day=1)
    if not month_arg:
        prev = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        print(
            f"[info] No --month provided, using current month: {target0.year}-{target0.month:02d}")
        print("[usage] Specify a month explicitly:")
        print("  ./vytvor_xml.sh --month YYYY-MM")
        print(
            f"[example] Previous month: ./vytvor_xml.sh --month {prev.year}-{prev.month:02d}")
        print()
    months = month_list(target0, months_back)

    oldest = months[-1]
    newest = months[0]
    start, _ = month_range(oldest)
    _, end = month_range(newest)
    since_dt = datetime.combine(start, datetime.min.time()) - timedelta(days=2)
    until_dt = datetime.combine(end, datetime.min.time()) + timedelta(days=2)

    token = oauth_token_client_credentials(client_id, client_secret, ua)
    slug = slug_env or get_account_slug(token, ua)
    invs = fetch_invoices(token, ua, slug, since_dt, until_dt)

    data = collect_month_data(invs, months, period_field, exclude_country)

    os.makedirs(out_dir, exist_ok=True)
    written = []

    for d in months:
        key = (d.year, d.month)
        total = data[key]["total"]
        total_int = dec_round_int(total)
        count = data[key]["count"]
        vat_country_set = data[key]["vat_country_set"]

        if count > 0 and len(vat_country_set) != 1:
            if not vat_country_set:
                die(
                    "Missing VAT/country for "
                    f"{d.year}-{d.month:02d}. "
                    "Please fix invoice data or fill SH manually."
                )
            pairs = sorted(vat_country_set)
            die(
                "Found multiple VAT/country pairs for "
                f"{d.year}-{d.month:02d}: {pairs}. "
                "This is not implemented. Please report it in issues."
            )

        country = ""
        vat = ""
        if len(vat_country_set) == 1:
            country, vat = next(iter(vat_country_set))

        if total_int == 0:
            print(
                f"[info] {d.year}-{d.month:02d}: total=0, DP3/SH not needed; no XML generated."
            )
            continue

        dp3_tree = load_template(tmpl_dp3)
        sh_tree = load_template(tmpl_sh)

        update_dp3(
            dp3_tree,
            d.year,
            d.month,
            submit_date,
            total_int,
            c_ufo,
            c_pracufo)
        update_sh(
            sh_tree, d.year, d.month, submit_date, total_int, count,
            c_ufo, c_pracufo, country, vat
        )

        dp3_name = f"{name_prefix}-DP3-{d.year}-{d.month:02d}.xml"
        sh_name = f"{name_prefix}-SH-{d.year}-{d.month:02d}.xml"
        dp3_path = os.path.join(out_dir, dp3_name)
        sh_path = os.path.join(out_dir, sh_name)

        write_tree(dp3_tree, dp3_path)
        write_tree(sh_tree, sh_path)
        written.extend([dp3_path, sh_path])

    for p in written:
        print(f"[ok] wrote {p}")
    print()
    print("[next] If OK, move to xml_k_poslani and send:")
    print("  mv -i xml_vygenerovane/*.xml xml_k_poslani/ && ./odesli_xml_datovka.sh")


if __name__ == "__main__":
    main()
