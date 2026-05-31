const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');
const cors = require('cors');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.static('.'));

// Initialize SQLite database
const dbPath = path.join(__dirname, 'usecases.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('❌ Database connection error:', err);
  } else {
    console.log('✅ Connected to SQLite database at', dbPath);
    initializeDB();
  }
});

function initializeDB() {
  db.run(`
    CREATE TABLE IF NOT EXISTS usecases (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      businessUnit TEXT NOT NULL,
      name TEXT NOT NULL,
      description TEXT NOT NULL,
      priority TEXT NOT NULL,
      owner TEXT,
      status TEXT,
      output TEXT,
      isPersonal INTEGER DEFAULT 0,
      createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
      updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
    )
  `, (err) => {
    if (err) {
      console.error('Table creation error:', err);
    } else {
      console.log('✅ Database table ready');
      seedDB();
    }
  });
}

// Seed the recovered baseline use cases from seed-data.json.
// Render free tier has an ephemeral filesystem, so the SQLite file is wiped
// on every restart/spin-down. Re-seeding from the committed file on each boot
// guarantees the baseline list of use cases always survives.
function seedDB() {
  const seedPath = path.join(__dirname, 'seed-data.json');
  if (!fs.existsSync(seedPath)) {
    console.log('ℹ️  No seed-data.json found, skipping seed.');
    return;
  }

  let seed;
  try {
    seed = JSON.parse(fs.readFileSync(seedPath, 'utf8'));
  } catch (e) {
    console.error('Seed parse error:', e.message);
    return;
  }

  const stmt = db.prepare(
    `INSERT OR IGNORE INTO usecases (id, businessUnit, name, description, priority, owner, status, output, isPersonal)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  );
  seed.forEach(u => {
    stmt.run([
      u.id, u.businessUnit, u.name, u.description, u.priority,
      u.owner || null, u.status || 'Planned', u.output || '', u.isPersonal ? 1 : 0
    ]);
  });
  stmt.finalize(err => {
    if (err) console.error('Seed error:', err.message);
    else console.log(`✅ Seed complete: ensured ${seed.length} baseline use cases`);
  });
}

// API Routes

// GET all use cases
app.get('/api/usecases', (req, res) => {
  db.all(`SELECT * FROM usecases ORDER BY createdAt DESC`, (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows || []);
  });
});

// POST new use case
app.post('/api/usecases', (req, res) => {
  const { businessUnit, name, description, priority, owner, status, output, isPersonal } = req.body;

  if (!businessUnit || !name || !description || !priority) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  db.run(
    `INSERT INTO usecases (businessUnit, name, description, priority, owner, status, output, isPersonal)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    [businessUnit, name, description, priority, owner || null, status || 'Planned', output || null, isPersonal ? 1 : 0],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ id: this.lastID, message: 'Use case created' });
    }
  );
});

// PUT update use case
app.put('/api/usecases/:id', (req, res) => {
  const { businessUnit, name, description, priority, owner, status, output, isPersonal } = req.body;

  db.run(
    `UPDATE usecases
     SET businessUnit=?, name=?, description=?, priority=?, owner=?, status=?, output=?, isPersonal=?, updatedAt=CURRENT_TIMESTAMP
     WHERE id=?`,
    [businessUnit, name, description, priority, owner, status, output, isPersonal ? 1 : 0, req.params.id],
    function(err) {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ message: 'Use case updated' });
    }
  );
});

// DELETE use case
app.delete('/api/usecases/:id', (req, res) => {
  db.run(`DELETE FROM usecases WHERE id=?`, [req.params.id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ message: 'Use case deleted' });
  });
});

// Export as CSV
app.get('/api/export-csv', (req, res) => {
  db.all(`SELECT * FROM usecases ORDER BY businessUnit, priority`, (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });

    if (!rows || rows.length === 0) {
      return res.json({ csv: 'No data to export' });
    }

    const headers = Object.keys(rows[0]);
    const csv = [headers.join(','), ...rows.map(r => headers.map(h => `"${r[h] || ''}"`).join(','))].join('\n');

    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', 'attachment; filename=usecases.csv');
    res.send(csv);
  });
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', database: 'connected' });
});

app.listen(PORT, () => {
  console.log(`\n🚀 Server running on http://localhost:${PORT}`);
  console.log(`📊 Database: usecases.db`);
  console.log(`\nAPI Endpoints:`);
  console.log(`  GET    /api/usecases       - Fetch all use cases`);
  console.log(`  POST   /api/usecases       - Create use case`);
  console.log(`  PUT    /api/usecases/:id   - Update use case`);
  console.log(`  DELETE /api/usecases/:id   - Delete use case`);
  console.log(`  GET    /api/export-csv     - Export as CSV\n`);
});

process.on('SIGINT', () => {
  db.close();
  process.exit(0);
});
