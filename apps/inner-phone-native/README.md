# Inner Phone

A minimal native iPhone prototype of a "phone inside the phone."

## What this build does
- Shows a custom fictional dialer UI.
- Accepts a phone number manually.
- Never requests Contacts permission and contains no Contacts code.
- Uses iOS's `tel:` handoff when CALL is tapped.
- iOS controls the final confirmation and cellular call.

## Run it
1. Open `InnerPhone.xcodeproj` in Xcode on a Mac.
2. Select the **InnerPhone** target.
3. Under Signing & Capabilities, choose your Apple Development team.
4. If Xcode asks, change the bundle identifier to something unique.
5. Plug in your iPhone, select it as the run destination, and press Run.
6. Test calling on the physical iPhone; the iOS Simulator does not provide normal cellular calling behavior.

## Privacy
This prototype has no Contacts usage description and does not link to Contacts APIs. It stores no address book. The entered number exists only as transient UI state in this version.

## Browser preview
The GitHub Pages preview is at `../inner-phone.html`. It uses a manual keypad and `tel:` handoff but is not a replacement for the native iOS build.
