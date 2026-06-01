const express = require('express');
const path = require('path');
const fs = require('fs');
const cors = require('cors');
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json());

// Serve the frontend from this same server (single origin, no separate CDN).
// HTML is served with no-cache headers so app updates always show immediately
// and we never get the stale-cache problems a CDN can cause.
app.get(['/', '/index.html', '/app'], (req, res) => {
  res.set('Cache-Control', 'no-cache, no-store, must-revalidate');
  res.set('Pragma', 'no-cache');
  res.set('Expires', '0');
  res.sendFile(path.join(__dirname, 'index.html'));
});

// ─── PostgreSQL connection ───────────────────────────────────────────────
// DATABASE_URL is provided by Render (linked Postgres instance).
if (!process.env.DATABASE_URL) {
  console.warn('⚠️  DATABASE_URL is not set. Set it to your Render Postgres connection string.');
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  // Render Postgres requires SSL for external connections; harmless for internal.
  ssl: process.env.DATABASE_URL ? { rejectUnauthorized: false } : false,
  max: 5,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
});

pool.on('error', (err) => console.error('Unexpected PG pool error:', err.message));

// ─── Schema + one-time seed ──────────────────────────────────────────────
async function initializeDB() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS usecases (
      id            SERIAL PRIMARY KEY,
      "businessUnit" TEXT NOT NULL,
      name          TEXT NOT NULL,
      description   TEXT NOT NULL,
      priority      TEXT NOT NULL,
      owner         TEXT,
      status        TEXT,
      output        TEXT,
      "isPersonal"  INTEGER DEFAULT 0,
      "createdAt"   TIMESTAMPTZ DEFAULT NOW(),
      "updatedAt"   TIMESTAMPTZ DEFAULT NOW()
    )
  `);
  console.log('✅ Postgres table ready');
  await seedIfEmpty();
}

// Seed the recovered 45 ONLY when the table is empty (first boot on a fresh DB).
// Because Postgres persists, we never re-seed after that — so any edits, new
// additions, or deletions you make are permanent and never get overwritten.
async function seedIfEmpty() {
  const { rows } = await pool.query('SELECT COUNT(*)::int AS c FROM usecases');
  if (rows[0].c > 0) {
    console.log(`ℹ️  Table already has ${rows[0].c} rows — skipping seed (data is persistent).`);
    return;
  }

  const seedPath = path.join(__dirname, 'seed-data.json');
  if (!fs.existsSync(seedPath)) {
    console.log('ℹ️  No seed-data.json found, starting with an empty table.');
    return;
  }

  let seed;
  try {
    seed = JSON.parse(fs.readFileSync(seedPath, 'utf8'));
  } catch (e) {
    console.error('Seed parse error:', e.message);
    return;
  }

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    for (const u of seed) {
      await client.query(
        `INSERT INTO usecases (id, "businessUnit", name, description, priority, owner, status, output, "isPersonal")
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
         ON CONFLICT (id) DO NOTHING`,
        [u.id, u.businessUnit, u.name, u.description, u.priority,
         u.owner || null, u.status || 'Planned', u.output || '', u.isPersonal ? 1 : 0]
      );
    }
    // Advance the SERIAL sequence past the seeded ids so new inserts don't collide.
    await client.query(
      `SELECT setval(pg_get_serial_sequence('usecases','id'),
                     GREATEST((SELECT MAX(id) FROM usecases), 1))`
    );
    await client.query('COMMIT');
    console.log(`✅ Seeded ${seed.length} baseline use cases (one-time).`);
  } catch (e) {
    await client.query('ROLLBACK');
    console.error('Seed error:', e.message);
  } finally {
    client.release();
  }
}

// ─── API routes ──────────────────────────────────────────────────────────
app.get('/api/usecases', async (req, res) => {
  try {
    const { rows } = await pool.query('SELECT * FROM usecases ORDER BY "createdAt" DESC, id DESC');
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/usecases', async (req, res) => {
  const { businessUnit, name, description, priority, owner, status, output, isPersonal } = req.body;
  if (!businessUnit || !name || !description || !priority) {
    return res.status(400).json({ error: 'Missing required fields' });
  }
  try {
    const { rows } = await pool.query(
      `INSERT INTO usecases ("businessUnit", name, description, priority, owner, status, output, "isPersonal")
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id`,
      [businessUnit, name, description, priority, owner || null, status || 'Planned', output || null, isPersonal ? 1 : 0]
    );
    res.json({ id: rows[0].id, message: 'Use case created' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.put('/api/usecases/:id', async (req, res) => {
  const { businessUnit, name, description, priority, owner, status, output, isPersonal } = req.body;
  try {
    await pool.query(
      `UPDATE usecases
       SET "businessUnit"=$1, name=$2, description=$3, priority=$4, owner=$5,
           status=$6, output=$7, "isPersonal"=$8, "updatedAt"=NOW()
       WHERE id=$9`,
      [businessUnit, name, description, priority, owner, status, output, isPersonal ? 1 : 0, req.params.id]
    );
    res.json({ message: 'Use case updated' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.delete('/api/usecases/:id', async (req, res) => {
  try {
    await pool.query('DELETE FROM usecases WHERE id=$1', [req.params.id]);
    res.json({ message: 'Use case deleted' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/export-csv', async (req, res) => {
  try {
    const { rows } = await pool.query('SELECT * FROM usecases ORDER BY "businessUnit", priority');
    if (!rows.length) return res.json({ csv: 'No data to export' });
    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(','),
      ...rows.map(r => headers.map(h => `"${(r[h] ?? '').toString().replace(/"/g, '""')}"`).join(','))
    ].join('\n');
    res.setHeader('Content-Type', 'text/csv');
    res.setHeader('Content-Disposition', 'attachment; filename=usecases.csv');
    res.send(csv);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/health', async (req, res) => {
  try {
    const { rows } = await pool.query('SELECT COUNT(*)::int AS c FROM usecases');
    res.json({ status: 'ok', database: 'postgres', rowCount: rows[0].c });
  } catch (err) {
    res.status(500).json({ status: 'error', database: 'disconnected', error: err.message });
  }
});

// ─── Boot ────────────────────────────────────────────────────────────────
initializeDB()
  .then(() => {
    app.listen(PORT, () => {
      console.log(`\n🚀 Server running on http://localhost:${PORT}`);
      console.log('📊 Database: PostgreSQL (persistent)\n');
    });
  })
  .catch((err) => {
    console.error('❌ Failed to initialize database:', err.message);
    // Still start the server so /api/health can report the problem.
    app.listen(PORT, () => console.log(`⚠️  Server up on ${PORT} but DB init failed.`));
  });

process.on('SIGINT', async () => {
  await pool.end().catch(() => {});
  process.exit(0);
});
