const sqlite3 = require('sqlite3').verbose();
const path = require('path');

const dbPath = path.join(__dirname, 'usecases.db');
const db = new sqlite3.Database(dbPath, (err) => {
  if (err) {
    console.error('❌ Database error:', err);
    process.exit(1);
  } else {
    console.log('✅ Connected to database');
    initDB().then(importData).then(closeDB);
  }
});

function initDB() {
  return new Promise((resolve, reject) => {
    db.run(`
      CREATE TABLE IF NOT EXISTS usecases (
        id INTEGER PRIMARY KEY,
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
      if (err) reject(err);
      else {
        console.log('✅ Table initialized');
        resolve();
      }
    });
  });
}

function importData() {
  return new Promise((resolve, reject) => {
    // Your data
    const usecases = [{"id":2,"businessUnit":"Personal","priority":"Critical","name":"Generate Revenue","description":"Generate Revenue with Content Skills","owner":"Arvind","status":"Planned","output":""},{"id":3,"businessUnit":"Chef Onboarding","priority":"Medium","name":"One Click Onboard","description":"1. Make Pink Sheet online (Move from Share Drive excel to an excel looking App)\n2. Call Image Generation in Batch and take it to approve stage\n3. Retry or Accept Image\n4. Push to Insert \n5. Approve by Admin\n6. Push it Live and sync with Algolia","owner":"Arvind","status":"Planned","output":""},{"id":4,"businessUnit":"Chef Onboarding","priority":"Low","name":"Chef Scrum Manager","description":"1. Currently chef assignment and task entries happen manually over excel.\n2. Create a pipeline where chef onboarding requests from the App and the current chef leads data are unified into one central data base\n3. Project and task management should happen over this underlying data\n4. Everyday task updates should happen automatically and alerts happen when status change.","owner":"Arvind","status":"Planned","output":""},{"id":5,"businessUnit":"Logistics","priority":"High","name":"Delivery Booking MCP","description":"1. In the absence of Porter APIs, we need to orchestrate a MCP booking capabilities with Porter and Rapido and automate booking.\n2. Once we see it working, we need to fuse this as part of \"Book Now\" capabilities in our delivery management dashboard.\n3. Core Capabilities: Book Rides | Update Status | Track | Cancel | Rebook","owner":"Arvind","status":"In Progress","output":""},{"id":6,"businessUnit":"Chef Onboarding","priority":"Medium","name":"Onboarding Performance Dashboard","description":"Build an interactive dashboard where we can see chef onboarding progress MoM. Be able to: (1) See Health board. Chefs Active/InActive/Retired. Time to Onboard.\n(2) No of chefs onboarded MoM by Team Members. \n(3) Goal Tracker","owner":"Arvind","status":"Planned","output":""},{"id":7,"businessUnit":"Logistics","priority":"Low","name":"Logistics Performance Dashboard","description":"Build an interactive dashboard where we surface:\n1. Total Deliveries per day, per month\n2. Cost Per Delivery\n3. Delivery Kms\n4. Delivery Time","owner":"Arvind","status":"Planned","output":""},{"id":8,"businessUnit":"Operations","priority":"Medium","name":"Smart Swapper","description":"When a chef rejects an order or dont accept within 20 mins, then automatically ping the chefs nearer to customer within 5 kms radius to see if they will accept it. If they accept it, then the order gets transferred in the database.","owner":"Arvind","status":"Planned","output":""},{"id":9,"businessUnit":"Operations","priority":"Low","name":"Auto Credit for Cancellation","description":"When an order that is not picked-up yet needs to be cancelled, the system automatically process refund with PhonePe and intimates customers","owner":"Arvind","status":"Planned","output":""},{"id":10,"businessUnit":"Operations","priority":"Low","name":"Auto Cancel Instant Order","description":"Auto Cancel Instant Order is the chef has not accepted or the team hasnt swapped within 30 mins. Send notifications to customers.","owner":"Arvind","status":"Planned","output":""},{"id":11,"businessUnit":"Chef Onboarding","priority":"Medium","name":"Free Sampler","description":"Build an automated system that allows the onboarding team to figure out who is the best customer to receive Food Sample. This should be based on Customer LTV and proximity to Chef. Once the team approves the customer, an order has to be generated as Sample order and arrive at delivery dashboard. The chef should not be paid as it Sample and the chef wont exist in the chef database but temp table here with only bare minimum information","owner":"Arvind","status":"Planned","output":""}];

    let imported = 0;
    let errors = 0;

    usecases.forEach(uc => {
      const isPersonal = uc.businessUnit === 'Personal' ? 1 : 0;

      db.run(
        `INSERT OR REPLACE INTO usecases (id, businessUnit, name, description, priority, owner, status, output, isPersonal)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [uc.id, uc.businessUnit, uc.name, uc.description, uc.priority, uc.owner, uc.status, uc.output, isPersonal],
        function(err) {
          if (err) {
            console.error(`❌ Error importing id ${uc.id}:`, err.message);
            errors++;
          } else {
            imported++;
          }

          if (imported + errors === usecases.length) {
            console.log(`\n✅ Import complete: ${imported} records imported, ${errors} errors`);
            resolve();
          }
        }
      );
    });
  });
}

function closeDB() {
  db.close((err) => {
    if (err) console.error('Error closing database:', err);
    else console.log('✅ Database connection closed');
    process.exit(0);
  });
}
