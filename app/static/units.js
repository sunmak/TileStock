'use strict';
function mountReceiptUnits(){
  if(page!=='inventory')return;
  const form=$('#adjust');
  form.innerHTML=`<h2>Receive or adjust stock</h2><div class="fields"><label>Batch<select name="batch_id" required>${options(state.batches,b=>b.sku+' · '+b.name+(b.colour?' · '+b.colour:'')+' / '+b.code+' · '+qty(b.quantity)+' '+b.unit)}</select></label>${field('Quantity received (+) or reduced (−)','delta','number','required step="0.001"')}<label>Unit<select name="unit" required><option value="piece">piece</option><option value="box">box</option></select></label>${field('Reason / delivery reference','reason','text','required maxlength="200"')}</div><p class="hint">Choose the unit directly. Saving changes the product's unit for all its batches; existing quantity numbers and prices stay unchanged.</p><button>Save stock movement</button>`;
  let pending=null;
  const currentBatch=()=>state.batches.find(b=>b.id==form.elements.batch_id.value);
  form.elements.batch_id.onchange=()=>{
    pending=null;const batch=currentBatch();if(!batch)return;
    const units=[...new Set([batch.unit,'piece','box','carton','set','sqm','sqft','kg'])];
    form.elements.unit.innerHTML=units.map(unit=>`<option value="${esc(unit)}">${esc(unit)}</option>`).join('');
    form.elements.unit.value=batch.unit;
  };
  form.oninput=()=>{pending=null;};form.elements.unit.onchange=()=>{pending=null;};
  form.onsubmit=async event=>{
    event.preventDefault();const button=form.querySelector('button');button.disabled=true;
    try{
      const batch=currentBatch();if(!batch)throw Error('Select a batch.');
      pending=pending||crypto.randomUUID();
      await api('/batches/'+batch.id+'/adjust',{delta:form.elements.delta.value,unit:form.elements.unit.value,reason:form.elements.reason.value,request_key:pending,expected_stock_unit:batch.unit});
      pending=null;await load();message('Stock saved. Unit saved.');
    }catch(error){message(error.message,true);}finally{button.disabled=false;}
  };
}
