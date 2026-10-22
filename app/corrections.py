"""Versioned edits and owner-approved, append-only correction history."""
import json
from decimal import Decimal
from fastapi import APIRouter,HTTPException
from psycopg.types.json import Jsonb
from .db import connect,actor_context
from .models import ProductEdit,CustomerEdit,DraftEdit,Correction,money
from .auth import owner_only,audit

router=APIRouter(prefix='/api')

def require(row,label='Record'):
    if not row:raise HTTPException(404,label+' not found')
    return row

def version(row,expected):
    if row['version']!=expected:raise HTTPException(409,'This record changed since you opened it. Close the editor, refresh, and review the latest version.')

def record(c,action,entity,entity_id,body,before,after):
    actor=actor_context.get()
    row=c.execute('''INSERT INTO correction_log(actor_id,actor_email,action,entity,entity_id,reason,before_data,after_data,request_key)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
      (actor['id'],actor['email'],action,entity,entity_id,body.reason,
       Jsonb(json.loads(json.dumps(before,default=str))),Jsonb(json.loads(json.dumps(after,default=str))),body.request_key)).fetchone()
    audit(c,action,'correction_log',row['id'])
    return row['id']

@router.get('/corrections')
def corrections():
    owner_only()
    with connect() as c:return c.execute('''SELECT id,actor_email,action,entity,entity_id,reason,created_at FROM correction_log ORDER BY id DESC LIMIT 500''').fetchall()

@router.post('/products/{product_id}/edit')
def edit_product(product_id:int,body:ProductEdit):
    from .main import once
    with connect() as c:
        def apply():
            old=require(c.execute('SELECT * FROM products WHERE id=%s FOR UPDATE',(product_id,)).fetchone(),'Product')
            version(old,body.expected_version)
            if old['unit']!=body.unit:raise HTTPException(409,'Change stock units using Inventory, not the product editor.')
            new=c.execute('''UPDATE products SET sku=%s,name=%s,area_per_unit=%s,sale_price=%s,brand=%s,pack=%s,grade=%s,
              criticality=%s,minimum_stock=%s,critical_stock=%s,stock_alerts_enabled=%s WHERE id=%s RETURNING *''',
              (body.sku,body.name,body.area_per_unit,body.sale_price,body.brand,body.pack,body.grade,body.criticality,body.minimum_stock,body.critical_stock,body.stock_alerts_enabled,product_id)).fetchone()
            record(c,'PRODUCT_EDITED','products',product_id,body,old,new)
            return {'id':product_id,'version':new['version']}
        return once(c,body.request_key,f'edit-product/{product_id}',body.model_dump(mode='json'),apply)

@router.post('/customers/{customer_id}/edit')
def edit_customer(customer_id:int,body:CustomerEdit):
    from .main import once
    with connect() as c:
        def apply():
            old=require(c.execute('SELECT * FROM customers WHERE id=%s FOR UPDATE',(customer_id,)).fetchone(),'Customer')
            version(old,body.expected_version)
            new=c.execute('UPDATE customers SET name=%s,phone=%s,address=%s WHERE id=%s RETURNING *',(body.name,body.phone,body.address,customer_id)).fetchone()
            record(c,'CUSTOMER_EDITED','customers',customer_id,body,old,new)
            return {'id':customer_id,'version':new['version']}
        return once(c,body.request_key,f'edit-customer/{customer_id}',body.model_dump(mode='json'),apply)

@router.post('/documents/{doc_id}/edit')
def edit_draft(doc_id:int,body:DraftEdit):
    owner_only()
    from .main import once
    with connect() as c:
        def apply():
            old=require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE',(doc_id,)).fetchone(),'Document')
            version(old,body.expected_version)
            if old['status']!='draft':raise HTTPException(409,'Only draft documents can be edited. Posted and void documents are preserved.')
            if old['kind']!=body.kind:raise HTTPException(409,'Document type cannot be changed')
            if c.execute('SELECT 1 FROM documents WHERE source_estimate_id=%s',(doc_id,)).fetchone():
                raise HTTPException(409,'This estimate already has a linked invoice. Edit its invoice draft instead.')
            old['lines']=c.execute('SELECT * FROM document_lines WHERE document_id=%s ORDER BY id',(doc_id,)).fetchall()
            customer=require(c.execute('SELECT * FROM customers WHERE id=%s',(body.customer_id,)).fetchone(),'Customer')
            c.execute('''SELECT id FROM products WHERE id IN (SELECT product_id FROM batches WHERE id=ANY(%s)) ORDER BY id FOR UPDATE''',([l.batch_id for l in body.lines],)).fetchall()
            total=sum((money(l.quantity*l.unit_price) for l in body.lines),Decimal(0))
            new=c.execute('''UPDATE documents SET customer_id=%s,customer_name=%s,customer_address=%s,notes=%s,vehicle_no=%s,total=%s WHERE id=%s RETURNING *''',
                (body.customer_id,customer['name'],customer['address'],body.notes,body.vehicle_no,total,doc_id)).fetchone()
            c.execute('DELETE FROM document_lines WHERE document_id=%s',(doc_id,))
            for line in body.lines:
                b=require(c.execute('''SELECT b.code,b.colour,p.name,p.unit,p.brand,p.pack,p.grade FROM batches b JOIN products p ON p.id=b.product_id WHERE b.id=%s''',(line.batch_id,)).fetchone(),'Batch')
                c.execute('''INSERT INTO document_lines(document_id,batch_id,description,unit,quantity,unit_price,amount,product_name,brand,pack,grade,colour)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                  (doc_id,line.batch_id,b['name']+' / '+b['code'],b['unit'],line.quantity,line.unit_price,money(line.quantity*line.unit_price),b['name'],b['brand'],b['pack'],b['grade'],b['colour']))
            new['lines']=c.execute('SELECT * FROM document_lines WHERE document_id=%s ORDER BY id',(doc_id,)).fetchall()
            correction=record(c,'DRAFT_EDITED','documents',doc_id,body,old,new)
            return {'id':doc_id,'version':new['version'],'correction_id':correction}
        return once(c,body.request_key,f'edit-draft/{doc_id}',body.model_dump(mode='json'),apply)

