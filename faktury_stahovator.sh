set -a
source .env
set +a
python3 faktury_stahovator.py # --month 2025-12 --back 6
