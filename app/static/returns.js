'use strict';
const customerReturnReasons=['Excess / unused material','Wrong product ordered','Wrong product supplied','Wrong size / colour / shade','Damaged / broken goods','Defective product / quality issue','Customer changed requirement','Order cancelled','Other reason'];
function returnNumber(id){return 'RET-'+String(id).padStart(6,'0');}
function renderReturns(){
  const invoices=state.documents.filter(d=>d.kind==='invoice'&&d.status==='posted');
  $('#content').innerHTML=`<div class="panel"><h2>Receive a customer return</h2><p class="hint">Search by customer name or mobile, select the customer, then choose their original invoice. Resellable goods go back to their original batch. Corrections require an owner and a reason.</p><form id="return-customer-filter">${customerPicker('return-customer')}<button type="button" id="return-show-all" class="secondary">Show all customers / invoices</button></form><section id="return-customer-browser" class="panel" hidden></section><label>Original invoice<select id="return-invoice"></select></label><p id="return-invoice-status" class="hint" role="status"></p><button id="load-return-invoice" class="secondary">Load invoice items</button><div id="return-items"></div></div><div class="panel"><h2>Return history</h2><div id="return-history"></div></div>`;
  const picker=bindCustomerPicker('return-customer');$('#return-customer-filter').onsubmit=e=>e.preventDefault();
  const draw=()=>{const id=$('#selected-return-customer-id').value,pending=$('#return-customer-search').value.trim()&&!id;$('#return-items').replaceChildren();$('#return-invoice').innerHTML=options(pending?[]:invoices.filter(d=>!id||String(d.customer_id)===id),d=>number(d)+' · '+d.customer_name);$('#return-invoice-status').textContent=pending?'Select a matching customer to see their invoices.':id?(invoices.some(d=>String(d.customer_id)===id)?'Choose one of this customer’s posted invoices.':'This customer has no posted invoices available for returns.'):'Showing posted invoices for all customers.';const rows=pending?[]:state.returns.filter(r=>!id||String(r.customer_id)===id);$('#return-history').innerHTML=table(['Return','Invoice','Customer','Received','Credit','Status','Reason',''],rows.map(r=>`<tr><td>${returnNumber(r.id)}</td><td>INV-${String(r.document_id).padStart(6,'0')}</td><td>${esc(r.customer_name)}</td><td>${new Date(r.created_at).toLocaleString()}</td><td>${cash(r.total)}</td><td>${r.reversed_at?'Reversed':'Active'}</td><td>${esc(r.reversed_at?r.reversal_reason:r.reason)}</td><td><button class="secondary" data-return-view="${r.id}">View</button></td></tr>`));document.querySelectorAll('[data-return-view]').forEach(b=>b.onclick=()=>openReturn(b.dataset.returnView));};
  const browseCustomers=mountReturnCustomerBrowser(picker);
  $('#return-customer-search').addEventListener('change',draw);$('#return-customer-search').addEventListener('input',draw);$('#return-show-all').onclick=()=>{$('#return-customer-search').value='';$('#return-customer-search').dispatchEvent(new Event('input',{bubbles:true}));browseCustomers();};
  $('#load-return-invoice').onclick=()=>loadReturnItems($('#return-invoice').value);$('#return-invoice').onchange=()=>$('#return-items').replaceChildren();draw();
}
async function loadReturnItems(id){
  if(!id){message('Choose an invoice first.',true);return;}
  try{
    const d=await api('/documents/'+id);
    if($('#return-invoice').value!==String(id))return;
    const lines=d.lines.filter(l=>Number(l.returnable_quantity)>0);
    $('#return-items').innerHTML=`<form id="receive-return" style="margin-top:24px"><h3>${number(d)} · ${esc(d.customer_name)}</h3>${table(['Product / batch','Sold','Already returned','Return now','Add to sellable stock'],lines.map(l=>`<tr><td>${esc(l.description)}<br><small>${cash(l.unit_price)} / ${esc(l.unit)}</small></td><td>${qty(l.quantity)} ${esc(l.unit)}</td><td>${qty(l.returned_quantity)}</td><td><input aria-label="Return quantity for ${esc(l.description)}" data-return-line="${l.id}" type="number" min="0" max="${esc(l.returnable_quantity)}" step="0.001" value="0" required></td><td><label class="restock-label"><input data-restock-line="${l.id}" type="checkbox" checked> Resellable</label></td></tr>`))}<label>Reason for return<select name="reason" required><option value="">Choose a reason…</option>${customerReturnReasons.map(reason=>`<option value="${esc(reason)}">${esc(reason)}</option>`).join('')}</select></label><div id="other-return-reason-field" hidden><label>Other return reason<input name="other_reason" type="text" maxlength="180" placeholder="Explain why the customer is returning these goods" disabled></label></div><p class="hint">Credit uses the original selling price. Leave quantities at zero for items not being returned. Uncheck Resellable for damaged or defective goods that cannot be sold again. The reason does not change this checkbox automatically. Do not also make a manual stock adjustment for this return.</p><button ${lines.length?'':'disabled'}>Receive return & update stock</button><p id="return-error" role="alert" class="error-text"></p></form>`;
    applyPermissions();
    let key=crypto.randomUUID();
    const form=$('#receive-return');
    const otherReason=form.elements.other_reason;
    form.elements.reason.onchange=()=>{
      key=crypto.randomUUID();const other=form.elements.reason.value==='Other reason';
      $('#other-return-reason-field').hidden=!other;otherReason.disabled=!other;otherReason.required=other;otherReason.setCustomValidity('');
    };
    otherReason.oninput=()=>otherReason.setCustomValidity('');
    form.oninput=()=>{key=crypto.randomUUID();};
    form.onsubmit=async e=>{
      e.preventDefault();const b=form.querySelector('button');b.disabled=true;
      try{
        if($('#return-invoice').value!==String(id))throw Error('The selected invoice changed. Load its items before saving.');
        const selected=[...form.querySelectorAll('[data-return-line]')].filter(i=>Number(i.value)>0).map(i=>({document_line_id:Number(i.dataset.returnLine),quantity:i.value,restock:form.querySelector(`[data-restock-line="${i.dataset.returnLine}"]`).checked}));
        if(!selected.length)throw Error('Enter a return quantity for at least one item.');
        let reason=form.elements.reason.value;
        if(!customerReturnReasons.includes(reason))throw Error('Choose a return reason.');
        if(reason==='Other reason'){
          const detail=otherReason.value.trim();
          if(!detail){otherReason.setCustomValidity('Enter the other return reason.');otherReason.reportValidity();return;}
          reason+=': '+detail;
        }
        const result=await api('/documents/'+id+'/returns',{reason,lines:selected,request_key:key});
        await load();message(returnNumber(result.id)+' saved. Stock and customer balance updated.');await openReturn(result.id);
      }catch(err){$('#return-error').textContent=err.message;}finally{b.disabled=false;}
    };
  }catch(e){message(e.message,true);}
}
async function openReturn(id){
  try{
    const r=await api('/returns/'+id);
    $('#detail-body').innerHTML=`<div class="doc-head"><div class="eyebrow">${esc(business)} · CUSTOMER RETURN</div><h2>${returnNumber(r.id)}</h2><p>${esc(r.customer_name)} · Invoice INV-${String(r.document_id).padStart(6,'0')}</p><small>${new Date(r.created_at).toLocaleString()}</small></div>${table(['Product / batch','Received','Stock handling','Credit'],r.lines.map(l=>`<tr><td>${esc(l.description)}</td><td>${qty(l.quantity)} ${esc(l.unit)}</td><td>${l.restock?(r.reversed_at?'Restock reversed':'Added to original batch'):'Damaged / not restocked'}</td><td>${cash(l.amount)}</td></tr>`))}<div class="total">${r.reversed_at?'Original return credit':'Return credit'} ${cash(r.total)}</div><p class="notes">${esc(r.reason)}</p><p class="hint">${r.reversed_at?'REVERSED on '+new Date(r.reversed_at).toLocaleString()+' by owner #'+r.reversed_by+'. Reason: '+esc(r.reversal_reason)+'. Original quantities and credit are retained for history; they no longer affect stock or balances.':'Active return. Stock was added only for resellable items; refunds are recorded separately.'}</p>${!r.reversed_at&&currentUser.role==='owner'?'<button id="reverse-this-return" class="danger">Reverse return</button>':''}<button id="return-original-invoice">Open original invoice / record refund</button>`;
    $('#return-original-invoice').onclick=()=>openDocument(r.document_id);
    if($('#reverse-this-return'))$('#reverse-this-return').onclick=()=>showReversal('returns',r.id,()=>openReturn(r.id));
    $('#print').hidden=true;
    if(!$('#detail').open)$('#detail').showModal();applyPermissions();
  }catch(e){message(e.message,true);}
}
function augmentInvoice(d){
  if(d.kind!=='invoice')return;
  const section=document.createElement('section');
  section.className='panel';
  section.innerHTML=`<h3>Returns & refunds</h3><p>Return credit: <b>${cash(d.returned)}</b> · Net invoice: <b>${cash(d.net_total)}</b><br>Refunds paid: <b>${cash(d.refunded)}</b> · Amount due: <b>${cash(d.due)}</b> · Customer credit / refund due: <b>${cash(d.refund_due)}</b></p><p class="hint">A negative invoice balance means money is owed back to the customer. Credit stays on this invoice until refunded; automatic transfer to another invoice is not supported.</p>${table(['Return','Date','Reason / correction','Original credit','Status',''],(d.returns||[]).map(r=>`<tr><td>${returnNumber(r.id)}</td><td>${new Date(r.created_at).toLocaleString()}</td><td>${esc(r.reversed_at?r.reversal_reason:r.reason)}</td><td>${cash(r.total)}</td><td>${r.reversed_at?'Reversed':'Active'}</td><td><button class="secondary" data-invoice-return="${r.id}">View</button></td></tr>`))}${table(['Refund','Date','Method','Reference / correction','Original amount','Status',''],(d.refunds||[]).map(r=>`<tr><td>#${r.id}</td><td>${new Date(r.created_at).toLocaleString()}</td><td>${esc(r.method)}</td><td>${esc(r.reversed_at?r.reversal_reason:r.reference)}</td><td>${cash(r.amount)}</td><td>${r.reversed_at?'Reversed':'Active'}</td><td>${!r.reversed_at&&currentUser.role==='owner'?'<button class="danger" data-reverse-refund="'+r.id+'">Reverse refund</button>':''}</td></tr>`))}${d.status==='posted'?'<button id="start-customer-return" class="secondary">Receive customer return</button>':''}${d.status==='posted'&&Number(d.refund_due)>0?`<form id="refund-form" class="pay-form"><h3>Record money refunded</h3><p class="hint">This records a refund already given to the customer. It does not transfer money automatically.</p><div class="fields">${field('Refund amount','amount','number',`min="0.01" max="${esc(d.refund_due)}" step="0.01" required`)}<label>Refund method<select name="method"><option>cash</option><option>bank</option><option>upi</option><option>card</option><option>other</option></select></label>${field('Refund reference','reference','text','maxlength="200"')}</div><button>Save refund record</button><p id="refund-error" role="alert" class="error-text"></p></form>`:''}`;
  $('#detail-body').append(section);
  section.querySelectorAll('[data-invoice-return]').forEach(b=>b.onclick=()=>openReturn(b.dataset.invoiceReturn));
  section.querySelectorAll('[data-reverse-refund]').forEach(b=>b.onclick=()=>showReversal('refunds',b.dataset.reverseRefund,()=>openDocument(d.id)));
  if($('#start-customer-return'))$('#start-customer-return').onclick=async()=>{
    $('#detail').close();page='returns';render();$('#return-invoice').value=String(d.id);await loadReturnItems(d.id);
  };
  if($('#refund-form')){
    const form=$('#refund-form');let key=crypto.randomUUID();form.oninput=()=>{key=crypto.randomUUID();};
    form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('button');b.disabled=true;try{await api('/documents/'+d.id+'/refunds',{...Object.fromEntries(new FormData(form)),request_key:key});await load();await openDocument(d.id);message('Refund recorded.');}catch(err){$('#refund-error').textContent=err.message;}finally{b.disabled=false;}};
  }
}

