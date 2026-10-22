"""Product-level stock alerts; batch sums are read from committed inventory.
No stored alert flags, scheduled processes or changes to stock transactions.
"""
from decimal import Decimal

SEVERITY_RANK={'out_of_stock':4,'critical':3,'warning':2,'notice':1,'healthy':0,'disabled':-1}
CRITICALITY_RANK={'high':3,'medium':2,'low':1}

def classify(available, minimum, critical, criticality, enabled=True):
    if not enabled:
        return 'disabled'
    if available==0:
        return 'out_of_stock'
    if critical>0 and available<=critical:
        return 'critical'
    if minimum>0 and available<=minimum:
        return {'high':'critical','medium':'warning','low':'notice'}[criticality]
    return 'healthy'

def snapshot(conn):
    rows=conn.execute('''SELECT p.id,p.sku,p.name,p.unit,p.criticality,p.minimum_stock,p.critical_stock,p.stock_alerts_enabled,
      coalesce(b.available,0) available FROM products p LEFT JOIN
      (SELECT product_id,sum(quantity) available FROM batches GROUP BY product_id) b ON b.product_id=p.id
      ORDER BY p.name,p.id''').fetchall()
    alerts=[]
    for row in rows:
        row['severity']=classify(row['available'],row['minimum_stock'],row['critical_stock'],row['criticality'],row['stock_alerts_enabled'])
        row['shortfall_to_minimum']=max(Decimal(0),row['minimum_stock']-row['available'])
        if row['severity'] in ('healthy','disabled'):
            continue
        row['message']=('No stock available' if row['severity']=='out_of_stock' else
          'At or below critical stock' if row['critical_stock']>0 and row['available']<=row['critical_stock'] else
          'High-criticality product at or below minimum' if row['criticality']=='high' else
          'At or below minimum stock')
        alerts.append(row)
    def order(row):
        coverage=row['available']/row['minimum_stock'] if row['minimum_stock'] else Decimal(0)
        return (-SEVERITY_RANK[row['severity']],-CRITICALITY_RANK[row['criticality']],coverage,row['name'].casefold(),row['id'])
    alerts.sort(key=order)
    summary={key:sum(row['severity']==key for row in alerts) for key in ('out_of_stock','critical','warning','notice')}
    summary['total']=len(alerts)
    summary['monitored']=sum(row['stock_alerts_enabled'] for row in rows)
    return {'alerts':alerts,'products':rows,'summary':summary}
