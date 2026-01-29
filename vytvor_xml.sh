set -a
source .env
set +a
python3 vytvor_xml.py "$@"
