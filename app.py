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
with st.expander("📂 Show Data File Info"):
    if "current_filename" in st.session_state:
        st.write(f"**Current file name:** `{st.session_state['current_filename']}`")
    else:
        st.warning("No file has been loaded yet.")

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

if df is not None:
    with st.expander("🔍 Preview Data"):
        st.dataframe(df.head())

    user_question = st.text_input("Ask a question about the car market:", placeholder="e.g., What Audi models are available?")

    if user_question and st.button("🔎 Analyze"):
        with st.spinner("Analyzing data with GPT-4..."):

            required_cols = ['Brand', 'Model', 'Price', 'Year', 'Kilometers']
            if not all(col in df.columns for col in required_cols):
                st.error(f"Missing required columns: {required_cols}")
            else:
                data = df[required_cols].dropna().copy()
                data['Price'] = data['Price'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)
                data['Kilometers'] = data['Kilometers'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)

                general_keywords = ['overall', 'market', 'all brands', 'general trend', 'whole market', 'total', '总览', '整体', '全部', '所有', '市场', '平均']
                is_general = any(kw.lower() in user_question.lower() for kw in general_keywords)

                if is_general:
                    brand_summary = data.groupby("Brand").agg({
                        "Model": "nunique",
                        "Price": ["mean", "min", "max"],
                        "Year": "mean",
                        "Kilometers": "mean"
                    }).reset_index()

                    brand_summary.columns = ['Brand', 'Model Count', 'Avg Price', 'Min Price', 'Max Price', 'Avg Year', 'Avg Km']

                    overall = pd.DataFrame({
                        'Brand': ['Overall'],
                        'Model Count': [brand_summary['Model Count'].sum()],
                        'Avg Price': [data['Price'].mean()],
                        'Min Price': [data['Price'].min()],
                        'Max Price': [data['Price'].max()],
                        'Avg Year': [data['Year'].mean()],
                        'Avg Km': [data['Kilometers'].mean()]
                    })

                    brand_summary = pd.concat([brand_summary, overall], ignore_index=True)

                    prompt = f"""
You are a professional automotive market analyst in Dubai.

The user asked: "{user_question}"

Here is a summary of the entire used car dataset (10,000+ records), generated from real data.

Brand-level statistics including an overall row at the bottom:

{brand_summary.to_markdown(index=False)}

Please:
1. Identify major market trends across price, mileage, and year.
2. Highlight which brands are high-end vs affordable.
3. Comment on how mileage correlates with price or year.
4. Suggest which segments (brands/models) offer the best value.
5. Write like you're briefing a business executive team in simple, clear terms.
6. Based on the analysis, provide practical suggestions for buyers (e.g., which brands or years offer the best value, which to avoid, etc.)

"""

                else:
                    brands = data["Brand"].dropna().unique().tolist()
                    matched_brands = [brand for brand in brands if re.search(rf"\b{re.escape(brand)}\b", user_question, re.IGNORECASE)]

                    if matched_brands:
                        filtered = data[data["Brand"].str.contains('|'.join(re.escape(b) for b in matched_brands), case=False)]
                        prompt_data = filtered
                        st.info(f"📌 Detected brands: {', '.join(matched_brands)}. Analyzing {len(filtered)} records.")
                    else:
                        prompt_data = data.sample(min(100, len(data)))
                        st.info(f"⚠️ No specific brand detected. Using random sample of {len(prompt_data)} records.")

                    prompt = f"""
You are a professional car market analyst in Dubai.

A user asked: "{user_question}"

Please perform the following:

1. Compare all mentioned brands ({', '.join(matched_brands) if matched_brands else 'selected sample'}).
2. Create a Markdown table showing for each brand: average price, average year, and mileage.
3. Then analyze differences between them, especially which brand tends to have newer or cheaper listings.
4. Provide a short summary recommendation.
5. Based on the analysis, provide practical suggestions for buyers (e.g., which brands or years offer the best value, which to avoid, etc.)


Use the dataset below:

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
