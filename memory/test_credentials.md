# Test Credentials

## Admin Dashboard (/)
- **Passcode**: `Camp1993`
- SHA-256 hash: `b7065804da716830f45517bd6fcb311b75edabc58375df300cb584063cc0bc81`
- Session stored in `sessionStorage` (clears on tab close)
- Auto-lock after 45 minutes of inactivity
- 5 failed attempts = 60 second lockout

## Counselor App (/counselor)
- No passcode required - direct access
- **Login PIN**: Any valid bus number (1-34)
- **Test Bus**: Enter `1` to login as Bus #01 (15 campers)
- **Admin Access**: Enter `admin` as PIN → then enter password `Camp1993` → opens admin panel with Routes & Clear Data tabs

## API Testing
- Use REACT_APP_BACKEND_URL from frontend/.env
- Current: https://counselor-admin-test.preview.emergentagent.com