function mountReturnCustomerBrowser(picker){
  const panel=$('#return-customer-browser');
  let offset=0;const size=25;
  const open=()=>{
    panel.hidden=false;offset=0;
    panel.innerHTML='<div class="toolbar"><h3>All customers</h3><button type="button" id="close-return-customers" class="secondary">Close customer list</button></div><label>Filter customer list by name or mobile<input id="return-customer-list-search" type="search" maxlength="200" placeholder="Name or mobile number"></label><div id="return-customer-list-rows"></div><div id="return-customer-list-pages" class="actions"></div>';
    const draw=()=>{
      const term=$('#return-customer-list-search').value.trim().toLowerCase(),digits=term.replace(/\D/g,'');
      const rows=state.customers.filter(c=>!term||c.name.toLowerCase().includes(term)||c.phone.toLowerCase().includes(term)||(digits&&c.phone.replace(/\D/g,'').includes(digits)));
      offset=Math.min(offset,Math.max(0,Math.floor((rows.length-1)/size)*size));
      $('#return-customer-list-rows').innerHTML=table(['Customer','Mobile','Address','Posted invoices',''],rows.slice(offset,offset+size).map(c=>`<tr><td>${esc(c.name)}<br><small>Customer #${c.id}</small></td><td>${esc(c.phone||'—')}</td><td>${esc(c.address)}</td><td>${state.documents.filter(d=>d.customer_id===c.id&&d.kind==='invoice'&&d.status==='posted').length}</td><td><button type="button" class="secondary" data-return-choose-customer="${c.id}">Choose customer</button></td></tr>`));
      $('#return-customer-list-pages').innerHTML=`<span class="hint">${rows.length?'Showing '+(offset+1)+'–'+Math.min(offset+size,rows.length)+' of '+rows.length+' customers':'No matching customers'}</span><button type="button" id="return-customers-prev" class="secondary" ${offset===0?'disabled':''}>Previous</button><button type="button" id="return-customers-next" class="secondary" ${offset+size>=rows.length?'disabled':''}>Next</button>`;
      panel.querySelectorAll('[data-return-choose-customer]').forEach(b=>b.onclick=()=>{const customer=state.customers.find(c=>c.id===Number(b.dataset.returnChooseCustomer));if(customer){picker.choose(customer);panel.hidden=true;}});
      $('#return-customers-prev').onclick=()=>{offset-=size;draw();};$('#return-customers-next').onclick=()=>{offset+=size;draw();};
    };
    $('#return-customer-list-search').oninput=()=>{offset=0;draw();};$('#close-return-customers').onclick=()=>{panel.hidden=true;};draw();
  };
  $('#return-customer-search').addEventListener('input',()=>{panel.hidden=true;});
  return open;
}
