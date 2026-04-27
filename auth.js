// auth.js - 統一認證與權限管理
import { onAuthStateChanged, signOut } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";
import { getFirestore, doc, getDoc } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-firestore.js";
import { auth, isAdminUser } from "./firebase-config.js";

const db = getFirestore();

// 全局 Promise：確保頁面邏輯可以等待認證完成
let resolveAuth;
window.authReady = new Promise(resolve => { resolveAuth = resolve; });

window.currentUser = null;
window.isAdmin = false;
window.authInitialized = false;

// 防止首次 onAuthStateChanged 未返回時就重定向
let firstAuthCheckDone = false;
let unsubscribeAuth = null;

// 判斷是否在登入頁（更可靠的檢測）
function isLoginPageCheck() {
    const url = window.location.href.toLowerCase();
    const pathname = window.location.pathname.toLowerCase();
    const filename = pathname.split("/").pop() || "";
    
    // 只有當確實在 login.html 或類似登入相關路徑時才算在登入頁
    return filename.includes("login") || url.endsWith("login.html") || 
           (url.includes("/login") && !url.includes("logout") && !url.includes("login-redirect"));
}

unsubscribeAuth = onAuthStateChanged(auth, async (user) => {
    try {
        const isLogin = isLoginPageCheck();
        
        if (!user) {
            window.currentUser = null;
            window.isAdmin = false;
            
            console.log(`[Auth] 未認證 (isLoginPage=${isLogin})`);
            
            // 只在首次檢查完成且不在登入頁時才重定向
            if (firstAuthCheckDone && !isLogin) {
                console.log("[Auth] 重定向到登入頁");
                window.location.href = "login.html";
            }
        } else {
            window.currentUser = user;
            window.isAdmin = isAdminUser(user);
            
            // 嘗試獲取學生資料
            try {
                const snap = await getDoc(doc(db, "students", user.uid));
                if (snap.exists()) window.studentData = snap.data();
            } catch (e) { 
                console.warn("[Auth] 獲取 Firestore 資料失敗:", e.code); 
            }

            console.log(`[Auth] 已認證：${user.email}（${window.isAdmin ? '管理員' : '學生'}）`);
            updateUIForUserRole();
            
            // 在登入頁時，已認證用戶應重定向到首頁
            if (isLogin) {
                console.log("[Auth] 已認證用戶在登入頁，重定向到首頁");
                window.location.href = "index.html";
            }
        }
        
        // 標記首次檢查完成
        if (!firstAuthCheckDone) {
            firstAuthCheckDone = true;
            window.authInitialized = true;
            resolveAuth({ user, isAdmin: window.isAdmin });
        }
        
    } catch (error) {
        console.error("[Auth] 檢查錯誤:", error);
        window.authInitialized = true;
        resolveAuth({ user: null, isAdmin: false });
    }
});

function updateUIForUserRole() {
    const adminEls = document.querySelectorAll(".admin-only");
    const studentEls = document.querySelectorAll(".student-only");
    adminEls.forEach(el => window.isAdmin ? el.classList.remove("hidden") : el.classList.add("hidden"));
    studentEls.forEach(el => !window.isAdmin ? el.classList.remove("hidden") : el.classList.add("hidden"));
}

window.handleLogout = async () => {
    if (confirm("確定要登出嗎？")) {
        await signOut(auth);
        window.location.href = "login.html";
    }
};