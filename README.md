# Automatizace podání DPH (DPHDP3) a Souhrnného hlášení (VIES/SH) dle faktur z Fakturoidu

**EN (short summary):** Two small scripts to speed up Czech VAT filings from Fakturoid: `send_dane_xml_sh_dp3.sh` bulk-sends existing XML via Datovka (data box), `faktury_stahovator.py` fetches monthly totals from Fakturoid API. A planned feature will auto-fill your XML templates.

---

## K čemu to je
Pokud fakturujete přes Fakturoid do zahraničí (EU), musíte se stát "identifikovanou osobou" a každý měsíc podávat:

- **Přiznání k DPH (DPHDP3)** a
- **Souhrnné hlášení (VIES/SH)**,

Tohle repo vám šetří čas a energii, zvlášť pokud máte odpor k administrativním úkonům.

Máte dvě cesty (s konkrétními skripty):

### 1) Máte vyšší tarif Fakturoidu (generuje hlášení ve formátu XML)
Fakturoid vám vygeneruje XML pro EPO. Vy je stáhnete do jednoho adresáře a tento projekt je pak umí **hromadně odeslat přes datovou schránku** (pomocí programu **Datovka**) → `send_dane_xml_sh_dp3.sh`

Výhoda: žádné ruční klikání v EPO pro každý měsíc, ideální pro „dohánění“ zpětných období.

### 2) Tarif nemáte
Skript `faktury_stahovator.py` si z Fakturoidu přes API stáhne podklady (částky) za měsíc(e) a připraví vám čísla, která patří do XML.

---

## Co je v repu
- **`send_dane_xml_sh_dp3.sh` (posílač XML / Datovka)**  
  Pošle najednou více XML souborů datovou schránkou a po úspěchu je roztřídí.
- **`faktury_stahovator.py` (stažení podkladů z Fakturoid API)**  
  Vytáhne faktury za zvolený měsíc (nebo i více měsíců zpětně), odfiltruje CZ, spočítá částky a vypíše hodnoty pro DPHDP3 + VIES.

---

## Plánovaná funkce (WIP)
Automatické **přepsání/naplnění XML** ze šablony:
- vezme data z Fakturoidu (`faktury_stahovator.py`),
- doplní do připravených XML šablon správné hodnoty a data,
- výsledná XML pak půjde rovnou poslat skriptem `send_dane_xml_sh_dp3.sh`.

---

## Požadavky
- Linux/macOS (funguje i na WSL)
- **Python 3.9+**
- Pro odesílání XML: nainstalovaný **Datovka** klient (CLI režim)

---

## Instalace
Naklonujte repo a nainstalujte (není potřeba nic extra):

```bash
git clone <repo>
cd <repo>
````

---

## Konfigurace Fakturoid API (`.env`)

Vytvořte `.env` (NEcommitujte):

```env
FAKTUROID_CLIENT_ID=xxxxxxxx
FAKTUROID_CLIENT_SECRET=yyyyyyyy
FAKTUROID_UA=DPH-Automation (email@example.com)
# volitelně:
# FAKTUROID_ACCOUNT_SLUG=moje-firma
```

Doporučeno:

```bash
chmod 600 .env
```

---

## Použití

### A) Hromadné odeslání existujících XML přes datovou schránku

1. Ve Fakturoidu stáhněte XML (DPHDP3 a VIES/SH) a dejte je do jednoho adresáře (default je `batch1/`).
2. Nastavte login pro Datovku do env proměnné:

```bash
export DATOVKA_LOGIN="username='...',password='...'"
```

3. Spusťte posílač:

```bash
./send_dane_xml_sh_dp3.sh
```

> Posílač po úspěchu soubory roztřídí do `sent/YYYY-MM/...`.

Pokud chcete vidět, co to bude posílat, program Datovka lze mít puštěné jako GUI a ve skriptu [send_dane_xml_sh_dp3.sh] odkomentovat/přepnout na možnost `--compose`. Pak to jen zobrazí, neodešle automaticky.
---

### B) Stažení podkladů z Fakturoidu (částky) pro vyplnění XML

```bash
source .env
python3 faktury_stahovator.py
```

Konkrétní měsíc:

```bash
python3 faktury_stahovator.py --month 2024-12
```

Více měsíců zpětně:

```bash
python3 faktury_stahovator.py --month 2024-12 --back 6
```

Výstup vám dá připravené hodnoty pro DPHDP3 a VIES/SH.

---

## Podání: EPO vs. datová schránka

* **EPO**: XML načtete ve webovém rozhraní a odešlete (víc klikání). Výhodou je automatická kontrola dat i možnost  oční kontroly.
* **Datová schránka (Datovka)**: XML pošlete rychleji, skriptem. Hromadně, ale přitom každý soubor zvlášť.


---

## Licence

MIT

::contentReference[oaicite:0]{index=0}
