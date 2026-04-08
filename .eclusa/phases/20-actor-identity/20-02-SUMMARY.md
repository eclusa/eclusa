# 20-02 Summary

## Task 1
- Replaced the login form secret key field with email and password fields.
- Kept the existing MercuryOS zinc-dark styling and updated the card copy to describe email/password sign-in.
- Forwarded backend authentication errors to the UI and added a `Create account` link to `/register`.

## Task 2
- Added `ui/src/pages/RegisterPage.tsx` with full name, email, password, and confirm-password fields.
- Added client-side password confirmation validation with the message `Passwords do not match`.
- Added an `Already have an account?` link back to `/login`.

## Task 3
- Wired `/register` into `ui/src/App.tsx` as an unauthenticated route alongside `/login`.

## Task 4
- Updated `ui/src/auth/AuthProvider.tsx` with JWT payload helpers that understand `sub` and legacy `actor_id` subject claims.
- Preserved token storage and Authorization header behavior; only the token subject decoding logic was expanded.

## Verification
- TypeScript compiled successfully against the writable clone with `tsc --noEmit`.
