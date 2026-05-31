// One-off: parse the recovered CSV into seed-data.json
const fs = require('fs');
const path = require('path');

const csvPath = process.argv[2] || '/Users/arvind/Downloads/bhookle-ai-usecases.csv';
const raw = fs.readFileSync(csvPath, 'utf8');

// RFC-4180-ish CSV parser supporting quoted fields, escaped quotes, and embedded newlines.
function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else { inQuotes = false; }
      } else {
        field += c;
      }
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\r') { /* ignore */ }
      else if (c === '\n') { row.push(field); rows.push(row); row = []; field = ''; }
      else field += c;
    }
  }
  if (field.length > 0 || row.length > 0) { row.push(field); rows.push(row); }
  return rows;
}

const rows = parseCSV(raw).filter(r => r.length > 1 && r.some(c => c.trim() !== ''));
const header = rows.shift();

const usecases = rows.map(r => {
  const id = parseInt(r[0], 10);
  const businessUnit = (r[1] || '').trim();
  const name = (r[2] || '').trim();
  const description = (r[3] || '').trim();
  const priority = (r[4] || '').trim();
  const owner = (r[5] || '').trim();
  return {
    id,
    businessUnit,
    name,
    description,
    priority,
    owner,
    status: 'Planned',
    output: '',
    isPersonal: businessUnit.toLowerCase() === 'personal' ? 1 : 0
  };
}).filter(u => u.id && u.name);

const outPath = path.join(__dirname, 'seed-data.json');
fs.writeFileSync(outPath, JSON.stringify(usecases, null, 2));
console.log(`✅ Parsed ${usecases.length} use cases → ${outPath}`);
console.log(usecases.map(u => `  ${u.id}. [${u.businessUnit}] ${u.name}`).join('\n'));
