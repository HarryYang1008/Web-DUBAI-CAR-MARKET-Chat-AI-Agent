import streamlit as st
import pandas as pd
import os
from openai import OpenAI

# 初始化 OpenAI 客户端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Dubai Car Market Q&A", layout="wide")
st.title("🚗 Dubai Used Car Price Assistant")

# ---------------------- 🔘 文件信息弹窗按钮 ----------------------
if st.button("🗂️ Show Data File Info"):
    with st.modal("📄 Loaded File Info", close_on_click=True):
        if "current_filename" in st.session_state:
            st.write(f"**Current file name:** `{st.session_state['current_filename']}`")
        else:
            st.warning("No file has been loaded yet.")
# ---------------------------------------------------------------

# ---------------------- 🔽 数据来源选择 ------------------------
data_source = st.radio("Select data source", ["📂 Upload CSV", "🌐 Load from GitHub"])
df = None

if data_source == "📂 Upload CSV":
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        st.session_state["current_filename"] = uploaded_file.name
        st.success(f"✅ Uploaded: {uploaded_file.name} ({df.shape[0]} rows)")

elif data_source == "🌐 Load from GitHub":
    github_url = st.text_input("Paste raw GitHub CSV URL")
    if github_url:
        try:
            df = pd.read_csv(github_url)
            filename = github_url.split("/")[-1]
            st.session_state["current_filename"] = filename
            st.success(f"✅ Loaded: {filename} ({df.shape[0]} rows)")
        except Exception as e:
            st.error(f"❌ Failed to load from GitHub: {e}")
# ---------------------------------------------------------------

# ---------------------- ❓ 用户提问并分析 -----------------------
if df is not None:
    with st.expander("🔍 Preview Data"):
        st.dataframe(df.head())

    user_question = st.text_input("Ask a question about the car market:", placeholder="e.g., What's the price trend for Camry?")

    if user_question and st.button("🔎 Analyze"):
        with st.spinner("Analyzing data with GPT-4..."):

            # 数据清洗
            target_cols = ['Brand', 'Model', 'Price', 'Year', 'Kilometers']
            if not all(col in df.columns for col in target_cols):
                st.error(f"Missing required columns in uploaded file: {target_cols}")
            else:
                filtered_df = df[target_cols].dropna().copy()
                filtered_df['Price'] = filtered_df['Price'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)
                filtered_df['Kilometers'] = filtered_df['Kilometers'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)

                # 选取样本避免 token 超限
                sample_df = filtered_df.sample(min(100, len(filtered_df)))

                # 构建 Prompt
                prompt = f"""
You are a car market analyst. Analyze the following dataset based on this user question: "{user_question}".

Summarize price trends, model-year variations, and mileage impact. If the user asked about a specific brand/model (e.g., Camry), focus on those.

Here is the dataset (Brand, Model, Year, Price in AED, Kilometers):

{sample_df.to_csv(index=False)}

Return a clear summary and use Markdown tables if helpful.
"""

                # OpenAI 请求
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a data analyst specialized in car market trends in Dubai."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )

                st.markdown("### 📊 Analysis Result")
                st.markdown(response.choices[0].message.content)
# ---------------------------------------------------------------
