import os
import boto3
import firebase_admin
from firebase_admin import credentials, firestore, auth
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv
from typing import Optional
from google.api_core.exceptions import NotFound
from urllib.parse import urlparse, unquote

# 安全載入本地環境變數
if os.path.exists(".env"):
    load_dotenv()

app = FastAPI(title="KYWC-3D API System")

# 🔒 啟用 CORS 跨來源資源共享白名單（精準匹配您的自訂網域）
origins = [
    "https://qzz.io",
    "http://localhost:5500",
    "http://127.0.0.1:5500"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚠️ Firebase 初始化（支援 Vercel 環境變數直接注入與 Private Key 換行修正）
FIREBASE_KEY_PATH = os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY", "serviceAccountKey.json")
firebase_init_error = None

if not firebase_admin._apps:
    try:
        if os.path.exists(FIREBASE_KEY_PATH):
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        elif os.getenv("FIREBASE_PRIVATE_KEY"):
            # 雲端 Vercel 環境變數模式
            private_key = os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n')
            firebase_config = {
                "type": "service_account",
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key": private_key,
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "token_uri": "https://googleapis.com"
            }
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized successfully")
    except Exception as e:
        firebase_init_error = str(e)
        print(f"Firebase init failed: {e}")

db = firestore.client() if firebase_admin._apps else None

default_admin_emails = "admin@kywc.edu.hk,test1@gmail.com,admin@gmail.com"
ADMIN_EMAILS = [email.strip() for email in os.getenv("ADMIN_EMAILS", default_admin_emails).split(",") if email.strip()]

# ☁️ AWS / E2 S3 客戶端設定
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("E2_ENDPOINT"),
    aws_access_key_id=os.getenv("E2_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("E2_SECRET_KEY")
)
BUCKET_NAME = os.getenv("E2_BUCKET_NAME")
E2_ENDPOINT = os.getenv("E2_ENDPOINT", "").rstrip("/")

def photo_public_url(key: str) -> str:
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET_NAME, "Key": key},
            ExpiresIn=24 * 3600
        )
    except Exception:
        if E2_ENDPOINT and BUCKET_NAME:
            return f"{E2_ENDPOINT}/{BUCKET_NAME}/{key}"
        return key

def normalize_photo_key(photo_key_or_url: str) -> str:
    if not photo_key_or_url:
        return photo_key_or_url
    if photo_key_or_url.startswith("http://") or photo_key_or_url.startswith("https://"):
        parsed = urlparse(photo_key_or_url)
        path = unquote(parsed.path or "")
        bucket_prefix = f"/{BUCKET_NAME}/"
        if path.startswith(bucket_prefix):
            return path[len(bucket_prefix):]
        return path.lstrip("/")
    if E2_ENDPOINT and BUCKET_NAME:
        prefix = f"{E2_ENDPOINT}/{BUCKET_NAME}/"
        if photo_key_or_url.startswith(prefix):
            return photo_key_or_url[len(prefix):]
    return photo_key_or_url

async def verify_admin(authorization: Optional[str] = Header(None)):
    if not firebase_admin._apps:
        raise HTTPException(status_code=503, detail=f"Firebase 未正確初始化: {firebase_init_error}")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供認證憑證")
    token = authorization.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        user_email = decoded_token.get("email")
        if user_email not in ADMIN_EMAILS:
            raise HTTPException(status_code=403, detail="您沒有管理員權限")
        return decoded_token
    except HTTPException as he:
        raise he
    except Exception:
        raise HTTPException(status_code=401, detail="憑證驗證失敗")

# 🛠️ 根目錄路由 (確認後端狀態用)
@app.get("/")
async def root():
    return {"status": "online", "message": "KYWC-3D API running successfully on Vercel"}

# 📸 照片 API 區塊
@app.get("/api/admin/photos")
async def list_photos_admin(admin=Depends(verify_admin)):
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        photos = []
        if "Contents" in response:
            for obj in response["Contents"]:
                photos.append({
                    "key": obj["Key"],
                    "url": photo_public_url(obj["Key"]),
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat()
                })
            photos.sort(key=lambda x: x["last_modified"], reverse=True)
        return photos
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"獲取照片失敗: {str(e)}")

@app.get("/api/photos")
async def list_photos_public():
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        urls = []
        if "Contents" in response:
            items = sorted(response["Contents"], key=lambda x: x["LastModified"])
            for obj in items:
                urls.append(photo_public_url(obj["Key"]))
        return urls
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"獲取公開照片失敗: {str(e)}")

