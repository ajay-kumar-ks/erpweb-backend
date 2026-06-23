import json
import asyncio
import httpx
from app.main import app

results = []

async def request(client, method, path, json_body=None):
    try:
        if method == 'POST':
            resp = await client.post(path, json=json_body)
        elif method == 'GET':
            resp = await client.get(path)
        else:
            raise ValueError(method)
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        return {'method': method, 'path': path, 'status': resp.status_code, 'body': body}
    except Exception as exc:
        return {'method': method, 'path': path, 'status': None, 'body': str(exc)}

async def run_async():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        # COA
        coa = await request(client, 'POST', '/api/accounts/coa', {
            'account_code': '1000',
            'account_name': 'Cash',
            'account_type': 'asset',
            'parent_account_id': None,
            'is_active': True,
        })
        results.append(coa)
        account_id = None
        if coa['status'] == 200 and isinstance(coa['body'], dict):
            account_id = coa['body'].get('id')

        results.append(await request(client, 'GET', '/api/accounts/coa'))

        # Journals
        journal = await request(client, 'POST', '/api/accounts/journals', {
            'reference': 'JRN-001',
            'description': 'Test Journal',
            'status': 'draft',
            'date': '2026-06-22T00:00:00',
            'lines': [
                {'account_id': account_id or 1, 'memo': 'Debit line', 'debit': 100.0, 'credit': 0.0},
                {'account_id': account_id or 1, 'memo': 'Credit line', 'debit': 0.0, 'credit': 100.0},
            ],
        })
        results.append(journal)
        results.append(await request(client, 'GET', '/api/accounts/journals'))
        results.append(await request(client, 'GET', '/api/accounts/ledger'))

        # Budgets
        budget = await request(client, 'POST', '/api/accounts/budgets', {
            'name': 'Regression Budget',
            'fiscal_year': 2026,
            'total_amount': 1000.0,
            'status': 'draft',
            'start_date': '2026-01-01T00:00:00',
            'end_date': '2026-12-31T23:59:59',
        })
        results.append(budget)
        budget_id = None
        if budget['status'] == 200 and isinstance(budget['body'], dict):
            budget_id = budget['body'].get('id')
        results.append(await request(client, 'GET', '/api/accounts/budgets'))

        if budget_id:
            results.append(await request(client, 'POST', f'/api/accounts/budgets/{budget_id}/lines', {
                'account_id': account_id or 1,
                'allocated_amount': 250.0,
            }))
            results.append(await request(client, 'GET', f'/api/accounts/budgets/{budget_id}/lines'))

        # Expenses and Income
        if account_id:
            results.append(await request(client, 'POST', '/api/accounts/expenses', {
                'description': 'Test Expense',
                'amount': 50.0,
                'account_id': account_id,
            }))
            results.append(await request(client, 'GET', '/api/accounts/expenses'))
            results.append(await request(client, 'POST', '/api/accounts/income', {
                'description': 'Test Income',
                'amount': 120.0,
                'account_id': account_id,
            }))
            results.append(await request(client, 'GET', '/api/accounts/income'))

        # Customers / Invoices / Payments
        customer = await request(client, 'POST', '/api/accounts/customers', {
            'name': 'Test Customer',
            'email': 'customer@example.com',
            'phone': '1234567890',
            'address': '123 Test Lane',
            'is_active': 'active',
        })
        results.append(customer)
        customer_id = customer['body'].get('id') if customer['status'] == 200 and isinstance(customer['body'], dict) else None
        results.append(await request(client, 'GET', '/api/accounts/customers'))

        invoice = await request(client, 'POST', '/api/accounts/invoices', {
            'customer_id': customer_id or 1,
            'invoice_number': 'INV-001',
            'invoice_date': '2026-06-22T00:00:00',
            'due_date': '2026-07-22T00:00:00',
            'amount': 150.0,
            'description': 'Test Invoice',
        })
        results.append(invoice)
        invoice_id = invoice['body'].get('id') if invoice['status'] == 200 and isinstance(invoice['body'], dict) else None
        results.append(await request(client, 'GET', '/api/accounts/invoices'))

        if invoice_id:
            results.append(await request(client, 'POST', f'/api/accounts/invoices/{invoice_id}/payments', {
                'payment_date': '2026-06-23T00:00:00',
                'amount': 150.0,
                'reference': 'PAY-001',
            }))

        # Vendors / Bills / Payments
        vendor = await request(client, 'POST', '/api/accounts/vendors', {
            'name': 'Test Vendor',
            'email': 'vendor@example.com',
            'phone': '0987654321',
            'address': '456 Vendor Road',
            'is_active': 'active',
        })
        results.append(vendor)
        vendor_id = vendor['body'].get('id') if vendor['status'] == 200 and isinstance(vendor['body'], dict) else None
        results.append(await request(client, 'GET', '/api/accounts/vendors'))

        bill = await request(client, 'POST', '/api/accounts/bills', {
            'vendor_id': vendor_id or 1,
            'bill_number': 'BILL-001',
            'bill_date': '2026-06-22T00:00:00',
            'due_date': '2026-07-22T00:00:00',
            'amount': 120.0,
            'description': 'Test Bill',
        })
        results.append(bill)
        bill_id = bill['body'].get('id') if bill['status'] == 200 and isinstance(bill['body'], dict) else None
        results.append(await request(client, 'GET', '/api/accounts/bills'))

        if bill_id:
            results.append(await request(client, 'POST', f'/api/accounts/bills/{bill_id}/payments', {
                'payment_date': '2026-06-23T00:00:00',
                'amount': 120.0,
                'reference': 'VPAY-001',
            }))

        # Reports
        results.append(await request(client, 'GET', '/api/accounts/reports/trial-balance'))
        results.append(await request(client, 'GET', '/api/accounts/reports/profit-loss'))
        results.append(await request(client, 'GET', '/api/accounts/reports/balance-sheet'))

    print(json.dumps(results, indent=2, default=str))

if __name__ == '__main__':
    asyncio.run(run_async())
