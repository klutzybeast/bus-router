const API_URL = 'https://bustrek.preview.emergentagent.com/api/sheets/seat-availability';

function updateSeatAvailability() {
  try {
    Logger.log('Fetching data...');
    const response = UrlFetchApp.fetch(API_URL);
    const json = JSON.parse(response.getContentText());
    
    if (json.status !== 'success') {
      throw new Error('API returned error');
    }
    
    const data = json.data;
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    
    // Clear sheet
    sheet.clear();
    
    // Write all data at once
    sheet.getRange(1, 1, data.length, 10).setValues(data);
    
    // Format title rows
    sheet.getRange(1, 1, 1, 10).merge().setBackground('#1e40af').setFontColor('#ffffff').setFontSize(18).setFontWeight('bold').setHorizontalAlignment('center');
    sheet.getRange(2, 1, 1, 10).merge().setBackground('#3b82f6').setFontColor('#ffffff').setFontSize(14).setHorizontalAlignment('center');
    
    // Format header row (row 4)
    sheet.getRange(4, 1, 1, 10).setBackground('#2563eb').setFontColor('#ffffff').setFontWeight('bold').setHorizontalAlignment('center');
    
    // Format data rows
    for (let i = 5; i <= data.length; i++) {
      const cellValue = sheet.getRange(i, 1).getValue().toString();
      
      if (cellValue === 'TOTALS') {
        // Totals row - dark background
        sheet.getRange(i, 1, 1, 10).setBackground('#374151').setFontColor('#ffffff').setFontWeight('bold');
      } else if (cellValue.startsWith('AVAILABLE')) {
        // Available summary section
        sheet.getRange(i, 1, 1, 10).merge().setBackground('#d1fae5').setFontWeight('bold').setFontSize(12);
      } else if (cellValue.startsWith('Half')) {
        // Half season availability rows
        sheet.getRange(i, 1).setFontWeight('bold');
        sheet.getRange(i, 2).setBackground('#e0e7ff').setFontWeight('bold').setFontSize(14);
      } else if (cellValue.startsWith('Bus')) {
        // Regular bus rows - check availability
        const available = sheet.getRange(i, 10).getValue();
        if (available <= 0) {
          sheet.getRange(i, 1, 1, 10).setBackground('#fee2e2'); // Red - FULL
        } else if (available <= 5) {
          sheet.getRange(i, 1, 1, 10).setBackground('#fef3c7'); // Yellow - LOW
        } else {
          sheet.getRange(i, 1, 1, 10).setBackground('#d1fae5'); // Green - OPEN
        }
      }
    }
    
    // Auto-resize columns
    for (let col = 1; col <= 10; col++) {
      sheet.autoResizeColumn(col);
    }
    
    // Add borders
    sheet.getRange(4, 1, data.length - 3, 10).setBorder(true, true, true, true, true, true);
    
    Logger.log('SUCCESS: Sheet updated with ' + (data.length - 4) + ' buses');
    
  } catch (error) {
    Logger.log('ERROR: ' + error.toString());
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    sheet.getRange(1, 1).setValue('ERROR: ' + error.toString()).setBackground('#fee2e2');
  }
}

function setupTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(function(t) { ScriptApp.deleteTrigger(t); });
  
  ScriptApp.newTrigger('updateSeatAvailability').timeBased().everyMinutes(15).create();
  updateSeatAvailability();
  Logger.log('Setup complete! Check your sheet now.');
}

function manualRefresh() {
  updateSeatAvailability();
}
