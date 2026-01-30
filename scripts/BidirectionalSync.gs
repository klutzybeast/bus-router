/**
 * BIDIRECTIONAL Google Sheets Sync
 * Updates bus assignments back to your CampMinder sheet
 * 
 * SETUP:
 * 1. Open your CampMinder Google Sheet (the source data)
 * 2. Extensions → Apps Script
 * 3. Paste this script
 * 4. Update SHEET_ID and API_URL below
 * 5. Run setupTrigger once
 */

// CONFIGURATION
const API_URL = 'https://routewise-camp.preview.emergentagent.com/api/download/bus-assignments';
const CAMPMINDER_SHEET_ID = '1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k';  // Your source sheet
const BUS_COLUMN_AM = 6;  // Column F: "2026Transportation M AM Bus"
const BUS_COLUMN_PM = 13; // Column M: "2026Transportation M PM Bus"

/**
 * Update bus assignments in CampMinder sheet from the system
 */
function updateBusAssignments() {
  try {
    Logger.log('Fetching bus assignments from system...');
    
    // Get assignments from API (CSV format)
    const response = UrlFetchApp.fetch(API_URL);
    const csvText = response.getContentText();
    
    // Parse CSV
    const lines = csvText.split('\n');
    const assignments = {};
    
    for (let i = 1; i < lines.length; i++) {  // Skip header
      const parts = lines[i].split(',');
      if (parts.length < 3) continue;
      
      const lastName = parts[0];
      const firstName = parts[1];
      const busAssignment = parts[2];
      const type = parts[7];  // AM Pickup or PM Drop-off
      
      const key = `${lastName}_${firstName}`;
      
      if (!assignments[key]) {
        assignments[key] = {am: '', pm: ''};
      }
      
      if (type && type.includes('AM')) {
        assignments[key].am = busAssignment;
      } else if (type && type.includes('PM')) {
        assignments[key].pm = busAssignment;
      }
    }
    
    Logger.log(`Parsed ${Object.keys(assignments).length} camper assignments`);
    
    // Open source sheet
    const sheet = SpreadsheetApp.openById(CAMPMINDER_SHEET_ID).getActiveSheet();
    const data = sheet.getDataRange().getValues();
    
    let updatedCount = 0;
    
    // Update each row
    for (let i = 1; i < data.length; i++) {  // Skip header
      const lastName = data[i][0];
      const firstName = data[i][1];
      const key = `${lastName}_${firstName}`;
      
      if (assignments[key]) {
        // Update AM bus (column F)
        if (assignments[key].am && data[i][BUS_COLUMN_AM - 1] !== assignments[key].am) {
          sheet.getRange(i + 1, BUS_COLUMN_AM).setValue(assignments[key].am);
          updatedCount++;
        }
        
        // Update PM bus (column M)
        if (assignments[key].pm && data[i][BUS_COLUMN_PM - 1] !== assignments[key].pm) {
          sheet.getRange(i + 1, BUS_COLUMN_PM).setValue(assignments[key].pm);
          updatedCount++;
        }
      }
    }
    
    Logger.log(`✓ Updated ${updatedCount} bus assignments in CampMinder sheet`);
    
    // Also refresh seat availability
    if (typeof updateSeatAvailability === 'function') {
      updateSeatAvailability();
    }
    
  } catch (error) {
    Logger.log('Error updating bus assignments: ' + error.toString());
  }
}

/**
 * Setup trigger to sync every 15 minutes
 */
function setupBidirectionalSync() {
  // Delete existing triggers
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  
  // Update bus assignments every 15 minutes
  ScriptApp.newTrigger('updateBusAssignments')
    .timeBased()
    .everyMinutes(15)
    .create();
  
  Logger.log('✓ Bidirectional sync enabled!');
  Logger.log('Bus assignments will update in CampMinder sheet every 15 minutes');
  
  // Run once immediately
  updateBusAssignments();
}

/**
 * Manual sync button
 */
function manualSyncBuses() {
  updateBusAssignments();
}
