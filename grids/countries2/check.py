import csv, subprocess, sys
part, start, cid = sys.argv[1:4]
country = [r for r in csv.DictReader(open('grids/countries2/cells.tsv'), delimiter='\t') if r['id'] == cid][0]['country']
rows = list(csv.DictReader(open(part), delimiter='\t'))
if len(rows) != 1:
    print(f"expected the header line (country topic start_date scale url1 date1 quote1 url2 date2 quote2, tab separated) followed by exactly 1 data row; got {len(rows)} data rows. First line of your file: {open(part).readline()[:80]!r}"); sys.exit(0)
if rows[0]['country'] not in (country, 'NONE'):
    print(f"first field must be exactly '{country}' or NONE, got '{rows[0]['country']}'"); sys.exit(0)
r = subprocess.run(['python3', 'grids/countries/check_countries.py', part, start, cid], capture_output=True, text=True)
print(r.stdout, end='')
