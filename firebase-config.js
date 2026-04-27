import { initializeApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth, setPersistence, browserLocalPersistence } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";

export const firebaseConfig = {
    apiKey: "AIzaSyBgP4nuRrpTUjRsjIZPTCFMF8ichhNTm0g",
    authDomain: "kywc-3d-announcements.firebaseapp.com",
    projectId: "kywc-3d-announcements",
    storageBucket: "kywc-3d-announcements.firebasestorage.app",
    messagingSenderId: "388023540027",
    appId: "1:388023540027:web:4a82dc466b052ebc313f1e",
    measurementId: "G-ZT77DVXW79"
};

export const DEFAULT_API_BASE = "https://kywc3d.qzz.io/api";
const savedApiBase = (localStorage.getItem("apiBase") || "").replace(/\/+$/, "");
const legacyApiBase = "http://127.0.0.1:8000/api";
export const API_BASE = savedApiBase && savedApiBase !== legacyApiBase ? savedApiBase : DEFAULT_API_BASE;
export const API_ENABLED = API_BASE.length > 0;

const savedPhotosApiBase = (localStorage.getItem("photosApiBase") || "").replace(/\/+$/, "");
export const DEFAULT_PHOTOS_API_BASE = "https://kywc3d.qzz.io/api";
export const PHOTOS_API_BASE = savedPhotosApiBase || API_BASE || DEFAULT_PHOTOS_API_BASE;
export const PHOTOS_API_ENABLED = PHOTOS_API_BASE.length > 0;

export const ADMIN_EMAILS = ["admin@kywc.edu.hk", "test1@gmail.com", "admin@gmail.com"];
export const ADMIN_UIDS = [];

export function isAdminUser(user) {
    if (!user) return false;
    return ADMIN_EMAILS.includes(user.email) || ADMIN_UIDS.includes(user.uid);
}

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);

// 啟用本地持久化存儲認證狀態 (全局初始化一次)
setPersistence(auth, browserLocalPersistence).catch(e => console.warn("Persistence init:", e));
