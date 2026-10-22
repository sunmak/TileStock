import hashlib
import json
import logging
import os
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from .db import ROOT, connect, migrate, actor_context
from .auth import router as auth_router, access, owner_only
from .corrections import router as corrections_router
from .models import Product, Batch, Customer, Adjustment, Document, Payment, CustomerReturn, StockPolicy, money
from .stock_alerts import snapshot

@asynccontextmanager
async def lifespan(app):
    migrate()
    yield

app = FastAPI(title='Shivam Tiles', version='0.6.0', lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.include_router(auth_router)
app.include_router(corrections_router)

@app.middleware('http')
async def local_only(request: Request, call_next):
    # Fixed loopback deployment. Reject DNS rebinding and cross-site writes.
    if request.headers.get('host', '') not in ('127.0.0.1:8000', 'localhost:8000', 'testserver'):
        return JSONResponse({'detail': 'Use http://127.0.0.1:8000'}, status_code=400)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('origin')
        if origin and origin not in ('http://127.0.0.1:8000', 'http://localhost:8000'):
            return JSONResponse({'detail': 'Cross-site writes are disabled'}, status_code=403)
        if request.headers.get('x-tilestock-client') != 'local':
            return JSONResponse({'detail': 'Missing local client header'}, status_code=403)
    try:
        actor,error=access(request)
    except (psycopg.Error,RuntimeError):
        return JSONResponse({'detail':'Login service unavailable. Check the database and security key.'},status_code=503)
    if error:return JSONResponse({'detail':error[1]},status_code=error[0])
    context=actor_context.set(actor)
    try:
        response=await call_next(request)
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        return response
    finally:actor_context.reset(context)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    # Pydantic's default errors include input values; never echo password/OTP inputs.
    return JSONResponse({'detail':[{'loc':e['loc'],'msg':e['msg'],'type':e['type']} for e in exc.errors()]},status_code=422)

@app.exception_handler(psycopg.Error)
async def database_error(request, exc):
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return JSONResponse({'detail': 'This SKU, batch code, email or request already exists.'}, status_code=409)
    if isinstance(exc, (psycopg.errors.ForeignKeyViolation, psycopg.errors.CheckViolation, psycopg.errors.NumericValueOutOfRange)):
        return JSONResponse({'detail': 'Invalid reference or value outside the database limits.'}, status_code=422)
    logging.exception('Database request failed', exc_info=exc)
    return JSONResponse({'detail': 'Database unavailable or busy. Check PostgreSQL and retry.'}, status_code=503)

def require(row, label='Record'):
    if not row:
        raise HTTPException(404, label + ' not found')
    return row

def once(conn, key, scope, payload, operation):
    """Serialize retries by key; reject reuse for a different operation or body."""
    key = str(key)
    fingerprint = hashlib.sha256((scope + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
    conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (key,))
    previous = conn.execute('SELECT * FROM api_requests WHERE request_key=%s', (key,)).fetchone()
    if previous:
        if previous['fingerprint'] != fingerprint:
            raise HTTPException(409, 'Request key was already used for different data')
        return previous['result']
    result = operation()
    conn.execute('INSERT INTO api_requests VALUES (%s,%s,%s)', (key, fingerprint, Jsonb(result)))
    return result

@app.get('/api/health')
def health():
    with connect() as conn:
        conn.execute('SELECT 1')
    return {'status': 'ok', 'business_name': os.getenv('BUSINESS_NAME', 'Shivam Tiles'), 'currency': os.getenv('CURRENCY', 'INR')}

@app.get('/api/products')
def products():
    with connect() as c:
        return c.execute('SELECT * FROM products ORDER BY name,id').fetchall()

@app.post('/api/products', status_code=201)
def create_product(body: Product):
    with connect() as c:
        return c.execute('''INSERT INTO products(sku,name,unit,area_per_unit,sale_price,brand,pack,grade,
          criticality,minimum_stock,critical_stock,stock_alerts_enabled) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
          (body.sku,body.name,body.unit,body.area_per_unit,body.sale_price,body.brand,body.pack,body.grade,
           body.criticality,body.minimum_stock,body.critical_stock,body.stock_alerts_enabled)).fetchone()

@app.post('/api/products/{product_id}/stock-policy')
def stock_policy(product_id: int, body: StockPolicy):
    with connect() as c:
        return require(c.execute('''UPDATE products SET criticality=%s,minimum_stock=%s,critical_stock=%s,
          stock_alerts_enabled=%s WHERE id=%s RETURNING *''',
          (body.criticality,body.minimum_stock,body.critical_stock,body.stock_alerts_enabled,product_id)).fetchone(),'Product')

@app.get('/api/stock-alerts')
def stock_alerts():
    with connect() as c:
        return snapshot(c)

@app.get('/api/batches')
def batches():
    with connect() as c:
        return c.execute('SELECT b.*,p.sku,p.name,p.unit,p.area_per_unit,p.sale_price FROM batches b JOIN products p ON p.id=b.product_id ORDER BY p.name,b.id').fetchall()

@app.post('/api/batches', status_code=201)
def create_batch(body: Batch):
    with connect() as c:
        return c.execute('INSERT INTO batches(product_id,code,shade,size,colour) VALUES (%s,%s,%s,%s,%s) RETURNING *',
                         (body.product_id,body.code,body.shade,body.size,body.colour)).fetchone()

@app.get('/api/customers')
def customers():
    with connect() as c:
        return c.execute('SELECT * FROM customers ORDER BY name,id').fetchall()

@app.get('/api/customers/search')
def search_customers(q: str = Query(default='',max_length=200)):
    term=q.strip()
    if not term:
        return {'items':[],'has_more':False}
    digits=''.join(char for char in term if char in '0123456789') if not any(char.isalpha() for char in term) else ''
    with connect() as c:
        rows=c.execute('''SELECT id,name,phone,address FROM customers
          WHERE strpos(lower(name),lower(%s))>0
             OR (%s<>'' AND strpos(regexp_replace(phone,'[^0-9]','','g'),%s)>0)
          ORDER BY lower(name),id LIMIT 21''',(term,digits,digits)).fetchall()
        return {'items':rows[:20],'has_more':len(rows)>20}

@app.post('/api/customers', status_code=201)
def create_customer(body: Customer):
    with connect() as c:
        return c.execute('INSERT INTO customers(name,phone,address) VALUES (%s,%s,%s) RETURNING *',
                         (body.name,body.phone,body.address)).fetchone()

@app.post('/api/batches/{batch_id}/adjust')
def adjust(batch_id: int, body: Adjustment):
    with connect() as c:
        def apply():
            product=require(c.execute('SELECT p.* FROM products p JOIN batches b ON b.product_id=p.id WHERE b.id=%s FOR UPDATE OF p',(batch_id,)).fetchone(),'Batch')
            if body.expected_stock_unit is not None and body.expected_stock_unit!=product['unit']:
                raise HTTPException(409,'The stock unit changed. Refresh and review this receipt before saving.')
            b = require(c.execute('SELECT * FROM batches WHERE id=%s FOR UPDATE', (batch_id,)).fetchone(), 'Batch')
            unit=body.unit or product['unit']
            actor=actor_context.get()
            if actor and actor['role']!='owner' and (body.delta<0 or unit!=product['unit']):
                raise HTTPException(403,'Only the owner can reduce stock manually or change the stock unit')
            if unit!=product['unit']:
                c.execute('UPDATE products SET unit=%s WHERE id=%s',(unit,product['id']))
            delta=body.delta
            factor=Decimal(1)
            if b['quantity'] + delta < 0:
                raise HTTPException(409, 'Adjustment would make stock negative')
            c.execute('UPDATE batches SET quantity=quantity+%s WHERE id=%s', (delta,batch_id))
            row = c.execute('''INSERT INTO stock_movements(batch_id,delta,reason,request_key,entered_quantity,entered_unit,conversion_factor,stock_unit)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
              (batch_id,delta,body.reason,body.request_key,body.delta,unit,factor,unit)).fetchone()
            return row
        return once(c,body.request_key,f'adjust/{batch_id}',body.model_dump(mode='json'),apply)

@app.get('/api/movements')
def movements():
    with connect() as c:
        return c.execute('SELECT m.*,p.name,p.unit AS base_unit,b.code FROM stock_movements m JOIN batches b ON b.id=m.batch_id JOIN products p ON p.id=b.product_id ORDER BY m.id DESC LIMIT 500').fetchall()

@app.get('/api/documents')
def documents():
    with connect() as c:
        return c.execute('''SELECT d.*,b.paid,b.returned,b.refunded,b.net_total,b.balance,b.due,b.refund_due
          FROM documents d JOIN document_balances b ON b.document_id=d.id ORDER BY d.id DESC''').fetchall()

@app.get('/api/documents/{doc_id}')
def document(doc_id: int):
    with connect() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        d = require(c.execute('SELECT * FROM documents WHERE id=%s', (doc_id,)).fetchone())
        d['lines'] = c.execute('''SELECT l.*,coalesce(r.quantity,0) AS returned_quantity,
          l.quantity-coalesce(r.quantity,0) AS returnable_quantity FROM document_lines l
          LEFT JOIN (SELECT rl.document_line_id,sum(rl.quantity) quantity FROM customer_return_lines rl JOIN customer_returns cr ON cr.id=rl.return_id WHERE cr.reversed_at IS NULL GROUP BY rl.document_line_id) r
          ON r.document_line_id=l.id WHERE l.document_id=%s ORDER BY l.id''', (doc_id,)).fetchall()
        d['payments'] = c.execute('SELECT * FROM payments WHERE document_id=%s ORDER BY id', (doc_id,)).fetchall()
        d.update(c.execute('SELECT paid,returned,refunded,net_total,balance,due,refund_due FROM document_balances WHERE document_id=%s',(doc_id,)).fetchone())
        d['returns'] = c.execute('SELECT * FROM customer_returns WHERE document_id=%s ORDER BY id',(doc_id,)).fetchall()
        d['refunds'] = c.execute('SELECT * FROM refunds WHERE document_id=%s ORDER BY id',(doc_id,)).fetchall()
        d['previous_balance'] = c.execute('''SELECT coalesce(sum(b.balance),0) amount
          FROM documents d JOIN document_balances b ON b.document_id=d.id
          WHERE d.customer_id=%s AND d.id<%s AND d.kind='invoice' AND d.status='posted' ''',
          (d['customer_id'],doc_id)).fetchone()['amount']
        return d

@app.get('/api/documents/{doc_id}/pdf')
def document_pdf(doc_id: int):
    from .invoice_pdf import render_bill
    d = document(doc_id)
    content = render_bill(d)
    return Response(content, media_type='application/pdf', headers={
        'Content-Disposition': f'inline; filename="Shivam-Tiles-{d["kind"]}-{doc_id:06d}.pdf"',
        'Cache-Control': 'no-store'})

@app.post('/api/documents', status_code=201)
def create_document(body: Document):
    with connect() as c:
        def apply():
            customer = require(c.execute('SELECT * FROM customers WHERE id=%s', (body.customer_id,)).fetchone(), 'Customer')
            c.execute('''SELECT id FROM products WHERE id IN
              (SELECT product_id FROM batches WHERE id=ANY(%s)) ORDER BY id FOR UPDATE''',
              ([line.batch_id for line in body.lines],)).fetchall()
            total = sum((money(l.quantity*l.unit_price) for l in body.lines), Decimal(0))
            d = c.execute('''INSERT INTO documents(kind,status,customer_id,customer_name,customer_address,request_key,notes,total,vehicle_no)
              VALUES (%s,'draft',%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
              (body.kind,body.customer_id,customer['name'],customer['address'],body.request_key,body.notes,total,body.vehicle_no)).fetchone()
            for line in body.lines:
                b = require(c.execute('SELECT b.code,b.colour,p.name,p.unit,p.brand,p.pack,p.grade FROM batches b JOIN products p ON p.id=b.product_id WHERE b.id=%s', (line.batch_id,)).fetchone(), 'Batch')
                c.execute('''INSERT INTO document_lines(document_id,batch_id,description,unit,quantity,unit_price,amount,product_name,brand,pack,grade,colour)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                  (d['id'],line.batch_id,b['name']+' / '+b['code'],b['unit'],line.quantity,line.unit_price,money(line.quantity*line.unit_price),b['name'],b['brand'],b['pack'],b['grade'],b['colour']))
            return d
        return once(c,body.request_key,'create-document',body.model_dump(mode='json'),apply)

@app.post('/api/documents/{doc_id}/convert')
def convert(doc_id: int):
    with connect() as c:
        d = require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE', (doc_id,)).fetchone())
        if d['kind'] != 'estimate' or d['status'] != 'draft':
            raise HTTPException(409, 'Only an active estimate can be converted')
        existing = c.execute('SELECT id FROM documents WHERE source_estimate_id=%s', (doc_id,)).fetchone()
        if existing:
            return existing
        new = c.execute('''INSERT INTO documents(kind,status,customer_id,customer_name,customer_address,source_estimate_id,request_key,notes,total,vehicle_no)
          VALUES ('invoice','draft',%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
          (d['customer_id'],d['customer_name'],d['customer_address'],doc_id,uuid4(),d['notes'],d['total'],d['vehicle_no'])).fetchone()
        c.execute('''INSERT INTO document_lines(document_id,batch_id,description,unit,quantity,unit_price,amount,product_name,brand,pack,grade,colour)
          SELECT %s,batch_id,description,unit,quantity,unit_price,amount,product_name,brand,pack,grade,colour FROM document_lines WHERE document_id=%s''', (new['id'],doc_id))
        return new

@app.post('/api/documents/{doc_id}/post')
def post_invoice(doc_id: int):
    with connect() as c:
        d = require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE', (doc_id,)).fetchone())
        if d['kind'] != 'invoice' or d['status'] == 'void':
            raise HTTPException(409, 'Only an active invoice can be posted')
        if d['status'] == 'posted':
            return {'id':doc_id}
        lines = c.execute('SELECT * FROM document_lines WHERE document_id=%s ORDER BY batch_id', (doc_id,)).fetchall()
        # Deterministic row lock order prevents overlapping invoice deadlocks.
        for line in lines:
            b = require(c.execute('SELECT * FROM batches WHERE id=%s FOR UPDATE', (line['batch_id'],)).fetchone())
            if b['quantity'] < line['quantity']:
                raise HTTPException(409, f"Insufficient stock: {line['description']} (available {b['quantity']})")
            c.execute('UPDATE batches SET quantity=quantity-%s WHERE id=%s', (line['quantity'],b['id']))
            c.execute("INSERT INTO stock_movements(batch_id,delta,reason,document_id) VALUES (%s,%s,'Invoice posted',%s)", (b['id'],-line['quantity'],doc_id))
        c.execute("UPDATE documents SET status='posted',posted_at=now() WHERE id=%s", (doc_id,))
        return {'id':doc_id}

@app.post('/api/documents/{doc_id}/void')
def void_document(doc_id: int):
    with connect() as c:
        d = require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE', (doc_id,)).fetchone())
        if d['status'] == 'void':
            return {'id':doc_id}
        if c.execute('SELECT 1 FROM customer_returns WHERE document_id=%s AND reversed_at IS NULL',(doc_id,)).fetchone():
            raise HTTPException(409, 'Invoices with returns cannot be voided; stock has already been restored for returned items')
        if c.execute('SELECT 1 FROM payments WHERE document_id=%s', (doc_id,)).fetchone():
            raise HTTPException(409, 'Paid invoices cannot be voided. Receive a customer return and record any refund instead.')
        if d['status'] == 'posted':
            for line in c.execute('SELECT * FROM document_lines WHERE document_id=%s ORDER BY batch_id', (doc_id,)).fetchall():
                c.execute('SELECT id FROM batches WHERE id=%s FOR UPDATE', (line['batch_id'],))
                c.execute('UPDATE batches SET quantity=quantity+%s WHERE id=%s', (line['quantity'],line['batch_id']))
                c.execute("INSERT INTO stock_movements(batch_id,delta,reason,document_id) VALUES (%s,%s,'Invoice voided',%s)", (line['batch_id'],line['quantity'],doc_id))
        c.execute("UPDATE documents SET status='void' WHERE id=%s", (doc_id,))
        return {'id':doc_id}

@app.post('/api/documents/{doc_id}/payments', status_code=201)
def payment(doc_id: int, body: Payment):
    with connect() as c:
        def apply():
            d = require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE', (doc_id,)).fetchone())
            if d['kind'] != 'invoice' or d['status'] != 'posted':
                raise HTTPException(409, 'Payments require a posted invoice')
            due = c.execute('SELECT due FROM document_balances WHERE document_id=%s', (doc_id,)).fetchone()['due']
            if body.amount > due:
                raise HTTPException(409, 'Payment exceeds outstanding balance')
            return c.execute('INSERT INTO payments(document_id,amount,method,reference,request_key) VALUES (%s,%s,%s,%s,%s) RETURNING id',
                             (doc_id,body.amount,body.method,body.reference,body.request_key)).fetchone()
        return once(c,body.request_key,f'payment/{doc_id}',body.model_dump(mode='json'),apply)

@app.get('/api/returns')
def returns():
    with connect() as c:
        return c.execute('''SELECT r.*,d.customer_name,d.customer_id FROM customer_returns r
          JOIN documents d ON d.id=r.document_id ORDER BY r.id DESC''').fetchall()

@app.get('/api/returns/{return_id}')
def return_detail(return_id: int):
    with connect() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        r = require(c.execute('''SELECT r.*,d.customer_name,d.customer_id FROM customer_returns r JOIN documents d
          ON d.id=r.document_id WHERE r.id=%s''',(return_id,)).fetchone(),'Return')
        r['lines'] = c.execute('''SELECT rl.*,l.description,l.unit,l.batch_id,l.unit_price
          FROM customer_return_lines rl JOIN document_lines l ON l.id=rl.document_line_id
          WHERE rl.return_id=%s ORDER BY rl.id''',(return_id,)).fetchall()
        return r

@app.post('/api/documents/{doc_id}/returns', status_code=201)
def receive_return(doc_id: int, body: CustomerReturn):
    with connect() as c:
        def apply():
            d = require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE',(doc_id,)).fetchone(),'Invoice')
            if d['kind'] != 'invoice' or d['status'] != 'posted':
                raise HTTPException(409,'Returns require a posted invoice')
            validated=[]
            for requested in body.lines:
                original = require(c.execute('SELECT * FROM document_lines WHERE id=%s AND document_id=%s',
                  (requested.document_line_id,doc_id)).fetchone(),'Invoice line')
                prior = c.execute('''SELECT coalesce(sum(quantity),0) quantity,coalesce(sum(amount),0) amount
                  FROM customer_return_lines rl JOIN customer_returns cr ON cr.id=rl.return_id WHERE rl.document_line_id=%s AND cr.reversed_at IS NULL''',(original['id'],)).fetchone()
                cumulative=prior['quantity']+requested.quantity
                if cumulative>original['quantity']:
                    raise HTTPException(409,f"Return exceeds remaining quantity for {original['description']}")
                # Cumulative rounding means many partial returns credit exactly the
                # original rounded line amount when the full quantity is returned.
                credit=money(cumulative*original['unit_price'])-prior['amount']
                validated.append((original,requested,credit))
            total=sum((entry[2] for entry in validated),Decimal(0))
            r=c.execute('''INSERT INTO customer_returns(document_id,reason,total,request_key)
              VALUES (%s,%s,%s,%s) RETURNING id''',(doc_id,body.reason,total,body.request_key)).fetchone()
            for original,requested,credit in sorted(validated,key=lambda entry:entry[0]['batch_id']):
                c.execute('''INSERT INTO customer_return_lines(return_id,document_line_id,quantity,restock,amount)
                  VALUES (%s,%s,%s,%s,%s)''',(r['id'],original['id'],requested.quantity,requested.restock,credit))
                if requested.restock:
                    c.execute('SELECT id FROM batches WHERE id=%s FOR UPDATE',(original['batch_id'],))
                    c.execute('UPDATE batches SET quantity=quantity+%s WHERE id=%s',(requested.quantity,original['batch_id']))
                    c.execute('''INSERT INTO stock_movements(batch_id,delta,reason,document_id,return_id)
                      VALUES (%s,%s,%s,%s,%s)''',(original['batch_id'],requested.quantity,'Customer return #'+str(r['id'])+': '+body.reason,doc_id,r['id']))
            return r
        return once(c,body.request_key,f'return/{doc_id}',body.model_dump(mode='json'),apply)

@app.post('/api/documents/{doc_id}/refunds', status_code=201)
def refund(doc_id: int, body: Payment):
    with connect() as c:
        def apply():
            d=require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE',(doc_id,)).fetchone(),'Invoice')
            if d['kind']!='invoice' or d['status']!='posted':
                raise HTTPException(409,'Refunds require a posted invoice')
            available=c.execute('SELECT refund_due FROM document_balances WHERE document_id=%s',(doc_id,)).fetchone()['refund_due']
            if body.amount>available:
                raise HTTPException(409,'Refund exceeds the available customer credit on this invoice')
            return c.execute('''INSERT INTO refunds(document_id,amount,method,reference,request_key)
              VALUES (%s,%s,%s,%s,%s) RETURNING id''',(doc_id,body.amount,body.method,body.reference,body.request_key)).fetchone()
        return once(c,body.request_key,f'refund/{doc_id}',body.model_dump(mode='json'),apply)

app.mount('/static', StaticFiles(directory=ROOT/'app'/'static'), name='static')

@app.get('/')
def index():
    return FileResponse(ROOT/'app'/'static'/'index.html')
