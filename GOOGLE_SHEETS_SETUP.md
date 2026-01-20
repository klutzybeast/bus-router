# Google Sheets Auto-Update Setup Instructions

## ✅ Super Easy Setup (No API Keys Needed!)

Your seat availability sheet will automatically update every 15 minutes using Google Apps Script.

---

## 📋 Step-by-Step Instructions

### Step 1: Open Your Google Sheet
1. Go to your existing "Bus by Bus Seat Availability 2026" spreadsheet
2. OR create a new Google Sheet at https://sheets.google.com

### Step 2: Open Apps Script Editor
1. In your Google Sheet, click **Extensions** → **Apps Script**
2. This opens the script editor in a new tab

### Step 3: Paste the Script
1. **Delete** any existing code in the editor
2. **Copy** the entire script from `/app/scripts/GoogleSheets_AutoUpdate.gs`
3. **Paste** it into the Apps Script editor
4. The API URL is already configured: `https://campmap-routes.preview.emergentagent.com/api/sheets/compact-availability`

### Step 4: Save and Authorize
1. Click the **💾 Save** icon (or Ctrl+S / Cmd+S)
2. Name your project: `Bus Seat Auto-Update`
3. Click the **▶️ Run** button next to `setupTrigger`
4. Google will ask for permissions:
   - Click **Review permissions**
   - Choose your Google account
   - Click **Advanced** → **Go to Bus Seat Auto-Update (unsafe)**
   - Click **Allow**

### Step 5: Done!
✅ The script will run immediately and update your sheet
✅ It will automatically run every 15 minutes forever
✅ You can close the Apps Script tab

---

## 📊 What The Sheet Shows

Your sheet will display:

**Summary View:**
| Bus # | Capacity | Assigned | Available | Status |
|-------|----------|----------|-----------|--------|
| Bus #01 | 50 | 10 | 40 | 🟢 OPEN |
| Bus #02 | 50 | 3 | 47 | 🟢 OPEN |
| Bus #14 | 50 | 10 | 40 | 🟢 OPEN |
| ... | ... | ... | ... | ... |

**Color Coding:**
- 🟢 Green Background = Available seats (6+)
- 🟡 Yellow Background = Low availability (1-5 seats)
- 🔴 Red Background = FULL (0 seats)

**Auto-Updates:**
- Every 15 minutes (synced with CampMinder)
- Shows real-time seat availability
- Includes when seats are added OR removed

---

## 🔧 Manual Controls (Optional)

In Apps Script, you can run these functions manually:

- **manualRefresh** - Update sheet immediately (don't wait 15 min)
- **removeTriggers** - Stop auto-updates
- **setupTrigger** - Restart auto-updates

---

## 🎯 How It Works

1. Every 15 minutes, CampMinder syncs with your backend
2. New campers are auto-assigned to optimal buses
3. Your API endpoint calculates seat availability per bus
4. Google Apps Script fetches this data
5. Sheet updates automatically with latest numbers
6. Directors see real-time availability!

---

## 🆘 Troubleshooting

**Sheet not updating?**
- Open Apps Script → View → Executions
- Check for errors in the log
- Verify API_URL in the script is correct

**Permission error?**
- Re-run setupTrigger and re-authorize

**Need help?**
- Check Apps Script logs: View → Logs
- Test manually by running `manualRefresh`

---

## 📍 Your API Endpoint

The Google Sheet pulls data from:
`https://campmap-routes.preview.emergentagent.com/api/sheets/compact-availability`

You can test it anytime in your browser to see the raw data!
