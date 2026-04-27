#!/usr/bin/env python3
"""
遷移腳本：從 students.json 遷移到 Firebase Auth + Firestore
"""

import json
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, auth, firestore
from datetime import datetime, timezone

def get_service_account_path():
    env_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "").strip()
    if env_path:
        return Path(env_path)
    return Path(__file__).parent / "serviceAccountKey.json"

# 初始化 Firebase
if not firebase_admin.apps:
    service_account_path = get_service_account_path()
    if not service_account_path.exists():
        raise FileNotFoundError(
            f"找不到 Firebase 服務帳戶 JSON：{service_account_path}\n"
            "請設定環境變量 FIREBASE_SERVICE_ACCOUNT_KEY，或把 JSON 放到專案根目錄並命名為 serviceAccountKey.json"
        )
    cred = credentials.Certificate(str(service_account_path))
    firebase_admin.initialize_app(cred)

db = firestore.client()


def main():
    students_file = Path(__file__).parent / "students.json"
    
    if not students_file.exists():
        print("❌ students.json 不存在")
        return
    
    # 讀取舊數據
    with open(students_file, "r", encoding="utf-8") as f:
        try:
            students = json.load(f)
        except json.JSONDecodeError:
            print("❌ students.json 格式錯誤")
            return
    
    if not isinstance(students, list):
        print("❌ students.json 不是列表格式")
        return
    
    print(f"\n📋 找到 {len(students)} 筆學生記錄")
    
    created = 0
    failed = 0
    skipped = 0
    
    for idx, student in enumerate(students, 1):
        email = (student.get("email") or "").strip().lower()
        password = student.get("password_hash")  # 這是 hash 值，無法恢復
        name = student.get("name") or f"Student {idx}"
        student_id = student.get("student_id", "")
        
        if not email:
            print(f"  ⏭️  行 {idx}: 郵箱缺失，略過")
            skipped += 1
            continue
        
        # 由於無法從 hash 恢復密碼，我們為每個學生生成一個臨時密碼
        # 實際應用中，應該通過其他方式重新設置密碼
        temp_password = f"Temp_{student_id or 'Student'}_2026"
        
        try:
            # 檢查用戶是否已存在
            try:
                existing_user = auth.get_user_by_email(email)
                print(f"  ✓ 行 {idx}: {email} 已存在於 Firebase Auth")
                skipped += 1
                continue
            except auth.UserNotFoundError:
                pass  # 用戶不存在，繼續創建
            
            # 在 Firebase Auth 中創建用戶
            user = auth.create_user(
                email=email,
                password=temp_password,
                display_name=name
            )
            
            # 在 Firestore 中保存學生資料
            student_data = {
                "student_id": student_id,
                "name": name,
                "email": email,
                "created_at": student.get("created_at", datetime.now(timezone.utc).isoformat()),
                "uid": user.uid,
                "migrated_from": "students.json"
            }
            db.collection("students").document(user.uid).set(student_data)
            
            print(f"  ✓ 行 {idx}: {email} 遷移成功（臨時密碼：{temp_password}）")
            created += 1
            
        except Exception as e:
            print(f"  ✗ 行 {idx}: {email} 遷移失敗 - {str(e)}")
            failed += 1
    
    print(f"\n📊 遷移統計：")
    print(f"  ✓ 成功遷移：{created} 筆")
    print(f"  ✗ 遷移失敗：{failed} 筆")
    print(f"  ⏭️  已略過：{skipped} 筆")
    print(f"\n💡 注意：由於無法從密碼 hash 恢復原密碼，已為每個學生設置臨時密碼")
    print(f"   建議在管理員頁面重新設置學生密碼或發送密碼重置郵件")


if __name__ == "__main__":
    main()
