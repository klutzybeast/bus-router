/**
 * INSTANT Bus Assignment Webhook
 * Receives updates from the app and writes to Google Sheet immediately
 * 
 * SETUP:
 * 1. Open your SOURCE sheet (1QX0BSUuG889BjOYsTji8kYwT3VomSRE1j2_ZtxLd65k)
 * 2. Extensions → Apps Script
 * 3. Paste this script
 * 4. Click Deploy → New Deployment
 * 5. Type: Web App
 * 6. Execute as: Me
 * 7. Who has access: Anyone
 * 8. Click Deploy
 * 9. COPY THE WEB APP URL (looks like: https://script.google.com/...../exec)
 * 10. Give me that URL to configure the backend
 */

const BUS_COLUMN_AM = 6;   // Column F: "2026Transportation M AM Bus"
const BUS_COLUMN_PM = 13;  // Column M: "2026Transportation M PM Bus"

/**
 * Webhook receiver - called when bus assignment changes
 */
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    
    const firstName = data.first_name;
    const lastName = data.last_name;
    const amBus = data.am_bus_number;
    const pmBus = data.pm_bus_number;
    
    Logger.log(`Updating ${firstName} ${lastName}: AM=${amBus}, PM=${pmBus}`);
    
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const dataRange = sheet.getDataRange();
    const values = dataRange.getValues();
    
    let updated = false;
    
    // Find the camper row
    for (let i = 1; i < values.length; i++) {
      const rowLastName = values[i][0];
      const rowFirstName = values[i][1];
      
      if (rowLastName === lastName && rowFirstName === firstName) {
        // Update AM bus (column F = index 5)
        if (amBus) {
          sheet.getRange(i + 1, BUS_COLUMN_AM).setValue(amBus);
        }
        
        // Update PM bus (column M = index 12)
        if (pmBus) {
          sheet.getRange(i + 1, BUS_COLUMN_PM).setValue(pmBus);
        }
        
        updated = true;
        Logger.log(`✓ Updated row ${i + 1}`);
        break;
      }
    }
    
    return ContentService.createTextOutput(JSON.stringify({
      status: updated ? 'success' : 'not_found',
      message: updated ? 'Bus assignment updated' : 'Camper not found'
    })).setMimeType(ContentService.MimeType.JSON);
    
  } catch (error) {
    Logger.log('ERROR: ' + error.toString());
    return ContentService.createTextOutput(JSON.stringify({
      status: 'error',
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Test function
 */
function testWebhook() {
  const testData = {
    postData: {
      contents: JSON.stringify({
        first_name: 'Test',
        last_name: 'Camper',
        am_bus_number: 'Bus #01',
        pm_bus_number: 'Bus #01'
      })
    }
  };
  
  const result = doPost(testData);
  Logger.log(result.getContent());
}
