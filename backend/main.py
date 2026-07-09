import os
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Configuración de Base de Datos
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./parking_local.db") # Fallback a SQLite para desarrollo local

# Si se usa SQLite local, se necesita un parámetro especial para check_same_thread
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelos SQLAlchemy
class EstadoEstacionamiento(Base):
    __tablename__ = "estado_estacionamiento"
    
    id = Column(Integer, primary_key=True, index=True)
    carros_adentro = Column(Integer, default=0)
    ultima_actualizacion = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RegistroClima(Base):
    __tablename__ = "registro_clima"
    
    id = Column(Integer, primary_key=True, index=True)
    temperatura = Column(Float)
    humedad = Column(Float)
    fecha_hora = Column(DateTime, default=datetime.utcnow)

# Crear las tablas en la BD
Base.metadata.create_all(bind=engine)

# Aplicación FastAPI
app = FastAPI(title="API IoT - Parking & Clima")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permitir peticiones de cualquier frontend (para desarrollo)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependencia para inyectar la sesión de BD
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Schemas Pydantic para validar entradas
class CarrosUpdate(BaseModel):
    carros_adentro: int

class ClimaCreate(BaseModel):
    temperatura: float
    humedad: float

# Variable en memoria RAM para el clima en tiempo real
clima_live = {
    "temperatura": None,
    "humedad": None,
    "fecha_hora": None
}

# Endpoints
@app.post("/api/carros")
def actualizar_carros(data: CarrosUpdate, db: Session = Depends(get_db)):
    estado = db.query(EstadoEstacionamiento).first()
    if not estado:
        estado = EstadoEstacionamiento(carros_adentro=data.carros_adentro)
        db.add(estado)
    else:
        estado.carros_adentro = data.carros_adentro
    
    db.commit()
    db.refresh(estado)
    return {"message": "Estado del estacionamiento actualizado", "carros_adentro": estado.carros_adentro}

@app.get("/api/estado")
def obtener_estado(db: Session = Depends(get_db)):
    estado = db.query(EstadoEstacionamiento).first()
    if not estado:
        return {"carros_adentro": 0, "ultima_actualizacion": None}
    return {
        "carros_adentro": estado.carros_adentro,
        "ultima_actualizacion": estado.ultima_actualizacion
    }

@app.post("/api/clima")
def registrar_clima(data: ClimaCreate, db: Session = Depends(get_db)):
    global clima_live
    ahora = datetime.utcnow()
    
    # 1. SIEMPRE actualizamos la memoria RAM (Para que el frontend lo vea en tiempo real)
    clima_live["temperatura"] = data.temperatura
    clima_live["humedad"] = data.humedad
    clima_live["fecha_hora"] = ahora
    
    # 2. Verificamos la Base de Datos para ver si ya pasó 1 minuto
    ultimo_registro = db.query(RegistroClima).order_by(RegistroClima.id.desc()).first()
    
    guardar_en_bd = False
    if not ultimo_registro:
        guardar_en_bd = True # Si la BD está vacía, guardamos el primer registro
    else:
        # Calculamos los segundos que han pasado desde el último guardado
        diferencia_segundos = (ahora - ultimo_registro.fecha_hora).total_seconds()
        if diferencia_segundos >= 60:
            guardar_en_bd = True
            
    # 3. Solo escribimos en el disco (PostgreSQL/SQLite) si pasó 1 minuto
    if guardar_en_bd:
        nuevo_clima = RegistroClima(temperatura=data.temperatura, humedad=data.humedad, fecha_hora=ahora)
        db.add(nuevo_clima)
        db.commit()
        return {"message": "Clima guardado en la BD y en memoria", "bd_saved": True}
    
    return {"message": "Clima actualizado solo en memoria (Tiempo real)", "bd_saved": False}

@app.get("/api/dashboard")
def obtener_dashboard(db: Session = Depends(get_db)):
    # 1. Carros actuales (Este sigue consultando la BD porque cambia poco)
    estado = db.query(EstadoEstacionamiento).first()
    carros = estado.carros_adentro if estado else 0
    
    # 2. Último registro de clima (Lo sacamos directo de la RAM, es más rápido)
    global clima_live
    
    # Si la memoria RAM acaba de despertar (está vacía), jalamos el último dato de la BD por si acaso
    if clima_live["temperatura"] is None:
        ultimo_clima = db.query(RegistroClima).order_by(RegistroClima.id.desc()).first()
        if ultimo_clima:
            clima_live["temperatura"] = ultimo_clima.temperatura
            clima_live["humedad"] = ultimo_clima.humedad
            clima_live["fecha_hora"] = ultimo_clima.fecha_hora

    return {
        "carros_actuales": carros,
        "ultimo_clima": clima_live
    }

@app.get("/api/clima/historial")
def obtener_historial_clima(db: Session = Depends(get_db)):
    # Obtener los últimos 15 registros ordenados por id descendente (o fecha_hora)
    registros = db.query(RegistroClima).order_by(RegistroClima.id.desc()).limit(15).all()
    # Invertir para devolverlos en orden cronológico (más antiguo primero)
    return registros[::-1]