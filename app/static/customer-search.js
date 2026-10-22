'use strict';
function customerPicker(prefix="customer"){return `<div class="customer-picker"><label for="${prefix}-search">Customer — search by name or mobile number</label><input id="${prefix}-search" type="text" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="${prefix}-results" aria-describedby="${prefix}-search-status" placeholder="Type a name or mobile number…" maxlength="200" autocomplete="off" required><input type="hidden" name="customer_id" id="selected-${prefix}-id"><div id="${prefix}-search-status" class="hint" role="status" aria-live="polite">Type to find a customer, then select a match.</div><div id="${prefix}-results" role="listbox" aria-label="Matching customers" hidden></div><div id="${prefix}-selected" class="hint"></div></div>`;}
function bindCustomerPicker(prefix="customer"){
  const input=$('#'+prefix+'-search'),hidden=$('#selected-'+prefix+'-id'),results=$('#'+prefix+'-results'),status=$('#'+prefix+'-search-status'),selected=$('#'+prefix+'-selected');
  let timer,sequence=0,controller,matches=[],active=-1;
  const close=()=>{results.hidden=true;input.setAttribute('aria-expanded','false');input.removeAttribute('aria-activedescendant');active=-1;};
  const choose=customer=>{
    sequence++;controller?.abort();clearTimeout(timer);
    input.value=customer.name+(customer.phone?' · '+customer.phone:'');hidden.value=customer.id;
    input.setCustomValidity('');status.textContent='Customer selected.';
    selected.textContent=(customer.phone?'Mobile: '+customer.phone:'No mobile number recorded')+(customer.address?' · '+customer.address:'')+' · Customer #'+customer.id;
    close();input.focus();input.dispatchEvent(new Event('change',{bubbles:true}));
  };
  const highlight=index=>{
    active=index;
    results.querySelectorAll('[role=option]').forEach((el,i)=>{el.setAttribute('aria-selected',String(i===active));if(i===active){input.setAttribute('aria-activedescendant',el.id);el.scrollIntoView({block:'nearest'});}});
  };
  const search=async(term,request)=>{
    controller?.abort();controller=new AbortController();
    try{
      const response=await fetch('/api/customers/search?q='+encodeURIComponent(term),{signal:controller.signal});
      if(!response.ok)throw Error('Customer search unavailable. Please try again.');
      const data=await response.json();
      if(request!==sequence||!input.isConnected)return;
      matches=data.items;active=-1;
      results.innerHTML=matches.map((customer,i)=>`<div id="${prefix}-result-${i}" role="option" aria-selected="false" data-customer-result="${i}" tabindex="-1"><strong>${esc(customer.name)}</strong><span>${esc(customer.phone||'No mobile number')} · Customer #${customer.id}</span>${customer.address?`<small>${esc(customer.address)}</small>`:''}</div>`).join('');
      status.textContent=matches.length?(data.has_more?'Showing first 20 matches. Type more to narrow the search.':matches.length+' match'+(matches.length===1?'':'es')+'. Select the correct customer.'):'No matching customers. Add the customer on the Customers page first.';
      results.hidden=!matches.length||document.activeElement!==input;input.setAttribute('aria-expanded',String(!results.hidden));
      results.querySelectorAll('[data-customer-result]').forEach(el=>{el.addEventListener('mousedown',event=>event.preventDefault());el.addEventListener('click',()=>choose(matches[Number(el.dataset.customerResult)]));});
    }catch(error){if(error.name!=='AbortError'&&request===sequence&&input.isConnected){matches=[];close();status.textContent=error.message;}}
  };
  input.addEventListener('input',()=>{
    sequence++;clearTimeout(timer);controller?.abort();hidden.value='';selected.textContent='';matches=[];close();
    const term=input.value.trim();input.setCustomValidity(term?'Select a customer from the matching results.':'');
    if(!term){status.textContent='Type to find a customer, then select a match.';return;}
    status.textContent='Searching…';const request=sequence;timer=setTimeout(()=>search(term,request),200);
  });
  input.addEventListener('keydown',event=>{
    if(event.key==='Escape'){sequence++;controller?.abort();clearTimeout(timer);close();return;}
    if(results.hidden||!matches.length)return;
    if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();highlight(active<0?(event.key==='ArrowDown'?0:matches.length-1):(active+(event.key==='ArrowDown'?1:-1)+matches.length)%matches.length);}
    if(event.key==='Enter'){event.preventDefault();choose(matches[active<0?0:active]);}
  });
  input.addEventListener('blur',()=>{setTimeout(()=>{if(input.isConnected)close();},120);});
  input.addEventListener('focus',()=>{if(matches.length&&!hidden.value){results.hidden=false;input.setAttribute('aria-expanded','true');}});
  input.form.addEventListener('submit',event=>{if(!hidden.value){event.preventDefault();event.stopImmediatePropagation();input.setCustomValidity('Search and select a customer before saving.');input.reportValidity();}},{capture:true});
  return {choose};
}
