# Automatizace podání DPH (DPHDP3) a Souhrnného hlášení (VIES/SH) dle faktur z Fakturoidu

**EN (short summary):** Generate DP3/SH XML from Fakturoid data and send them via Datovka. Main scripts: `vytvor_xml.sh` (fills templates) and `odesli_xml_datovka.sh` (bulk send).

---

## K čemu to je
Pokud fakturujete přes Fakturoid do zahraničí (EU), musíte se stát "identifikovanou osobou" a každý měsíc podávat:

- **Přiznání k DPH (DPHDP3)** a
- **Souhrnné hlášení (VIES/SH)**,

Tohle repo vám šetří čas a energii, zvlášť pokud máte odpor k administrativním úkonům.

Základní workflow je dvoukrokové:

1) **Vytvořit XML** (z šablon a Fakturoidu)  
   → `vytvor_xml.sh`
2) **Odeslat XML** přes Datovku  
   → `odesli_xml_datovka.sh`

Pokud máte vyšší tarif Fakturoidu a generujete XML přímo v Fakturoidu, můžete krok 1 přeskočit a XML jen zkopírovat do `xml_k_poslani/`.

---

## Co je v repu
- **`vytvor_xml.sh` (generátor XML)**  
  Vezme šablony v `templates/`, stáhne data z Fakturoidu a vyplní DP3 + SH do `xml_vygenerovane/`.
- **`odesli_xml_datovka.sh` (posílač XML / Datovka)**  
  Pošle najednou více XML souborů datovou schránkou a po úspěchu je roztřídí.
- **`faktury_stahovator.py` (stažení podkladů z Fakturoid API)**  
  Vytáhne faktury za zvolený měsíc (nebo i více měsíců zpětně), odfiltruje CZ, spočítá částky a vypíše hodnoty pro DPHDP3 + VIES.

---

## Struktura adresářů
- `templates/` – vzorové XML šablony (DP3/SH)
- `xml_vygenerovane/` – výstup z `vytvor_xml.sh`
- `xml_k_poslani/` – XML připravené k odeslání
- `odeslane/` – odeslané XML (roztříděno podle měsíců)
- `logs/` – logy z odesílání (`logs/send_dane.log`)

---

## Požadavky
- **Python 3.9+**
- Pro odesílání XML datovou schránkou: nainstalovaný program **Datovka**, zde je [návod, jak Datovku nainstalovat v Linuxu](https://web.archive.org/web/20250803062753/https://software.opensuse.org//download.html?project=home%3ACZ-NIC%3Adatovka-latest&package=datovka)

---

## Instalace
Naklonujte repo a nainstalujte (není potřeba nic extra):

```bash
git clone <repo>
cd <repo>
````

---

## Konfigurace (`.env`)

Vytvořte `.env` a upravte dle sebe:

```env
FAKTUROID_CLIENT_ID=xxxxxxxx
FAKTUROID_CLIENT_SECRET=yyyyyyyy
FAKTUROID_UA=posilator (email@example.com)
# volitelně:
# FAKTUROID_ACCOUNT_SLUG=moje-firma

# cisla uradu
C_UFO=461
C_PRACUFO=3001

# prefix jmena souboru
XML_NAME_PREFIX="firma"

# sablony a vystup
XML_TEMPLATE_DP3="templates/dphdp3.xml"
XML_TEMPLATE_SH="templates/dphshv.xml"
XML_OUT_DIR="xml_vygenerovane"

# volitelne: rucne nastavit datum podani (dd.mm.yyyy)
# DPH_SUBMIT_DATE="31.01.2026"
```

---

## Použití

### 1) Vytvořím XML (z Fakturoidu)

```bash
./vytvor_xml.sh
```

Konkrétní měsíc:

```bash
./vytvor_xml.sh --month 2024-12
```

Více měsíců zpětně:

```bash
./vytvor_xml.sh --month 2024-12 --back 6
```

Pokud je součet 0, skript nic negeneruje a jen vypíše, že DP3/SH není potřeba.

> Pokud máte XML přímo z Fakturoidu, stačí je uložit do `xml_k_poslani/` a tento krok přeskočit.

### 2) Pošlu XML přes Datovku

1. Zkopírujte XML do `xml_k_poslani/` (buď z `xml_vygenerovane/`, nebo z Fakturoidu).
2. Nastavte login pro Datovku do env proměnné:

```bash
export DATOVKA_LOGIN="username='...',password='...'"
```

3. Pokud podáváte jinému FÚ, než BRNO I, upravte ve skriptu ID datové schránky (příjemce).

4. Spusťte posílač:

```bash
./odesli_xml_datovka.sh
```

> Posílač po úspěchu soubory roztřídí do `odeslane/YYYY-MM/...`.

Pokud chcete pouze vidět, co to bude posílat, program Datovka lze mít puštěné jako GUI a ve skriptu `odesli_xml_datovka.sh` odkomentovat/přepnout na možnost `--compose`. Pak to jen zobrazí, neodešle automaticky.

---

## Podání: EPO vs. datová schránka

* **EPO**: XML načtete ve webovém rozhraní a odešlete (víc klikání). Výhodou je jejich automatická kontrola dat i vlastní manuální kontrola ještě před odesláním.
* **Datová schránka (Datovka)**: XML pošlete rychleji, skriptem. Hromadně, a přitom každý soubor zvlášť.


---

## Licence

MIT
