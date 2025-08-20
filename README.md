# Course Q&A Agent (ADK) — KelasFullstack + Google Search

Agent multi-fungsi berbasis **Google ADK (Agent Development Kit)** buat:
- **Tanya–jawab kelas** KelasFullstack dari **API Codepolitan**  
- **Web lookup** via **Google Search (built-in tool)** untuk info pelengkap

> Catatan: **Google Search (built-in)** nggak boleh dicampur bareng tools lain di satu agent. Jadi repo ini pakai **dua agent terpisah**:
> 1) `kfs_course_agent` (khusus API kursus)  
> 2) `kfs_search_agent` (khusus Google Search)

---

## ✨ Fitur Utama

- **Index & Query Kursus** dari `https://api.codepolitan.com/course?page=1&limit=1000`
- **Normalisasi field** sesuai struktur JSON (lihat “Skema Data”)
- **Pencarian fuzzy** by `query`, `level`, `topic`, `author`, `premium`, `max_price`
- **Detail by slug/judul**, quick preview, dan rekomendasi berdasar **user preferences**
- **Caching** hasil fetch (TTL default 6 jam)
- **Agent terpisah** untuk **Google Search grounding** (Gemini 2)

---

## 🧱 Prasyarat

- Python **3.10+**
- API key **Google AI Studio** (Gemini 2)
- `pip`, `venv` (opsional tapi direkomendasikan)

---

## 🚀 Quickstart

```bash
# 1) Setup environment
python -m venv .venv
# Windows PowerShell
. .\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

# 2) Install deps
pip install google-adk requests

# 3) Struktur direktori (contoh)
adk_apps/
  kfs_course_agent/
    __init__.py
    agent.py
    .env
  kfs_search_agent/
    __init__.py
    agent.py
    .env

# 4) Konfigurasi .env (kedua agent)
# file: adk_apps/kfs_course_agent/.env
# file: adk_apps/kfs_search_agent/.env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=PASTE_API_KEY_GEMINI
```

### Jalankan UI/CLI
```bash
# Dev UI (pilih agent yang ingin dites)
adk web

# Atau jalankan satu agent via CLI
adk run kfs_course_agent
adk run kfs_search_agent
```

---

## 🧩 Arsitektur & Alur

```
adk_apps/
├─ kfs_course_agent/
│  ├─ agent.py        # Tools: refresh_courses, search_courses, get_course_detail,
│  │                  #        set_user_pref, recommend_for_user
│  └─ .env            # GOOGLE_API_KEY, dll.
└─ kfs_search_agent/
   ├─ agent.py        # Tools: google_search (built-in ADK)
   └─ .env
```

- **kfs_course_agent**: fokus **API kursus** (Codepolitan → KelasFullstack), stateful (menyimpan preferensi user di session state).
- **kfs_search_agent**: fokus **Google Search** (grounded answers), **tidak** dicampur tool lain.

---

## 🗃️ Skema Data (Disamakan dengan Contoh)

Contoh item kursus (API → dinormalisasi **tanpa mengubah nama field utama**):

```json
{
  "id": 421,
  "title": "Mengembangkan Aplikasi Restoran berbasis QR dengan Laravel 12 + Copilot AI",
  "mentor_username": null,
  "slug": "mengembangkan-aplikasi-restoran-berbasis-qr-dengan-laravel-12",
  "cover": "https://image.web.id/images/Mengembangkan-Aplikasi-Restoran-berbasis-QR-dengan-Laravel-12.png",
  "thumbnail": "https://image.web.id/images/Mengembangkan-Aplikasi-Restoran-berbasis-QR-dengan-Laravel-12.png",
  "description": "Kelas ini akan membimbing kamu ...",
  "seo_description": null,
  "premium": 1,
  "status": "publish",
  "total_module": 46,
  "total_time": 2,
  "total_student": 0,
  "level": "beginner",
  "author": "Aditya Fakhri Riansyah",
  "popular": null,
  "total_feedback": 0,
  "total_rating": 0,
  "normal_price": 350000,
  "retail_price": 249000,
  "buy": {
    "id": 738,
    "product_slug": "mengembangkan-aplikasi-restoran-berbasis-qr-dengan-laravel-12",
    "normal_price": 350000,
    "retail_price": 249000
  },
  "rent": {
    "id": 740,
    "product_slug": "mengembangkan-aplikasi-restoran-berbasis-qr-dengan-laravel-12-1-bulan",
    "normal_price": 149000,
    "retail_price": 99000
  },
  "labels": "Laravel, PHP, Framework"
}
```

