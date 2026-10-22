from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Qty = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]

def money(value):
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class StockPolicy(BaseModel):
    criticality: Literal['high','medium','low'] = 'medium'
    minimum_stock: Annotated[Decimal, Field(ge=0,max_digits=12,decimal_places=3)] = Decimal(0)
    critical_stock: Annotated[Decimal, Field(ge=0,max_digits=12,decimal_places=3)] = Decimal(0)
    stock_alerts_enabled: bool = True

    @model_validator(mode='after')
    def valid_thresholds(self):
        if self.critical_stock>self.minimum_stock:
            raise ValueError('Critical stock must not exceed minimum stock')
        return self

class Product(StockPolicy):
    sku: Text
    name: Text
    unit: Text = 'box'
    area_per_unit: Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=4)] = Decimal(0)
    sale_price: Money
    brand: str = Field(default='', max_length=200)
    pack: str = Field(default='', max_length=200)
    grade: str = Field(default='', max_length=200)

class Batch(BaseModel):
    product_id: int = Field(gt=0)
    code: Text
    shade: str = Field(default='', max_length=200)
    size: str = Field(default='', max_length=200)
    colour: str = Field(default='', max_length=200)

class Customer(BaseModel):
    name: Text
    phone: str = Field(default='', max_length=80)
    address: str = Field(default='', max_length=2000)

class Adjustment(BaseModel):
    delta: Annotated[Decimal, Field(max_digits=12, decimal_places=3)]
    reason: Text
    request_key: UUID
    conversion_id: int | None = Field(default=None,gt=0)
    expected_factor: Annotated[Decimal, Field(gt=0,max_digits=12,decimal_places=6)] | None = None
    expected_stock_unit: Text | None = None
    unit: Text | None = None

    @model_validator(mode='after')
    def nonzero(self):
        if self.delta == 0:
            raise ValueError('Quantity change must not be zero')
        if self.conversion_id is not None or self.expected_factor is not None:
            raise ValueError('Unit conversion is no longer used. Choose the stock unit directly.')
        return self

class Line(BaseModel):
    batch_id: int = Field(gt=0)
    quantity: Qty
    unit_price: Money

class Document(BaseModel):
    kind: Literal['estimate', 'invoice']
    customer_id: int = Field(gt=0)
    notes: str = Field(default='', max_length=4000)
    vehicle_no: str = Field(default='', max_length=80)
    lines: list[Line] = Field(min_length=1, max_length=100)
    request_key: UUID

    @model_validator(mode='after')
    def unique_batches(self):
        if len({line.batch_id for line in self.lines}) != len(self.lines):
            raise ValueError('Use one line per batch; combine duplicate quantities')
        if sum(money(x.quantity*x.unit_price) for x in self.lines) > Decimal('999999999999.99'):
            raise ValueError('Document total exceeds supported range')
        return self

class Payment(BaseModel):
    amount: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
    method: Literal['cash', 'bank', 'card', 'upi', 'other']
    reference: str = Field(default='', max_length=200)
    request_key: UUID

class ReturnLine(BaseModel):
    document_line_id: int = Field(gt=0)
    quantity: Qty
    restock: bool = True

class CustomerReturn(BaseModel):
    reason: Text
    request_key: UUID
    lines: list[ReturnLine] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_lines(self):
        if len({line.document_line_id for line in self.lines}) != len(self.lines):
            raise ValueError('Choose each invoice line only once')
        return self

class Correction(BaseModel):
    reason: Text
    request_key: UUID

class ProductEdit(Product):
    reason: Text
    request_key: UUID
    expected_version: int = Field(gt=0)

class CustomerEdit(Customer):
    reason: Text
    request_key: UUID
    expected_version: int = Field(gt=0)

class DraftEdit(Document):
    reason: Text
    expected_version: int = Field(gt=0)
