# FarmaScan 🏥

Sistema de escaneo de inventario para farmacia. Procesa archivos xlsx/csv de 1M+ filas y permite buscar productos por código LPN con un escáner Zebra.

## Estructura del proyecto

```
farmascan/
├── backend/          # Python 3.12 + FastAPI (3 capas)
├── frontend/         # Angular 18 (Standalone)
└── docker-compose.yml
```

---

## Desarrollo local

### Opción A: Docker Compose (recomendado)

```bash
docker compose up --build
# Backend:  http://localhost:8000/docs
# Frontend: http://localhost:80
```

### Opción B: Manual

**Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm start                    # http://localhost:4200
```

---

## Configuración del escáner Zebra (DataWedge)

El escáner MC9200 con DataWedge debe configurarse en modo **Keystroke Output**:

1. Abrir **DataWedge** en el escáner
2. Crear un nuevo perfil → "FarmaScan"
3. Asociar la aplicación: Browser (Internet Explorer o Chrome)
4. Keystroke Output → **Enable** ✓
5. Key Event Options → agregar sufijo: **Enter** (tecla Enter al final)
6. Abrir el browser en el escáner y navegar a la URL de la app

Con esto, cuando el operador escanea un código, DataWedge lo envía automáticamente al campo de búsqueda + presiona Enter → búsqueda automática.

---

## API Endpoints

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/inventory/search/{lpn_code}` | Buscar por LPN (escáner) |
| `POST` | `/inventory/upload` | Subir archivo xlsx/csv |
| `GET` | `/inventory/upload/jobs/{job_id}` | Estado del procesamiento |

Documentación interactiva: `http://localhost:8000/docs`

---

## Cálculo de Curvas

La curva se calcula automáticamente desde el mismo archivo xlsx:
- El archivo debe tener **2 hojas**: la de inventario y la tabla de referencia
- La tabla de referencia usa la columna B como clave (código producto) y columna G como valor (curva A/B/C)
- Si no se encuentra el producto: retorna `"0"`
- Equivalente al Excel: `=SI.ERROR(BUSCARV(C2,Ref!$B$2:$G$12921,6,0),0)`

El nombre de la hoja de referencia se configura en `.env`:
```
CURVA_REFERENCE_SHEET=Curvas   # nombre exacto de la hoja
CURVA_LOOKUP_KEY_COL=1         # columna B (0-indexed)
CURVA_RESULT_COL=5             # columna G (0-indexed)
```

---

## Deploy en producción

### Backend → Heroku (Docker)

```bash
heroku login
heroku create farmascan-api
heroku container:push web -a farmascan-api
heroku container:release web -a farmascan-api

# Variables de entorno en Heroku:
heroku config:set DATABASE_URL="postgresql+asyncpg://..." -a farmascan-api
heroku config:set CORS_ORIGINS='["https://farmascan.netlify.app"]' -a farmascan-api
```

### Frontend → Netlify

1. Actualizar `frontend/src/environments/environment.prod.ts` con la URL de Heroku
2. Build: `npm run build -- --configuration=production`
3. Subir `frontend/dist/frontend/browser/` a Netlify

### Base de datos → Supabase

Actualizar `DATABASE_URL` en Heroku:
```
postgresql+asyncpg://postgres:[password]@[host]:5432/postgres
```
