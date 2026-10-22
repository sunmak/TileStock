from decimal import Decimal
from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.models import Document, Adjustment, Payment, money

def test_half_up_rounding():
    assert money(Decimal('1.005')) == Decimal('1.01')
    assert money(Decimal('2.345')*Decimal('1.11')) == Decimal('2.60')

def test_duplicate_batch_rejected():
    with pytest.raises(ValidationError):
        Document(kind='invoice',customer_id=1,request_key=uuid4(),lines=[dict(batch_id=1,quantity=1,unit_price=1)]*2)

@pytest.mark.parametrize('value',['0','NaN','Infinity','0.0001'])
def test_invalid_adjustments(value):
    with pytest.raises(ValidationError):
        Adjustment(delta=value,reason='Test',request_key=uuid4())

@pytest.mark.parametrize('value',['0','-1','1.001','NaN'])
def test_invalid_payments(value):
    with pytest.raises(ValidationError):
        Payment(amount=value,method='cash',request_key=uuid4())
