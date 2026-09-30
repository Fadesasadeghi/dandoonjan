"use strict";
// Decorative asset lifecycle only. Case, upload, processing and report handlers
// remain in app.js. A failed image exposes a neutral inline status message.
const landingTooth = document.getElementById("landing-tooth");
const showLandingFallback = () => landingTooth.closest("figure").classList.add("art-unavailable");
landingTooth.addEventListener("error", showLandingFallback);
if (landingTooth.complete && !landingTooth.naturalWidth) showLandingFallback();
