/**
 * Camp Bus Routing - Auto-Update Seat Availability
 * 
 * HOW TO INSTALL:
 * 1. Open your Google Sheet
 * 2. Extensions → Apps Script
 * 3. Delete any existing code
 * 4. Paste this entire script
 * 5. Update API_URL below with your backend URL
 * 6. Click Save (💾 icon)
 * 7. Run 'setupTrigger' once (it will ask for permissions)
 * 8. Done! Sheet will auto-update every 15 minutes
 */

// ⚙️ CONFIGURATION - Update this with your backend URL
const API_URL = 'https://camp-busmap.preview.emergentagent.com/api/sheets/compact-availability';

/**
 * Main function to update the sheet with seat availability
 */
function updateSeatAvailability() {
  try {
    Logger.log('Fetching seat availability data...');
    
    // Fetch data from API
    const response = UrlFetchApp.fetch(API_URL);
    const json = JSON.parse(response.getContentText());
    
    if (json.status !== 'success') {
      throw new Error('API returned error status');
    }
    
    const data = json.data;
    const lastUpdated = new Date(json.last_updated);
    
    // Get active sheet
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // Clear existing data
    sheet.clear();
    
    // Add title
    sheet.getRange(1, 1).setValue('🚌 Camp Bus Seat Availability - 2026')
      .setFontSize(16)
      .setFontWeight('bold')
      .setBackground('#1e40af')
      .setFontColor('#ffffff');
    
    sheet.getRange(2, 1).setValue('Last Updated: ' + Utilities.formatDate(lastUpdated, Session.getScriptTimeZone(), 'MM/dd/yyyy HH:mm:ss'))
      .setFontSize(10)
      .setFontColor('#666666');
    
    // Write data starting from row 4
    const startRow = 4;
    const numRows = data.length;
    const numCols = data[0].length;
    
    // Write all data at once for better performance
    sheet.getRange(startRow, 1, numRows, numCols).setValues(data);
    
    // Format header row
    sheet.getRange(startRow, 1, 1, numCols)
      .setBackground('#2563eb')
      .setFontColor('#ffffff')
      .setFontWeight('bold')
      .setHorizontalAlignment('center');
    
    // Format data rows
    for (let i = 1; i < numRows; i++) {
      const row = startRow + i;
      const available = sheet.getRange(row, 4).getValue();
      
      // Color code based on availability
      if (available <= 0) {
        sheet.getRange(row, 1, 1, numCols).setBackground('#fee2e2'); // Red - Full
      } else if (available <= 5) {
        sheet.getRange(row, 1, 1, numCols).setBackground('#fef3c7'); // Yellow - Low
      } else {
        sheet.getRange(row, 1, 1, numCols).setBackground('#d1fae5'); // Green - Open
      }
    }
    
    // Auto-resize columns
    sheet.autoResizeColumns(1, numCols);
    
    // Add borders
    sheet.getRange(startRow, 1, numRows, numCols).setBorder(
      true, true, true, true, true, true,
      '#000000', SpreadsheetApp.BorderStyle.SOLID
    );
    
    Logger.log('✓ Sheet updated successfully!');
    
  } catch (error) {
    Logger.log('Error updating sheet: ' + error.toString());
    
    // Write error to sheet
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    sheet.getRange(1, 1).setValue('❌ Error updating data: ' + error.toString())
      .setBackground('#fee2e2')
      .setFontColor('#dc2626');
  }
}

/**
 * Setup automatic trigger (run this ONCE)
 */
function setupTrigger() {
  // Delete existing triggers
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  
  // Create new trigger to run every 15 minutes
  ScriptApp.newTrigger('updateSeatAvailability')
    .timeBased()
    .everyMinutes(15)
    .create();
  
  Logger.log('✓ Trigger created! Sheet will auto-update every 15 minutes.');
  
  // Run once immediately
  updateSeatAvailability();
}

/**
 * Remove all triggers (run this to stop auto-updates)
 */
function removeTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  Logger.log('✓ All triggers removed. Auto-update stopped.');
}

/**
 * Manual refresh button (run this anytime to update immediately)
 */
function manualRefresh() {
  updateSeatAvailability();
}
