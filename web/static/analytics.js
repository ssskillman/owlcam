// Firebase's documented CDN setup for static sites without a JavaScript
// package build: https://firebase.google.com/docs/web/alt-setup#from-the-cdn
import { initializeApp } from "https://www.gstatic.com/firebasejs/12.18.0/firebase-app.js"
import {
  getAnalytics,
  isSupported,
} from "https://www.gstatic.com/firebasejs/12.18.0/firebase-analytics.js"

const firebaseConfig = {
  apiKey: "AIzaSyCnj32HoTproEw2vX6PPGKvxad-QAqlcXU",
  authDomain: "carver-owlcam-72343.firebaseapp.com",
  projectId: "carver-owlcam-72343",
  storageBucket: "carver-owlcam-72343.firebasestorage.app",
  messagingSenderId: "893105889089",
  appId: "1:893105889089:web:9b4253a910a9587922cbc0",
  measurementId: "G-WMSVQJWJQR",
}

// Do Not Track is not enforced by GA4 itself. Respect it before initializing
// so browsers expressing that preference make no Analytics request.
const doNotTrack =
  navigator.doNotTrack === "1" ||
  window.doNotTrack === "1"

if (!doNotTrack) {
  isSupported()
    .then((supported) => {
      if (!supported) return
      const app = initializeApp(firebaseConfig)
      getAnalytics(app)
    })
    .catch(() => {
      // Analytics is non-essential. Ad blockers, offline operation, and
      // restrictive browsers must never affect the OwlCam page or stream.
    })
}