> Di agent, `labels` otomatis di-split jadi **list** (e.g. `["Laravel","PHP","Framework"]`) supaya gampang difilter.

---

## 🛠️ Tools yang Tersedia

### Di `kfs_course_agent`
- `refresh_courses()`  
  Refresh cache dari API.  
  **Return**: `{status, count}`

- `search_courses(query=None, level=None, topic=None, max_price=None, premium=None, author=None, limit=10)`  
  Cari kursus berdasarkan teks & filter.  
  **Return**: `{status, results:[{id,title,slug,level,labels,retail_price,normal_price,premium,author,preview,score}], total_indexed}`

- `get_course_detail(slug_or_title)`  
  Ambil **1** kursus by **slug** (prioritas) atau potongan **judul**.  
  **Return**: `{status, course:{…}}`

- `set_user_pref(preferred_topic=None, preferred_level=None, budget_max=None, prefer_premium=None)`  
  Simpan preferensi user (disimpan di state).  
  **Return**: `{status, saved:{…}}`

- `recommend_for_user(limit=5)`  
  Rekomendasi berdasar preferensi tersimpan.  
  **Return**: `{status, recommendations:[…], prefs:{…}}`

### Di `kfs_search_agent`
- `google_search` (built-in ADK, **Gemini 2 only**)  
  Lakukan pencarian web yang grounded.  
  > **Batasan penting:** built-in tools **tidak boleh** dipakai bareng tools custom lain di agent yang sama / sub-agent.

---

## 🧪 Contoh Penggunaan (Prompt)

**Course Agent**
- “Ada kelas **Laravel** untuk **pemula** di bawah **300k**?”
- “Detail kelas slug **mengembangkan-aplikasi-restoran-berbasis-qr-dengan-laravel-12**.”
- “Aku prefer **Tailwind**, **beginner**, budget **150k**. Simpan & rekomen.”
- “Refresh data terbaru.”

**Search Agent**
- “Cari update terbaru tentang ‘Laravel 12 features’ dari sumber tepercaya.”
- “Ringkasin hasil web terkait **QRIS Midtrans Laravel**.”

---

## ⚙️ Konfigurasi

- **API endpoint**: `https://api.codepolitan.com/course?page=1&limit=1000`  
  (Bisa diubah di `API_URL` dalam `kfs_course_agent/agent.py`)
- **TTL cache**: default **6 jam** (ubah di `_ensure_index`)
- **Model**: `gemini-2.0-flash` (disarankan untuk kecepatan + kompatibilitas search)

---

## 🧯 Troubleshooting

- **`HTTP 4xx/5xx` saat fetch kursus**  
  Cek koneksi, rate limit, atau ubah `timeout` di helper `_http_get_json`.
- **Pencarian nggak nemu padahal datanya ada**  
  Coba lebih spesifik (pakai `slug`), atau kurangi filter (`level`, `premium`, `max_price`).
- **Google Search tool error**  
  Pastikan agent model = **Gemini 2**, dan agent **khusus** untuk search (tidak ada tools lain).
- **Env key tidak kebaca**  
  Pastikan file `.env` ada di **folder agent** yang sesuai dan variabel tepat (`GOOGLE_API_KEY`).

---

## 🧰 Kustomisasi Cepat

- **Bobot skor fuzzy**: atur fungsi `_score` (tuning relevansi).
- **Field mapping**: jika API menambah field baru, extend `_normalize_course`.
- **Preferensi user**: tambahkan sinyal lain (mis. `labels` tertentu, durasi, dll).

---

## 🗺️ Roadmap

- [ ] Router otomatis (pilih Course/Search Agent berdasar intent)  
- [ ] Pagination & incremental refresh  
- [ ] Sorting (harga, rating, populer)  
- [ ] Filter `labels` via AND/OR

---

## 🤝 Kontribusi

PR & issue welcome. Ikuti style yang ada (PEP8, docstring singkat, fungsi pure di helpers).

---

## 📄 Lisensi

MIT (atau sesuaikan kebutuhan projek lo).

---

## 🙏 Kredit

- **Google ADK** untuk kerangka agent + built-in tools  
- **Codepolitan/KelasFullstack** untuk API kursus

---

## 🔎 Lampiran: Contoh Query CLI (opsional)

```bash
# Cek respons API mentah
curl -s "https://api.codepolitan.com/course?page=1&limit=1000" | head -c 800

# Jalankan agent Course di CLI
adk run kfs_course_agent

# Jalankan agent Search di CLI
adk run kfs_search_agent
```
