'use strict';
let selectedStockSeverity=null;
const stockLabels={out_of_stock:'Out of stock',critical:'Critical',warning:'Warning',notice:'Notice',healthy:'Healthy',disabled:'Disabled'};
function severityBadge(value){return `<span class="stock-badge stock-${esc(value)}">${esc(stockLabels[value]||value)}</span>`;}
function stockPolicyFields(){return `<label>Product criticality<select name="criticality"><option value="high">High — essential / urgent</option><option value="medium" selected>Medium — standard</option><option value="low">Low — less urgent</option></select></label>${field('Minimum stock (stock units)','minimum_stock','number','min="0" step="0.001" value="0" required')}${field('Critical stock (stock units)','critical_stock','number','min="0" step="0.001" value="0" required')}<label class="restock-label"><input type="checkbox" name="stock_alerts_enabled" checked> Enable stock alerts</label>`;}
function stockSummary(){const s=state.stockAlerts.summary;return `<div class="stock-summary">${['out_of_stock','critical','warning','notice'].map(value=>`<button type="button" class="stock-summary-button" data-alert-severity="${value}" aria-pressed="${page==='alerts'&&selectedStockSeverity===value}">${severityBadge(value)} <b>${s[value]}</b></button>`).join('')}</div>`;}
function stockAlertsTable(limit){const rows=state.stockAlerts.alerts.filter(p=>page!=='alerts'||!selectedStockSeverity||p.severity===selectedStockSeverity);return rows.length?table(['Urgency','Product','Criticality','Available','Minimum','Critical level','Why'],rows.slice(0,limit??rows.length).map(p=>`<tr><td><button type="button" class="stock-badge stock-${esc(p.severity)}" data-alert-product="${p.id}" aria-label="Open ${esc(p.name)} — ${esc(stockLabels[p.severity])}">${esc(stockLabels[p.severity])}</button></td><td><button type="button" class="product-link" data-alert-product="${p.id}">${esc(p.sku)} · ${esc(p.name)}</button></td><td>${esc(p.criticality)}</td><td><b>${qty(p.available)} ${esc(p.unit)}</b></td><td>${qty(p.minimum_stock)}</td><td>${qty(p.critical_stock)}</td><td>${esc(p.message)}</td></tr>`)):`<p class="hint">${selectedStockSeverity&&page==='alerts'?'No '+esc(stockLabels[selectedStockSeverity])+' products right now.':'No active stock alerts.'}</p>`;}
function stockDashboard(){return `<div class="panel" id="stock-alert-panel"><div class="toolbar"><h2>Stock alerts</h2><button type="button" class="secondary" id="manage-stock-alerts">Manage stock levels</button></div><div id="stock-summary">${stockSummary()}</div><div id="stock-alert-list">${stockAlertsTable(6)}</div><p class="hint">${state.stockAlerts.summary.total>6?'Showing the six most urgent alerts. ':''}Total sellable stock across batches. Checks refresh every 30 seconds while this page is visible.</p></div>`;}
function updateStockBadge(){const b=document.querySelector('nav [data-page="alerts"]');if(b)b.textContent='Stock alerts'+(state.stockAlerts.summary.total?' ('+state.stockAlerts.summary.total+')':'');}
function mountStockAlerts(){
  updateStockBadge();
  if(page==='overview'||page==='inventory'){
    const panel=document.createElement('div');panel.innerHTML=stockDashboard();
    const target=page==='overview'?$('#content .cards'):null;
    if(target)target.after(panel);else $('#content').prepend(panel);
    $('#manage-stock-alerts').onclick=()=>{page='alerts';render();};
  }
  if(page==='products'){
    const note=document.createElement('p');note.className='hint';note.innerHTML='Need to change alert levels for an existing product? <button type="button" class="secondary" id="existing-stock-policy">Manage stock levels</button>';
    $('#product').append(note);$('#existing-stock-policy').onclick=()=>{page='alerts';render();};
  }
  if(page==='alerts')renderStockAlerts();
}
function renderStockAlerts(){
  $('#content').innerHTML=`<div class="panel"><div class="toolbar"><h2>Stock alerts by urgency</h2><button type="button" class="secondary" data-clear-alert-filter>Show all alerts</button></div><p id="stock-alert-filter" class="hint">${selectedStockSeverity?esc(stockLabels[selectedStockSeverity])+' products':'All alert priorities'}</p><div id="stock-summary">${stockSummary()}</div><div id="stock-alert-list">${stockAlertsTable()}</div><p class="hint">Out of stock comes first. At the minimum: High criticality gives a Critical alert, Medium gives a Warning, Low gives a Notice. At or below the critical level, every product gives a Critical alert. Thresholds include equality; disabled products do not alert. Counts refresh every 30 seconds on a visible page.</p></div><form id="stock-policy-form" class="panel"><h2>Set product stock levels</h2><label>Product to configure<select name="product_id" required>${options(state.products,p=>p.sku+' · '+p.name)}</select></label><div class="fields">${stockPolicyFields()}</div><p class="hint" id="stock-policy-unit">Use the product's stock unit. Critical stock must not exceed minimum stock. A zero minimum monitors only out-of-stock status.</p><button>Save stock levels</button></form><div class="panel"><h2>All product stock levels</h2><div id="stock-policy-list"></div></div>`;
  refreshPolicyList();
  const form=$('#stock-policy-form');
  const select=form.elements.product_id;
  select.onchange=()=>fillStockPolicy(select.value);
  form.onsubmit=async e=>{
    e.preventDefault();const b=form.querySelector('button');b.disabled=true;
    try{const data=Object.fromEntries(new FormData(form));const id=data.product_id;delete data.product_id;data.stock_alerts_enabled=form.elements.stock_alerts_enabled.checked;await api('/products/'+id+'/stock-policy',data);await load();fillStockPolicy(id);message('Stock levels saved. Alerts updated.');}catch(err){message(err.message,true);}finally{b.disabled=false;}
  };
}
function fillStockPolicy(id){
  const p=state.stockAlerts.products.find(p=>p.id==id);if(!p)return;
  const f=$('#stock-policy-form');f.elements.product_id.value=String(id);
  for(const key of ['criticality','minimum_stock','critical_stock'])f.elements[key].value=p[key];
  f.elements.stock_alerts_enabled.checked=p.stock_alerts_enabled;
  $('#stock-policy-unit').textContent='Quantities for '+p.name+' are in '+p.unit+'. Critical stock must not exceed minimum stock. A zero minimum monitors only out-of-stock status.';
}
function refreshPolicyList(){
  const el=$('#stock-policy-list');if(!el)return;
  el.innerHTML=table(['Product','Available','Criticality','Minimum','Critical level','Status',''],state.stockAlerts.products.map(p=>`<tr><td>${esc(p.sku)} · ${esc(p.name)}</td><td>${qty(p.available)} ${esc(p.unit)}</td><td>${esc(p.criticality)}</td><td>${qty(p.minimum_stock)}</td><td>${qty(p.critical_stock)}</td><td><button type="button" class="stock-badge stock-${esc(p.severity)}" data-alert-product="${p.id}">${esc(stockLabels[p.severity])}</button></td><td><button type="button" class="secondary" data-policy="${p.id}">Configure</button></td></tr>`));
  el.querySelectorAll('[data-policy]').forEach(b=>b.onclick=()=>{fillStockPolicy(b.dataset.policy);$('#stock-policy-form').scrollIntoView({behavior:'smooth'});});
}
let stockRefreshRunning=false;
async function pollStockAlerts(){
  if(!currentUser||currentUser.force_password_change||document.hidden||stockRefreshRunning)return;
  stockRefreshRunning=true;
  try{
    state.stockAlerts=await api('/stock-alerts',undefined,true);updateStockBadge();
    if($('#stock-summary'))$('#stock-summary').innerHTML=stockSummary();
    if($('#stock-alert-list'))$('#stock-alert-list').innerHTML=stockAlertsTable(page==='alerts'?undefined:6);
    refreshPolicyList();
  }catch(e){message('Stock alerts could not refresh: '+e.message,true);}finally{stockRefreshRunning=false;}
}
setInterval(pollStockAlerts,30000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollStockAlerts();});

