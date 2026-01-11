/**
 * Instant Bus Update Webhook
 * PASTE THIS IN YOUR SOURCE SHEET APPS SCRIPT
 */

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    
    const firstName = data.first_name;
    const lastName = data.last_name;
    const amBus = data.am_bus_number;
    const pmBus = data.pm_bus_number;
    
    Logger.log('Received: ' + firstName + ' ' + lastName);
    
    // Get the FIRST sheet (main data sheet)
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getSheets()[0];  // First tab
    
    const lastRow = sheet.getLastRow();
    const data = sheet.getRange(1, 1, lastRow, 16).getValues();
    
    let found = false;
    
    // Search for camper (case-insensitive)
    for (let i = 1; i < data.length; i++) {
      const rowLast = String(data[i][0]).trim().toLowerCase();
      const rowFirst = String(data[i][1]).trim().toLowerCase();
      
      if (rowLast === lastName.toLowerCase() && rowFirst === firstName.toLowerCase()) {
        // Update AM bus (column F = 6)
        if (amBus) {
          sheet.getRange(i + 1, 6).setValue(amBus);
          Logger.log('Updated AM bus row ' + (i+1) + ' to ' + amBus);
        }
        
        // Update PM bus (column M = 13)
        if (pmBus) {
          sheet.getRange(i + 1, 13).setValue(pmBus);
          Logger.log('Updated PM bus row ' + (i+1) + ' to ' + pmBus);
        }
        
        found = true;
        break;
      }
    }
    
    SpreadsheetApp.flush();  // Force write
    
    return ContentService.createTextOutput(JSON.stringify({
      status: found ? 'success' : 'not_found',
      message: found ? 'Updated' : 'Camper not found in sheet'
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    Logger.log('ERROR: ' + error.toString());
    return ContentService.createTextOutput(JSON.stringify({
      status: 'error',
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}
