# RAG DevOps Project: AI สนับสนุนงานพ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA)

ระบบ Retrieval-Augmented Generation (RAG) เพื่อช่วยค้นหาและวิเคราะห์ข้อมูลเกี่ยวกับกฎหมายคุ้มครองข้อมูลส่วนบุคคล (PDPA) ของไทย

## การติดตั้ง Docker Desktop

ก่อนเริ่มใช้งานระบบ คุณต้องติดตั้ง Docker Desktop ในเครื่องของคุณ

### สำหรับ Windows

1. ดาวน์โหลด Docker Desktop สำหรับ Windows จาก [เว็บไซต์อย่างเป็นทางการ](https://www.docker.com/products/docker-desktop)
2. เปิดไฟล์ติดตั้งและทำตามขั้นตอนที่แสดงบนหน้าจอ
3. หากระบบแจ้งเตือนเกี่ยวกับ WSL 2 ให้ติดตั้งตามที่แนะนำ
4. หลังจากติดตั้งเสร็จสิ้น ให้รีสตาร์ทเครื่อง
5. เปิด Docker Desktop และตรวจสอบว่าสถานะเป็น "Docker is running"

### สำหรับ macOS

1. ดาวน์โหลด Docker Desktop สำหรับ Mac จาก [เว็บไซต์อย่างเป็นทางการ](https://www.docker.com/products/docker-desktop)
2. ลาก Docker.app ไปยังโฟลเดอร์ Applications
3. เปิด Docker จากโฟลเดอร์ Applications
4. เมื่อได้รับแจ้งให้อนุญาตการใช้งาน privileges ให้ป้อนรหัสผ่าน
5. รอจนกระทั่ง Docker เริ่มต้นเสร็จสิ้นและสถานะแสดง "Docker is running"

### การตรวจสอบการติดตั้ง

เปิด Terminal (macOS) หรือ Command Prompt (Windows) และรันคำสั่งต่อไปนี้:

```bash
docker --version
docker-compose --version
```

หากคำสั่งแสดงเวอร์ชัน แสดงว่าการติดตั้งสำเร็จและพร้อมใช้งาน

## ส่วนประกอบหลัก

ระบบนี้ประกอบด้วย 3 ส่วนหลัก:

1. **Embedding Service**: ทำหน้าที่อ่านเอกสาร PDF และแปลงเป็น vector embeddings เพื่อเก็บลงใน OpenSearch
2. **API Service**: ให้บริการ API สำหรับค้นหาข้อมูลใน OpenSearch ด้วยวิธี text search
3. **App Service**: หน้าเว็บแอปพลิเคชัน Streamlit สำหรับผู้ใช้งาน ช่วยในการค้นหาข้อมูลและวิเคราะห์โดยใช้ LLM (Ollama)

## การตั้งค่าภายนอก

ระบบนี้ใช้บริการภายนอกสองบริการ:
- **OpenSearch**: สำหรับเก็บและค้นหา vector embeddings (http://113.53.253.39:9200)
- **Ollama**: สำหรับรัน LLM ท้องถิ่น (http://113.53.253.39:11434)

## วิธีการรัน

### การรันแบบ Docker

```bash
# สร้าง Docker network
docker network create rag-network

# รันระบบด้วย Docker Compose
docker-compose up -d
```

สามารถเข้าถึงหน้าเว็บแอปพลิเคชันได้ที่ http://localhost:8501

## การใช้งาน

1. เข้าสู่เว็บแอปพลิเคชันที่ http://localhost:8501
2. พิมพ์คำถามเกี่ยวกับ PDPA ในช่องค้นหา
3. กดปุ่ม "ค้นหา" เพื่อดึงข้อมูลที่เกี่ยวข้องจากเอกสาร
4. กดปุ่ม "วิเคราะห์" เพื่อใช้ AI วิเคราะห์ข้อมูลที่ได้และตอบคำถาม

## หมายเหตุ

- ระบบนี้ใช้ Qwen2:0.5b เป็นโมเดล LLM ผ่าน Ollama API
- ระบบถูกออกแบบให้ขยายได้ด้วยการเพิ่มเอกสาร PDF ในโฟลเดอร์ pdf_corpus
- ในการทำงานปกติ Embedding Service จะรันเพียงครั้งเดียวเพื่อสร้าง embeddings จากนั้นจะหยุดทำงาน

## Branches

- main: โค้ดต้นฉบับ
- complete: โค้ดต้นฉบับพร้อม Dockerfile และ docker-compose.yml