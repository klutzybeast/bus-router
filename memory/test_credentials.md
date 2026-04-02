# Test Credentials

## Counselor App (/counselor)
- **Login PIN**: Any valid bus number (1-34)
- **Test Bus**: Enter `1` to login as Bus #01 (15 campers)
- **No passcode required** - Direct access

## Admin Dashboard (/)
- **Passcode**: `Camp1993`
- **SHA-256 Hash**: `b7065804da716830f45517bd6fcb311b75edabc58375df300cb584063cc0bc81`
- **Session Storage Keys**: `rrdc_auth_token`, `rrdc_auth_ts`
- **Session Timeout**: 45 minutes (warning at 40 minutes)
- **Lockout**: 5 failed attempts = 60 second lockout

## API Testing
- Use REACT_APP_BACKEND_URL from frontend/.env
- Current: https://camper-location.preview.emergentagent.com
