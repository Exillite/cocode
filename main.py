from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
import subprocess
import tempfile
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from jose import JWTError, jwt
from datetime import datetime, timedelta
import uuid
import bcrypt

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

# MongoDB
mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
print(f"Connecting to MongoDB at: {mongodb_url}")
client = AsyncIOMotorClient(mongodb_url)
db = client.cocode
users_collection = db.users
rooms_collection = db.rooms




# Создаем уникальный индекс на username
async def init_db():
    try:
        await users_collection.create_index("username", unique=True)
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

@app.on_event("startup")
async def startup_event():
    await init_db()

# Auth
SECRET_KEY = "your-secret-key-change-this"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class CodeRequest(BaseModel):
    code: str
    inputs: str = ""
    room: str
    script: str

class User(BaseModel):
    username: str
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    password: str

class Room(BaseModel):
    id: str
    name: str
    owner: str
    scripts: Dict[str, str]
    created_at: datetime

class ConnectionManager:
    def __init__(self, name: str = "", room_id: str = ""):
        self.active_connections: List[WebSocket] = []
        self.scripts: Dict[str, str] = {}
        self.name = name
        self.room_id = room_id
        self.processes: Dict[WebSocket, dict] = {}

    async def load_room(self):
        room = await rooms_collection.find_one({"id": self.room_id})
        if room:
            self.scripts = room.get("scripts", {"main.py": "# Введите ваш Python код здесь\nprint('Hello, World!')"})
        else:
            self.scripts = {"main.py": "# Введите ваш Python код здесь\nprint('Hello, World!')"}

    async def save_room(self):
        await rooms_collection.update_one(
            {"id": self.room_id},
            {"$set": {"scripts": self.scripts}},
            upsert=True
        )

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        if not self.scripts:
            await self.load_room()
        self.active_connections.append(websocket)
        # Отправляем все скрипты
        await websocket.send_json({
            "scripts": self.scripts,
            "name": self.name
        })

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        if websocket in self.processes:
            process_info = self.processes[websocket]
            if process_info['process']:
                process_info['process'].kill()
            if process_info['task']:
                process_info['task'].cancel()
            del self.processes[websocket]

    async def broadcast(self, data: dict):
        if "script" in data and "code" in data:
            self.scripts[data["script"]] = data["code"]
        # Отправляем обновление
        full_data = {**data, "scripts": self.scripts, "name": self.name}
        for connection in self.active_connections:
            await connection.send_json(full_data)

    async def delete_script(self, script_name: str):
        if script_name in self.scripts:
            del self.scripts[script_name]
            await self.broadcast({"type": "script_deleted", "script": script_name})

    async def rename_script(self, old_name: str, new_name: str):
        if old_name in self.scripts and new_name not in self.scripts and new_name.endswith('.py'):
            self.scripts[new_name] = self.scripts.pop(old_name)
            await self.broadcast({"type": "script_renamed", "old_name": old_name, "new_name": new_name})

    async def start_process(self, websocket: WebSocket, script_name: str):
        await self.save_room()  # Сохранить перед запуском
        if websocket in self.processes:
            await websocket.send_json({"type": "process_error", "message": "Процесс уже запущен"})
            return
        code = self.scripts.get(script_name, "")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        process = await asyncio.create_subprocess_exec(
            sys.executable or 'python3', '-u', temp_file,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        task = asyncio.create_task(self._monitor_process(websocket, process, temp_file))
        self.processes[websocket] = {
            'process': process,
            'script': script_name,
            'task': task
        }
        await websocket.send_json({"type": "process_started", "script": script_name})

    async def _monitor_process(self, websocket: WebSocket, process, temp_file: str):
        try:
            async def read_stream(stream, kind):
                while True:
                    chunk = await stream.read(1024)
                    if not chunk:
                        break
                    await websocket.send_json({"type": "process_output", "stream": kind, "text": chunk.decode(errors='replace')})

            await asyncio.gather(
                read_stream(process.stdout, 'stdout'),
                read_stream(process.stderr, 'stderr')
            )

            returncode = await process.wait()
            await websocket.send_json({"type": "process_finished", "returncode": returncode})
        finally:
            if process.stdin:
                try:
                    process.stdin.close()
                except Exception:
                    pass
            if websocket in self.processes:
                del self.processes[websocket]
            try:
                os.unlink(temp_file)
            except Exception:
                pass

    async def send_stdin(self, websocket: WebSocket, text: str):
        if websocket not in self.processes or self.processes[websocket]['process'].stdin is None:
            await websocket.send_json({"type": "process_error", "message": "Нет запущенного процесса"})
            return
        try:
            self.processes[websocket]['process'].stdin.write(text.encode())
            await self.processes[websocket]['process'].stdin.drain()
        except Exception:
            await websocket.send_json({"type": "process_error", "message": "Не удалось отправить ввод"})

    async def stop_process(self, websocket: WebSocket):
        if websocket in self.processes:
            process = self.processes[websocket]['process']
            if process:
                process.kill()
                await process.wait()

class RoomRequest(BaseModel):
    name: str

class RenameRequest(BaseModel):
    new_name: str

class JoinRoomRequest(BaseModel):
    room_id: str

# Auth functions
def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )

