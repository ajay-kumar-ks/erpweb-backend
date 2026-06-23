import json
import asyncio
import httpx
from app.main import app


async def post(client, path, json_body):
    resp = await client.post(path, json=json_body)
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return {'path': path, 'status': resp.status_code, 'body': body}


async def run_async():
    tests = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        tests.append(await post(client, '/api/accounts/budgets', {'name': 'Dev Budget', 'fiscal_year': 2026, 'total_amount': 1000.0, 'start_date': '2026-01-01T00:00:00', 'end_date': '2026-12-31T23:59:59'}))
        tests.append(await post(client, '/api/accounts/expenses', {'description': 'Office supplies', 'amount': 50.0, 'account_id': 1}))
        tests.append(await post(client, '/api/accounts/income', {'description': 'Consulting', 'amount': 200.0, 'account_id': 2}))

        cust = await client.post('/api/accounts/customers', json={'name': 'Acme Co'})
        try:
            cust_body = cust.json()
        except Exception:
            cust_body = cust.text
        tests.append({'path': '/api/accounts/customers', 'status': cust.status_code, 'body': cust_body})

        tests.append(await post(client, '/api/accounts/invoices', {'customer_id': 1, 'invoice_number': 'INV-001', 'amount': 150.0}))
        tests.append(await post(client, '/api/accounts/bills', {'vendor_id': 1, 'bill_number': 'BILL-001', 'amount': 120.0}))

    print(json.dumps(tests, indent=2))


def run():
    asyncio.run(run_async())


if __name__ == '__main__':
    run()
