#!/usr/bin/env bash
set -euo pipefail

# ====== Nastavení ======
#RECIP_DBID="qdhny4c"                 # FÚ pro Jihomoravský kraj
RECIP_DBID="r4pn6hp"                 # FÚ BRNO I.
#RECIP_DBID="..."   # do vlastni schranky mi to nefunguje, jako fyzicke osobe
DIR="xml_k_poslani"                    # kde leží XML
SENT_DIR="./odeslane"                  # kam třídit po odeslání

: "${DATOVKA_LOGIN:?Set DATOVKA_LOGIN env var first (username='..',password='..')}"
command -v datovka >/dev/null || { echo "datovka binary not found"; exit 1; }

HELP="$(datovka --help 2>&1 || true)"

# Pro otevreni v GUI; akorat uz `datovka` musi bezet jako GUI zvlast.
#SEND_OPT="--compose"
# Naostro
SEND_OPT="--send-msg"
# GPT:
# Najdi správný send přepínač podle toho, co tvoje verze podporuje
#for cand in "--send-msg" "--send-message" "--sendmessage" "--send" ; do
  #if grep -qF "$cand" <<<"$HELP"; then
    #SEND_OPT="$cand"
    #break
  #fi
#done

if [[ -z "$SEND_OPT" ]]; then
  echo "Neumím najít send přepínač v 'datovka --help'."
  echo "Spusť: datovka --help | grep -i send -A30"
  exit 2
fi

# Klíč pro přílohu – většina verzí používá dmAttachment
ATT_KEY="dmAttachment"
if grep -qi "dmfile" <<<"$HELP"; then
  # některé buildy mohou používat jiné pojmenování – necháme jako fallback
  :
fi

echo "[i] Using send option: $SEND_OPT"

# ====== Funkce ======
parse_file() {
  # vstup: filename
  # výstup: TYPE YEAR MONTH
  local f="$1"
  if [[ "$f" =~ ^.+-DP3-([0-9]{4})-([0-9]{2})\.xml$ ]]; then
    echo "dphdp3 ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"
  elif [[ "$f" =~ ^.+-SH-([0-9]{4})-([0-9]{2})\.xml$ ]]; then
    echo "dphshv ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"
  elif [[ "$f" =~ ^.+-dphdp3-([0-9]{4})-([0-9]{1,2})m\.xml$ ]]; then
    echo "dphdp3 ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"
  elif [[ "$f" =~ ^.+-dphshv-([0-9]{4})-([0-9]{1,2})m\.xml$ ]]; then
    echo "dphshv ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"
  else
    return 1
  fi
}

annotation_for() {
  local type="$1" year="$2" month="$3"
  local mm
  printf -v mm "%02d" "$month"
  if [[ "$type" == "dphdp3" ]]; then
    echo "DPHDP3 ${year}-${mm}"
  else
    echo "VIES SH (DPHSHV) ${year}-${mm}"
  fi
}

target_dir_for() {
  local type="$1" year="$2" month="$3"
  local mm
  printf -v mm "%02d" "$month"
  echo "${SENT_DIR}/${year}-${mm}/${type}"
}

send_one() {
  local filepath="$(realpath $1)" type="$2" year="$3" month="$4"
  local ann
  ann="$(annotation_for "$type" "$year" "$month")"

  # Nejčastější formát: jeden parametr (kvazi-CSV) s klíči dbIDRecipient/dmAnnotation/dmAttachment
  local payload
  payload="dbIDRecipient='${RECIP_DBID}',dmAnnotation='${ann}',${ATT_KEY}='${filepath}',dmPublishOwnID='1'"

  echo "[>] Sending: $(basename "$filepath")  ->  ${RECIP_DBID}  (${ann})"

  # Zkus několik tvarů (pro kompatibilitu různých buildů)
  if datovka --login "$DATOVKA_LOGIN" "$SEND_OPT" "$payload" | tee -a logs/send_dane.log; then
    return 0
  fi

  # fallback 1: bez uvozovek kolem klíčů (některé verze)
  payload="dbIDRecipient=${RECIP_DBID},dmAnnotation=${ann},${ATT_KEY}=${filepath},dmPublishOwnID='1'"
  if datovka --login "$DATOVKA_LOGIN" "$SEND_OPT" "$payload" | tee -a logs/send_dane.log; then
    return 0
  fi

  # fallback 2: některé buildy chtějí parametr s prefixem (méně časté)
  if datovka --login "$DATOVKA_LOGIN" "$SEND_OPT" "dbIDRecipient='${RECIP_DBID}'" "dmAnnotation='${ann}'" "${ATT_KEY}='${filepath}'" | tee -a logs/send_dane.log; then
    return 0
  fi

  echo "[!] Failed to send: $filepath"
  echo "    Tip: spusť ručně s debugem:"
  echo "    datovka --login \"\$DATOVKA_LOGIN\" $SEND_OPT \"$payload\""
  return 1
}

# ====== Main ======
shopt -s nullglob

files=( "$DIR"/*.xml )
if (( ${#files[@]} == 0 )); then
  echo "Nenašel jsem žádné XML v $DIR (čekám *-DP3-YYYY-MM.xml / *-SH-YYYY-MM.xml)"
  exit 0
fi

# Seřadit chronologicky podle názvu (u tebe to funguje dobře)
IFS=$'\n' files_sorted=( $(printf "%s\n" "${files[@]##*/}" | sort) )
unset IFS

mkdir -p "$SENT_DIR"

for base in "${files_sorted[@]}"; do
  f="$DIR/$base"

  if ! out="$(parse_file "$base")"; then
    echo "[i] Skip (neodpovídá vzoru): $base"
    continue
  fi

  read -r type year month <<<"$out"

  # odeslat
  if send_one "$f" "$type" "$year" "$month"; then
    # roztřídit
    tdir="$(target_dir_for "$type" "$year" "$month")"
    mkdir -p "$tdir"
    mv -n -- "$f" "$tdir/"
    echo "[✓] Sent + moved to: $tdir/"
  else
    echo "[x] Stop on failure."
    exit 1
  fi
done

echo "[done] All files processed."