@app.post("/api/admin/photos/upload")
async def upload_photo(file: UploadFile = File(...), admin=Depends(verify_admin)):
    try:
        file_content = await file.read()
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=file.filename,
            Body=file_content,
            ContentType=file.content_type
        )
        return {"message": "上傳成功", "filename": file.filename, "url": photo_public_url(file.filename)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上傳失敗: {str(e)}")

@app.delete("/api/admin/photos/{photo_key:path}")
async def delete_photo(photo_key: str, admin=Depends(verify_admin)):
    try:
        normalized_key = normalize_photo_key(photo_key)
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=normalized_key)
        return {"message": f"已刪除 {normalized_key}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刪除失敗: {str(e)}")

# 🎓 學生管理 API 區塊
@app.get("/api/admin/students")
async def list_students_admin(admin=Depends(verify_admin)):
    if db is None:
        raise HTTPException(status_code=503, detail="Firestore 未初始化")
    try:
        docs = db.collection("students").stream()
        students = []
        for doc_item in docs:
            data = doc_item.to_dict() or {}
            students.append({"id": doc_item.id, **data})
        return students
    except NotFound:
        raise HTTPException(status_code=503, detail="Firestore 資料庫尚未建立")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"讀取學生資料失敗: {str(e)}")

@app.post("/api/admin/students")
async def create_student(payload: dict = Body(...), admin=Depends(verify_admin)):
    if db is None:
        raise HTTPException(status_code=503, detail="Firestore 未初始化")
    email = (payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    name = (payload.get("name") or "").strip()
    class_name = (payload.get("className") or "3D").strip()
    role = (payload.get("role") or "student").strip()

    if not email or not password:
        raise HTTPException(status_code=400, detail="email 與 password 為必填")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="password 至少 6 位")
    try:
        user = auth.create_user(email=email, password=password, display_name=name or None)
        db.collection("students").document(user.uid).set({
            "uid": user.uid,
            "email": email,
            "name": name,
            "className": class_name,
            "role": role,
            "createdBy": admin.get("uid"),
            "createdAt": firestore.SERVER_TIMESTAMP
        }, merge=True)
        return {"message": "學生帳戶建立成功", "uid": user.uid, "email": email}
    except auth.EmailAlreadyExistsError:
        raise HTTPException(status_code=409, detail="此 email 已存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"建立學生帳戶失敗: {str(e)}")

@app.put("/api/admin/students/{uid}")
async def update_student(uid: str, payload: dict = Body(...), admin=Depends(verify_admin)):
    if db is None:
        raise HTTPException(status_code=503, detail="Firestore 未初始化")
    email = payload.get("email")
    name = payload.get("name")
    class_name = payload.get("className")
    role = payload.get("role")
    password = payload.get("password")

    update_auth = {}
    if email is not None:
        update_auth["email"] = str(email).strip()
    if name is not None:
        update_auth["display_name"] = str(name).strip()
    if password:
        if len(str(password)) < 6:
            raise HTTPException(status_code=400, detail="password 至少 6 位")
        update_auth["password"] = str(password)

    firestore_patch = {"updatedBy": admin.get("uid"), "updatedAt": firestore.SERVER_TIMESTAMP}
    if email is not None:
        firestore_patch["email"] = str(email).strip()
    if name is not None:
        firestore_patch["name"] = str(name).strip()
    if class_name is not None:
        firestore_patch["className"] = str(class_name).strip()
    if role is not None:
        firestore_patch["role"] = str(role).strip()

    try:
        if update_auth:
            auth.update_user(uid, **update_auth)
Use code with caution.db.collection("students").document(uid).set(firestore_patch, merge=True)return {"message": "學生資料更新成功", "uid": uid}except auth.UserNotFoundError:raise HTTPException(status_code=404, detail="找不到此學生帳戶")except Exception as e:raise HTTPException(status_code=500, detail=f"更新學生資料失敗: {str(e)}")@app.delete("/api/admin/students/{uid}")async def delete_student(uid: str, admin=Depends(verify_admin)):if db is None:raise HTTPException(status_code=503, detail="Firestore 未初始化")try:db.collection("students").document(uid).delete()auth.delete_user(uid)return {"message": f"學生 {uid} 已刪除"}except auth.UserNotFoundError:db.collection("students").document(uid).delete()return {"message": f"學生 {uid} 已刪除（Auth 帳戶不存在）"}except Exception as e:raise HTTPException(status_code=500, detail=f"刪除學生失敗: {str(e)}")if name == "main":import uvicornapi_port = int(os.getenv("API_PORT", "8001"))uvicorn.run(app, host="0.0.0.0", port=api_port)
