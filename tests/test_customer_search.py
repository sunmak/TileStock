import os
import pytest
from test_postgres import client,post

pytestmark=pytest.mark.skipif(not os.getenv('TILESTOCK_TEST_DATABASE_URL'),reason='Disposable test database required')

def add(client,name,phone='',address=''):
    return post(client,'/customers',dict(name=name,phone=phone,address=address),201)

def search(client,term):
    r=client.get('/api/customers/search',params={'q':term})
    assert r.status_code==200,r.text
    return r.json()

def test_partial_name_case_insensitive_and_duplicate_names(client):
    first=add(client,'Sunil Patel','9876500001','Sihor')
    second=add(client,'Sunil Patel','9876500002','Bhavnagar')
    add(client,'Other customer','9000000000')
    items=search(client,'  sUNIL  ')['items']
    assert [x['id'] for x in items]==[first['id'],second['id']]
    assert [x['phone'] for x in items]==['9876500001','9876500002']
    assert [x['address'] for x in items]==['Sihor','Bhavnagar']
    assert len(search(client,'pat')['items'])==2

def test_mobile_matches_partial_and_ignores_phone_formatting(client):
    person=add(client,'Mobile customer','+91 98765-43210')
    add(client,'Unrelated','9000000000')
    for term in ('9876543210','98765','43210','+91 98765 43210'):
        assert [x['id'] for x in search(client,term)['items']]==[person['id']]

def test_empty_missing_and_nonmatching_search(client):
    add(client,'Alice','9876500000')
    for term in ('','   ','not here','----'):
        assert search(client,term)==dict(items=[],has_more=False)
    assert client.get('/api/customers/search').json()==dict(items=[],has_more=False)

def test_results_capped_and_literal_symbols_not_wildcards(client):
    for i in range(22):add(client,'Customer '+str(i).zfill(2),'12345'+str(i).zfill(5))
    result=search(client,'Customer')
    assert len(result['items'])==20 and result['has_more'] is True
    assert result['items'][0]['name']=='Customer 00'
    assert result['items'][-1]['name']=='Customer 19'
    add(client,'A%_Shop','')
    assert [p['name'] for p in search(client,'%_')['items']]==['A%_Shop']
    assert search(client,"' OR 1=1 --")['items']==[]

def test_search_query_length_limit(client):
    assert client.get('/api/customers/search',params={'q':'a'*201}).status_code==422
