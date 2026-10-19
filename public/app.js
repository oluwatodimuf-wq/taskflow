'use strict';
let config, records = [], editing = null;
const $ = id => document.getElementById(id);
const money = value => new Intl.NumberFormat('en-NG', {style:'currency', currency:'NGN'}).format(value / 100);
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notice(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; }
async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || 'Request failed.');
  return body;
}
function stats() {
  let values;
  if (config.slug === 'taskflow') {
    const done = records.filter(r => r.status === 'Done').length;
    values = [['Total tasks', records.length], ['In progress', records.filter(r => r.status === 'In progress').length], ['Completed', records.length ? Math.round(done / records.length * 100) + '%' : '0%']];
  } else if (config.slug === 'pocketledger') {
    const income = records.filter(r => r.kind === 'Income').reduce((s,r) => s+r.amount,0);
    const expense = records.filter(r => r.kind === 'Expense').reduce((s,r) => s+r.amount,0);
    values = [['Net balance', money(income-expense)], ['Income', money(income)], ['Expenses', money(expense)]];
  } else {
    values = [['Stock value', money(records.reduce((s,r) => s+r.price*r.quantity,0))], ['Products', records.length], ['Low stock', records.filter(r => r.quantity <= r.reorder_level).length]];
  }
  $('stats').replaceChildren(...values.map(([label,value]) => {
    const card = element('div', undefined, 'stat'); card.append(element('p',label),element('strong',value)); return card;
  }));
}
function render() {
  const query = $('search').value.toLowerCase().trim(), filter = $('filter').value;
  const filterField = config.fields.find(f => f.type === 'select');
  const visible = records.filter(r => config.fields.some(f => String(r[f.name]).toLowerCase().includes(query)) && (!filter || r[filterField.name] === filter));
  $('rows').replaceChildren(...visible.map(record => {
    const row = element('tr');
    config.fields.forEach(f => row.append(element('td',f.type === 'money' ? money(record[f.name]) : record[f.name])));
    const actions = element('td',undefined,'actions');
    const edit = element('button','Edit'), remove = element('button','Delete');
    const name = String(record[config.fields[0].name]);
    edit.setAttribute('aria-label','Edit '+name); remove.setAttribute('aria-label','Delete '+name);
    edit.onclick = () => startEdit(record);
    remove.onclick = async () => {
      if (!confirm('Delete “'+name+'”?')) return;
      remove.disabled = true;
      try { await api('/api/records/'+record.id,{method:'DELETE'}); if (editing === record.id) reset(); await refresh(); notice('Record deleted.'); }
      catch(error) { notice(error.message,true); }
      finally { remove.disabled = false; }
    };
    actions.append(edit,remove); row.append(actions); return row;
  }));
  $('empty').hidden = visible.length > 0;
  $('empty').textContent = records.length ? 'No matching records. Try another search or filter.' : 'No records yet. Add your first one to get started.';
  $('count').textContent = visible.length + ' OF ' + records.length;
  stats();
}
async function refresh() { records = await api('/api/records'); render(); }
function reset() {
  editing = null; $('record-form').reset(); $('form-title').textContent = 'New '+config.noun; $('cancel').hidden = true;
}
function startEdit(record) {
  editing = record.id;
  config.fields.forEach(f => { $('field-'+f.name).value = f.type === 'money' ? (record[f.name]/100).toFixed(2) : record[f.name]; });
  $('form-title').textContent = 'Edit '+config.noun; $('cancel').hidden = false;
  $('form-title').scrollIntoView({behavior:'smooth',block:'center'}); $('field-'+config.fields[0].name).focus();
}
async function boot() {
  try {
    config = await api('/api/config');
    document.documentElement.style.setProperty('--accent',config.color);
    config.fields.forEach(f => {
      const label = element('label',f.label), input = element(f.type === 'select' ? 'select' : 'input');
      input.id = 'field-'+f.name; input.name = f.name; input.required = true; label.htmlFor = input.id;
      if (f.type === 'select') f.options.forEach(option => { const o = element('option',option); o.value=option; input.append(o); });
      else { input.type = ['integer','money'].includes(f.type) ? 'number' : f.type; if (f.max) input.maxLength=f.max; }
      if (['integer','money'].includes(f.type)) { input.min=f.type==='money'?'0.01':'0'; input.max='999999999'; input.step=f.type==='money'?'0.01':'1'; }
      label.append(input); $('fields').append(label);
    });
    const filterField = config.fields.find(f => f.type === 'select');
    filterField.options.forEach(option => { const o=element('option',option); o.value=option; $('filter').append(o); });
    const heading = element('tr'); config.fields.forEach(f => heading.append(element('th',f.label))); heading.append(element('th','Actions')); $('head').append(heading);
    $('record-form').onsubmit = async event => {
      event.preventDefault(); const payload={}; config.fields.forEach(f => payload[f.name]=$('field-'+f.name).value);
      $('save').disabled=true;
      try { await api('/api/records'+(editing ? '/'+editing : ''), {method:editing?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); reset(); await refresh(); notice('Saved successfully.'); }
      catch(error) { notice(error.message,true); }
      finally { $('save').disabled=false; }
    };
    $('cancel').onclick=reset; $('search').oninput=render; $('filter').onchange=render;
    await refresh();
  } catch(error) { notice('Could not load workspace: '+error.message+'. Refresh to retry.',true); }
}
boot();
