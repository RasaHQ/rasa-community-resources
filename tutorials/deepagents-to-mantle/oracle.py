"""Print independent billing-country revenue from the pinned public database."""
import hashlib
import json
from shared import database
from fetch_data import SHA256

if __name__ == '__main__':
    if hashlib.sha256(database.database_path().read_bytes()).hexdigest() != SHA256:
        raise SystemExit('Oracle requires the pinned public Chinook database')
    result = database.query('SELECT BillingCountry, ROUND(SUM(Total),2) AS revenue FROM Invoice GROUP BY BillingCountry ORDER BY revenue DESC, BillingCountry ASC LIMIT 5')
    if result['status'] != 'ok':
        raise SystemExit('Oracle query failed')
    print(json.dumps(result, indent=2))