document.addEventListener('click',event=>{
  const product=event.target.closest('[data-alert-product]');
  if(product){openStockProduct(Number(product.dataset.alertProduct));return;}
  const severity=event.target.closest('[data-alert-severity]');
  if(severity){
    selectedStockSeverity=severity.dataset.alertSeverity;
    const matches=state.stockAlerts.alerts.filter(p=>p.severity===selectedStockSeverity);
    if(matches.length===1){openStockProduct(matches[0].id);return;}
    page='alerts';render();return;
  }
  if(event.target.closest('[data-clear-alert-filter]')){selectedStockSeverity=null;page='alerts';render();}
});
async function openStockProduct(id){
  try{
    const [products,batches,alerts]=await Promise.all([api('/products'),api('/batches'),api('/stock-alerts')]);
    state.products=products;state.batches=batches;state.stockAlerts=alerts;
    const p=products.find(p=>p.id===id);if(!p)throw Error('Product not found. Refresh the page.');
    const status=alerts.products.find(p=>p.id===id);
    const lots=batches.filter(b=>b.product_id===id);
    $('#detail-body').innerHTML=`<div class="doc-head"><div class="eyebrow">PRODUCT STOCK DETAILS</div><h2>${esc(p.name)}</h2><p>${esc(p.sku)} · ${severityBadge(status?.severity||'healthy')}</p></div><div class="fields"><p><b>Available:</b> ${qty(status?.available||0)} ${esc(p.unit)}</p><p><b>Price:</b> ${cash(p.sale_price)} / ${esc(p.unit)}</p><p><b>Criticality:</b> ${esc(p.criticality)}</p><p><b>Minimum:</b> ${qty(p.minimum_stock)} · <b>Critical level:</b> ${qty(p.critical_stock)} ${esc(p.unit)}</p><p><b>Brand:</b> ${esc(p.brand)} · <b>Pack:</b> ${esc(p.pack)} · <b>Grade:</b> ${esc(p.grade)}</p></div><h3>Batches</h3>${table(['Batch','Colour','Shade / size','Available',''],lots.map(b=>`<tr><td>${esc(b.code)}</td><td>${esc(b.colour)}</td><td>${esc(b.shade)} / ${esc(b.size)}</td><td>${qty(b.quantity)} ${esc(b.unit)}</td><td><button type="button" class="secondary" data-product-stock="${b.id}">Add stock</button></td></tr>`))}<button type="button" id="product-manage-levels" class="secondary">Manage this product's stock levels</button>`;
    $('#print').hidden=true;
    $('#detail-body').querySelectorAll('[data-product-stock]').forEach(button=>button.onclick=()=>{
      $('#detail').close();page='inventory';render();const form=$('#adjust');form.elements.batch_id.value=button.dataset.productStock;form.elements.batch_id.dispatchEvent(new Event('change'));form.scrollIntoView({behavior:'smooth'});form.elements.delta.focus();
    });
    $('#product-manage-levels').onclick=()=>{$('#detail').close();page='alerts';render();fillStockPolicy(id);$('#stock-policy-form').scrollIntoView({behavior:'smooth'});};
    if(!$('#detail').open)$('#detail').showModal();applyPermissions();
  }catch(error){message(error.message,true);}
}