@router.post('/returns/{return_id}/reverse')
def reverse_return(return_id:int,body:Correction):
    actor=owner_only()
    from .main import once
    with connect() as c:
        def apply():
            meta=require(c.execute('SELECT document_id FROM customer_returns WHERE id=%s',(return_id,)).fetchone(),'Return')
            d=require(c.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE',(meta['document_id'],)).fetchone(),'Invoice')
            r=require(c.execute('SELECT * FROM customer_returns WHERE id=%s FOR UPDATE',(return_id,)).fetchone(),'Return')
            if r['reversed_at']:return {'id':return_id,'already_reversed':True}
            if d['status']!='posted':raise HTTPException(409,'Only returns on posted invoices can be reversed')
            # Preserve cumulative half-up rounding and all original credited amounts.
            # For an affected invoice line, later active returns must be undone first.
            later=c.execute('''SELECT 1 FROM customer_return_lines a JOIN customer_return_lines b ON b.document_line_id=a.document_line_id
              JOIN customer_returns r ON r.id=b.return_id WHERE a.return_id=%s AND b.return_id>%s AND r.reversed_at IS NULL LIMIT 1''',(return_id,return_id)).fetchone()
            if later:raise HTTPException(409,'Reverse later active returns for these invoice items first, then reverse this return. This preserves exact credit rounding.')
            balances=c.execute('SELECT * FROM document_balances WHERE document_id=%s',(d['id'],)).fetchone()
            new_net=balances['net_total']+r['total']
            if balances['refunded']>max(balances['paid']-new_net,Decimal(0)):
                raise HTTPException(409,'Reverse the incorrect refund records first. Reversing this return would leave refunds exceeding customer credit.')
            lines=c.execute('''SELECT rl.*,l.batch_id FROM customer_return_lines rl JOIN document_lines l ON l.id=rl.document_line_id
              WHERE rl.return_id=%s ORDER BY l.batch_id''',(return_id,)).fetchall()
            for line in lines:
                if not line['restock']:continue
                b=require(c.execute('SELECT * FROM batches WHERE id=%s FOR UPDATE',(line['batch_id'],)).fetchone(),'Batch')
                if b['quantity']<line['quantity']:raise HTTPException(409,'Not enough stock to undo this return. Reconcile stock first; nothing was reversed.')
                c.execute('UPDATE batches SET quantity=quantity-%s WHERE id=%s',(line['quantity'],b['id']))
                c.execute('''INSERT INTO stock_movements(batch_id,delta,reason,document_id,return_id) VALUES (%s,%s,%s,%s,%s)''',
                  (b['id'],-line['quantity'],f'Reverse return #{return_id}: '+body.reason,d['id'],return_id))
            new=c.execute('UPDATE customer_returns SET reversed_at=now(),reversed_by=%s,reversal_reason=%s WHERE id=%s RETURNING *',(actor['id'],body.reason,return_id)).fetchone()
            correction=record(c,'RETURN_REVERSED','customer_returns',return_id,body,r,new)
            return {'id':return_id,'correction_id':correction}
        return once(c,body.request_key,f'reverse-return/{return_id}',body.model_dump(mode='json'),apply)

@router.post('/refunds/{refund_id}/reverse')
def reverse_refund(refund_id:int,body:Correction):
    actor=owner_only()
    from .main import once
    with connect() as c:
        def apply():
            meta=require(c.execute('SELECT document_id FROM refunds WHERE id=%s',(refund_id,)).fetchone(),'Refund')
            require(c.execute('SELECT id FROM documents WHERE id=%s FOR UPDATE',(meta['document_id'],)).fetchone(),'Invoice')
            r=require(c.execute('SELECT * FROM refunds WHERE id=%s FOR UPDATE',(refund_id,)).fetchone(),'Refund')
            if r['reversed_at']:return {'id':refund_id,'already_reversed':True}
            new=c.execute('UPDATE refunds SET reversed_at=now(),reversed_by=%s,reversal_reason=%s WHERE id=%s RETURNING *',(actor['id'],body.reason,refund_id)).fetchone()
            correction=record(c,'REFUND_REVERSED','refunds',refund_id,body,r,new)
            return {'id':refund_id,'correction_id':correction}
        return once(c,body.request_key,f'reverse-refund/{refund_id}',body.model_dump(mode='json'),apply)
