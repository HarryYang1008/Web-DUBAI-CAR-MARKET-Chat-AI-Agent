import streamlit as st
import pandas as pd
import os
import re
from openai import OpenAI

# 初始化 OpenAI 客户端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Dubai Car Market Q&A", layout="wide")
st.title("🚗 Dubai Used Car Price Assistant")

# ---------------------- 🔘 文件信息按钮 ----------------------
with st.expander("🗂️ Show Data File Info"):
    if "current_filename" in st.session_state:
        st.write(f"**Current file name:** `{st.session_state['current_filename']}`")
    else:
        st.warning("No file has been loaded yet.")
# ------------------------------------------------------------

# ---------------------- 数据加载 ----------------------------
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
# ------------------------------------------------------------

if df is not None:
    with st.expander("🔍 Preview Data"):
        st.dataframe(df.head())

    user_question = st.text_input("Ask a question about the car market:", placeholder="e.g., What Audi models are available?")

    if user_question and st.button("🔎 Analyze"):
        with st.spinner("Analyzing data with GPT-4..."):

            # 数据预处理
            required_cols = ['Brand', 'Model', 'Price', 'Year', 'Kilometers']
            if not all(col in df.columns for col in required_cols):
                st.error(f"Missing required columns: {required_cols}")
            else:
                data = df[required_cols].dropna().copy()
                data['Price'] = data['Price'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)
                data['Kilometers'] = data['Kilometers'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)

                # --- 关键词提取逻辑 ---
                brands = data["Brand"].dropna().unique().tolist()
                brand_match = None
                for brand in brands:
                    if re.search(rf"\b{re.escape(brand)}\b", user_question, re.IGNORECASE):
                        brand_match = brand
                        break

                if brand_match:
                    filtered = data[data["Brand"].str.contains(brand_match, case=False)]
                    prompt_data = filtered
                    st.info(f"📌 Detected brand in question: **{brand_match}**. Analyzing full {len(filtered)} records.")
                else:
                    prompt_data = data.sample(min(100, len(data)))
                    st.info(f"⚠️ No specific brand detected. Using random sample of {len(prompt_data)} records.")

                # 构建分析 Prompt
                prompt = f"""
You are a professional car market analyst in Dubai.

A user asked: "{user_question}"

Please perform the following:

1. Analyze the dataset and answer the user's question in detail.
2. Identify and list **all models** under the mentioned brand.
3. Create a Markdown table showing average price (AED), year, and mileage for each model.
4. Then, provide **a short analysis**, highlighting:
   - Which models tend to be the most expensive and why?
   - Which ones appear to be high mileage vs low mileage?
   - Any interesting market trend (e.g., newer models dropping in price, older models still expensive, etc.)
5. If relevant, give recommendations (e.g., which model offers best value based on price vs mileage vs year).

Use the following dataset (columns: Brand, Model, Year, Price, Kilometers):

{prompt_data.to_csv(index=False)}
"""

                # GPT 调用
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a data analyst specialized in car market trends in Dubai."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )

                st.markdown("### 📊 GPT-4 Analysis Result")
                st.markdown(response.choices[0].message.content)
