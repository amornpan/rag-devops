import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
from os import getenv

# Configure timeouts and settings
SEARCH_TIMEOUT = 30
OLLAMA_TIMEOUT = 120
MODEL_NAME = getenv("MODEL_NAME", "qwen2:0.5b")
API_URL = getenv("API_URL","http://api:8000")
OLLAMA_URL = getenv("OLLAMA_URL", "http://ollama:11434")

# Setup session with retries
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)

http = requests.Session()
adapter = HTTPAdapter(max_retries=retry_strategy)
http.mount("http://", adapter)
http.mount("https://", adapter)

# Streamlit UI
st.title("AI สนับสนุนความรู้ด้านการดูแลรักษาโครงข่าย Fiber Optic")

# Initialize session state
if "search_results" not in st.session_state:
    st.session_state.search_results = None
if "llm_response" not in st.session_state:
    st.session_state.llm_response = None

def check_api_health():
    """Check if API is healthy"""
    try:
        response = http.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def ensure_model_loaded():
    """Ensure the LLM model is loaded"""
    try:
        response = http.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = response.json().get("models", [])
        if not any(m.get("name") == MODEL_NAME for m in models):
            st.warning(f"กำลังโหลดโมเดล {MODEL_NAME}...")
            response = http.post(
                f"{OLLAMA_URL}/api/pull",
                json={"name": MODEL_NAME},
                timeout=600
            )
            return response.status_code == 200
        return True
    except Exception as e:
        st.error(f"ไม่สามารถโหลดโมเดลได้: {str(e)}")
        return False

def get_ollama_response(prompt):
    """Get response from Ollama"""
    llm_payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.5,
            "top_k": 40,
            "top_p": 0.9,
            "num_ctx": 1024,
            "num_thread": 4,
            "stop": ["</s>", "Human:", "Assistant:", "[/INST]"],
        }
    }
    
    try:
        response = http.post(
            f"{OLLAMA_URL}/api/generate",
            json=llm_payload,
            timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("response", "")
    except Exception as e:
        st.error(f"Error calling Ollama: {str(e)}")
        return None

# Create two columns
left_col, right_col = st.columns([3, 2])

with left_col:
    st.subheader("ค้นหาข้อมูล")
    user_input = st.text_input("คำถาม:", key="input")

    if st.button("ค้นหา"):
        if user_input:
            try:
                # Check API health
                if not check_api_health():
                    st.error("ไม่สามารถเชื่อมต่อกับ API ได้")
                    st.stop()

                with st.spinner('กำลังค้นหาข้อมูล...'):
                    response = http.post(
                        f"{API_URL}/search",
                        json={"query": user_input},
                        timeout=SEARCH_TIMEOUT
                    )
                    response.raise_for_status()
                    data = response.json()
                    st.session_state.search_results = data["results"]
                    st.success("ค้นพบข้อมูลที่เกี่ยวข้อง")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการค้นหา: {str(e)}")

    # Display search results
    if st.session_state.search_results:
        st.subheader("ผลการค้นหา")
        for i, result in enumerate(st.session_state.search_results, 1):
            with st.expander(f"ผลลัพธ์ที่ {i}"):
                st.write("**ข้อความ:**")
                st.write(result['text'])
                st.write("**ที่มา:**", result['file_path'])
                st.write("**คะแนนความเกี่ยวข้อง:**", f"{result['score']:.2f}")

with right_col:
    st.subheader("วิเคราะห์ด้วย AI")
    
    if st.button("วิเคราะห์", disabled=not st.session_state.search_results):
        if st.session_state.search_results:
            try:
                # Ensure model is loaded
                if not ensure_model_loaded():
                    st.error("ไม่สามารถโหลดโมเดล AI ได้")
                    st.stop()

                with st.spinner('กำลังวิเคราะห์ข้อมูล...'):
                    # ใช้เฉพาะ 2 ผลลัพธ์แรกที่มีคะแนนสูงสุด
                    sorted_results = sorted(
                        st.session_state.search_results,
                        key=lambda x: x['score'],
                        reverse=True
                    )[:2]
                    
                    context = "\n\n".join([
                        f"ข้อความ: {result['text']}\n"
                        f"ที่มา: {result['file_path']}"
                        for result in sorted_results
                    ])
                    
                    # Qwen2 specific prompt format
                    prompt = (
                        "<|im_start|>system\n"
                        "คุณเป็นผู้เชี่ยวชาญด้านการดูแลรักษาโครงข่าย Fiber Optic จะตอบคำถามโดยใช้ข้อมูลที่ให้มาเท่านั้น\n"
                        "<|im_end|>\n"
                        f"<|im_start|>user\nคำถาม: {user_input}\n\nข้อมูลอ้างอิง:\n{context}<|im_end|>\n"
                        "<|im_start|>assistant\n"
                    )

                    response_text = get_ollama_response(prompt)
                    if response_text:
                        st.session_state.llm_response = response_text.strip()
                        st.success("วิเคราะห์ข้อมูลเสร็จสิ้น")
                    else:
                        st.error("ไม่สามารถวิเคราะห์ข้อมูลได้ กรุณาลองใหม่อีกครั้ง")
                    
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดในการวิเคราะห์: {str(e)}")
                
    # Display LLM response
    if st.session_state.llm_response:
        st.subheader("ผลการวิเคราะห์")
        st.markdown(st.session_state.llm_response)

# Clear results button
if st.button("ล้างผลการค้นหา"):
    st.session_state.search_results = None
    st.session_state.llm_response = None
    st.experimental_rerun()