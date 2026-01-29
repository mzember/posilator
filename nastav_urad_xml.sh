# Fakturoid se drží místě příslušného úřadu, kam by se to mělo posílat.
# Příklad, jak upravit všechna XML, pokud by někdo potřeboval nastavit jiné pracoviště:
sed -i.bak-c_ufo 's/c_ufo="[^"]*"/c_ufo="461"/' *.xml; sed -i.bak-c_pracufo 's/c_pracufo="[^"]*"/c_pracufo="3001"/' *.xml