def get_password_hash(password):
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user(username: str):
    user = await users_collection.find_one({"username": username})
    if user:
        return User(**user)

async def authenticate_user(username: str, password: str):
    user = await get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user(username)
    if user is None:
        raise credentials_exception
    return user.username

# Словарь менеджеров по комнатам
managers: Dict[str, ConnectionManager] = {}

async def get_manager(room: str) -> ConnectionManager:
    if room not in managers:
        # Загрузить из DB если есть
        room_doc = await rooms_collection.find_one({"id": room})
        if room_doc:
            name = room_doc.get("name", "")
            scripts = room_doc.get("scripts", {})
            manager = ConnectionManager(name=name, room_id=room)
            manager.scripts = scripts
            managers[room] = manager
        else:
            managers[room] = ConnectionManager(room_id=room)
    return managers[room]

@app.get("/")
async def get():
    return FileResponse("static/login.html")

@app.post("/register")
async def register(user: UserCreate):
    try:
        existing = await users_collection.find_one({"username": user.username})
        if existing:
            raise HTTPException(status_code=400, detail="Username already registered")
        
        if len(user.password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        
        hashed = get_password_hash(user.password)
        user_dict = {"username": user.username, "hashed_password": hashed}
        await users_collection.insert_one(user_dict)
        return {"message": "User created"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/rooms")
async def get_rooms(current_user: str = Depends(get_current_user)):
    rooms = []
    async for room in rooms_collection.find({
        "$or": [
            {"owner": current_user},
            {"members": current_user}
        ]
    }):
        rooms.append({"id": room["id"], "name": room["name"]})
    return rooms

@app.get("/room/{room_id}")
async def get_room(room_id: str, current_user: str = Depends(get_current_user)):
    room = await rooms_collection.find_one({"id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"id": room["id"], "name": room["name"]}

@app.post("/create-room")
async def create_room(request: RoomRequest, current_user: str = Depends(get_current_user)):
    room_id = str(uuid.uuid4())
    room_dict = {
        "id": room_id,
        "name": request.name,
        "owner": current_user,
        "members": [current_user],
        "scripts": {"main.py": "# Введите ваш Python код здесь\nprint('Hello, World!')"},
        "created_at": datetime.utcnow()
    }
    await rooms_collection.insert_one(room_dict)
    manager = ConnectionManager(name=request.name, room_id=room_id)
    manager.scripts = room_dict["scripts"]
    managers[room_id] = manager
    return {"id": room_id}

@app.post("/join-room")
async def join_room(request: JoinRoomRequest, current_user: str = Depends(get_current_user)):
    room = await rooms_collection.find_one({"id": request.room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    await rooms_collection.update_one(
        {"id": request.room_id},
        {"$addToSet": {"members": current_user}}
    )

    return {"id": room["id"], "name": room["name"]}

@app.websocket("/ws/{room}")
async def websocket_endpoint(room: str, websocket: WebSocket):
    manager = await get_manager(room)
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get('type') == 'run_script':
                await manager.start_process(websocket, data.get('script', ''))
            elif data.get('type') == 'stdin':
                await manager.send_stdin(websocket, data.get('input', ''))
            elif data.get('type') == 'stop_script':
                await manager.stop_process(websocket)
            elif data.get('type') == 'save':
                await manager.save_room()
                await websocket.send_json({"type": "saved"})
            else:
                await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/run-code")
async def run_code(request: CodeRequest):
    manager = await get_manager(request.room)
    code = manager.scripts.get(request.script, "")
    try:
        # Создаем временный файл с кодом
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name

        # Запускаем код с входными данными
        process = subprocess.run(
            ['python3', temp_file],
            input=request.inputs,
            text=True,
            capture_output=True,
            timeout=10  # таймаут 10 секунд
        )

        # Удаляем временный файл
        os.unlink(temp_file)

        output = process.stdout
        error = process.stderr

        if process.returncode != 0:
            return {"output": output, "error": error, "success": False}
        else:
            return {"output": output, "error": error, "success": True}

    except subprocess.TimeoutExpired:
        return {"output": "", "error": "Timeout: код выполнялся слишком долго", "success": False}
    except Exception as e:
        return {"output": "", "error": f"Ошибка: {str(e)}", "success": False}

@app.delete("/room/{room}/script/{script_name}")
async def delete_script(room: str, script_name: str):
    manager = await get_manager(room)
    await manager.delete_script(script_name)
    return {"success": True}

@app.put("/room/{room}/script/{script_name}")
async def rename_script(room: str, script_name: str, request: RenameRequest):
    manager = await get_manager(room)
    await manager.rename_script(script_name, request.new_name)
    return {"success": True}
