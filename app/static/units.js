'use strict';
const stockAdjustmentReasons=['Opening stock','New purchase received','Stock count correction — increase','Stock count correction — decrease','Damaged / broken goods','Return to supplier','Samples / display use','Lost / missing stock','Other adjustment'];
function mountReceiptUnits(){
  if(page!=='inventory')return;
  const form=$('#adjust');
  form.innerHTML=`<h2>Receive or adjust stock</h2><div class="fields"><label>Batch<select name="batch_id" required>${options(state.batches,b=>b.sku+' · '+b.name+(b.colour?' · '+b.colour:'')+' / '+b.code+' · '+qty(b.quantity)+' '+b.unit)}</select></label>${field('Quantity received (+) or reduced (−)','delta','number','required step="0.001"')}<label>Unit<select name="unit" required><option value="piece">piece</option><option value="box">box</option></select></label><label>Reason<select name="reason" required><option value="">Choose a reason…</option>${stockAdjustmentReasons.map(reason=>`<option value="${esc(reason)}">${esc(reason)}</option>`).join('')}</select></label><div id="other-stock-reason-field" hidden><label>Other reason<input name="other_reason" type="text" maxlength="180" placeholder="Explain the stock adjustment" disabled></label></div></div><p class="hint">Choose the unit directly. Saving changes the product's unit for all its batches; existing quantity numbers and prices stay unchanged.</p><button>Save stock movement</button>`;
  let pending=null;
  const otherReason=form.elements.other_reason;
  form.elements.reason.onchange=()=>{
    pending=null;const other=form.elements.reason.value==='Other adjustment';
    $('#other-stock-reason-field').hidden=!other;otherReason.disabled=!other;otherReason.required=other;otherReason.setCustomValidity('');
  };
  otherReason.oninput=()=>otherReason.setCustomValidity('');
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
      let reason=form.elements.reason.value;
      if(!stockAdjustmentReasons.includes(reason))throw Error('Choose a reason.');
      if(reason==='Other adjustment'){
        const detail=otherReason.value.trim();
        if(!detail){otherReason.setCustomValidity('Enter the other reason.');otherReason.reportValidity();return;}
        reason+=': '+detail;
      }
      pending=pending||crypto.randomUUID();
      await api('/batches/'+batch.id+'/adjust',{delta:form.elements.delta.value,unit:form.elements.unit.value,reason,request_key:pending,expected_stock_unit:batch.unit});
      pending=null;await load();message('Stock saved. Unit saved.');
    }catch(error){message(error.message,true);}finally{button.disabled=false;}
  };
}
