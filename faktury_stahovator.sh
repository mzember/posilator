set -a
source .env
set +a
python3 fakturoid_monthly_eu_sum.py # --month 2025-12 --back 6
