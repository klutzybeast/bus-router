/**
 * Camp Bus Routing - Auto-Update Seat Availability
 * 
 * SETUP:
 * 1. Open your SEAT AVAILABILITY Google Sheet (ID: 1ZK58gjF4BO0HF_2y6oovrjzRH3qV5zAs8H-7CeKOSGE)
 * 2. Extensions → Apps Script
 * 3. Paste this script
 * 4. Click Save
 * 5. Run 'setupTrigger' once
 * 6. Done! Updates every 15 minutes
 */

// ⚙️ CONFIGURATION
const API_URL = 'https://bustrek.preview.emergentagent.com/api/sheets/seat-availability';

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
    
    // Add title with styling
    sheet.getRange(1, 1, 1, 7).merge()
      .setValue(data[0][0])
      .setFontSize(18)
      .setFontWeight('bold')
      .setBackground('#1e40af')
      .setFontColor('#ffffff')
      .setHorizontalAlignment('center');
    
    sheet.getRange(2, 1, 1, 7).merge()
      .setValue(data[1][0])
      .setFontSize(12)
      .setBackground('#3b82f6')
      .setFontColor('#ffffff')
      .setHorizontalAlignment('center');
    
    // Write all data starting from row 3
    const dataRows = data.slice(2);  // Skip title rows
    sheet.getRange(3, 1, dataRows.length, 7).setValues(
      dataRows.map(row => {
        // Pad rows to 7 columns
        while (row.length < 7) row.push('');
        return row.slice(0, 7);
      })
    );
    
    // Format bus headers (lines starting with "Rolling River Bus Number:")
    let currentRow = 3;
    for (let i = 0; i < dataRows.length; i++) {
      const row = dataRows[i];
      const cellValue = row[0] ? row[0].toString() : '';
      
      if (cellValue.startsWith('Rolling River Bus Number:')) {
        // Bus number header - blue background
        sheet.getRange(currentRow, 1, 1, 7).merge()
          .setBackground('#2563eb')
          .setFontColor('#ffffff')
          .setFontWeight('bold')
          .setFontSize(12);
      } else if (cellValue.startsWith('Location:') || cellValue.startsWith('Bus Driver') || cellValue.startsWith('Bus Counselor') || cellValue.startsWith('Seats:')) {
        // Info rows - light blue background
        sheet.getRange(currentRow, 1, 1, 7).merge()
          .setBackground('#dbeafe')
          .setFontWeight('bold');
      } else if (cellValue === 'Last Name' || (row.length > 1 && row[1] === 'First Name')) {
        // Camper table header - dark gray
        sheet.getRange(currentRow, 1, 1, 7)
          .setBackground('#374151')
          .setFontColor('#ffffff')
          .setFontWeight('bold')
          .setHorizontalAlignment('center');
      } else if (cellValue.startsWith('Seat Totals')) {
        // Totals section - yellow if warning, green otherwise
        const hasWarning = cellValue.includes('⚠️');
        sheet.getRange(currentRow, 1, 1, 7).merge()
          .setBackground(hasWarning ? '#fef3c7' : '#d1fae5')
          .setFontWeight('bold');
      } else if (cellValue.startsWith('Available Seats:') || cellValue.startsWith('Total Campers')) {
        // Stats rows
        sheet.getRange(currentRow, 1, 1, 7).merge()
          .setBackground('#f3f4f6')
          .setFontWeight('bold');
      } else if (cellValue.startsWith('Half 1') || cellValue.startsWith('Half 2')) {
        // Half counts - merge and style
        sheet.getRange(currentRow, 1, 1, 7).merge()
          .setBackground('#e0e7ff');
      }
      
      currentRow++;
    }
    
    // Auto-resize columns
    for (let col = 1; col <= 7; col++) {
      sheet.autoResizeColumn(col);
    }
    
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
