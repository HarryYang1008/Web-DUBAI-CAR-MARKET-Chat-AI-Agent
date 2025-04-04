import streamlit as st
import pandas as pd
import openai
import os
import io

# 设置 OpenAI API 密钥（在 Streamlit Cloud 上设置环境变量 OPENAI_API_KEY）
openai.api_key = os.getenv("OPENAI_API_KEY")

st.set_page_config(page_title="Dubai Car Market Q&A", layout="wide")
st.title("🚗 Dubai Used Car Price Assistant")

uploaded_file = st.file_uploader("Upload your CSV file (e.g., dubizzle_all_pages.csv)", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    # 简化列名处理，兼容格式差异
    df.columns = df.columns.str.strip()
    st.success(f"✅ Data uploaded. {df.shape[0]} rows loaded.")

    # 显示部分数据供检查
    with st.expander("🔍 Preview Data"):
        st.dataframe(df.head())

    user_question = st.text_input("Ask a question about the car market:", placeholder="e.g., What's the price trend for Camry?")

    if user_question and st.button("🔎 Analyze"):
        with st.spinner("Analyzing data with GPT-4..."):

            # 选取相关列并预处理
            target_cols = ['Brand', 'Model', 'Price', 'Year', 'Kilometers']
            if not all(col in df.columns for col in target_cols):
                st.error(f"Missing required columns in uploaded file: {target_cols}")
            else:
                # 清洗数据用于摘要
                filtered_df = df[target_cols].dropna().copy()
                filtered_df['Price'] = filtered_df['Price'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)
                filtered_df['Kilometers'] = filtered_df['Kilometers'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)

                # 限制分析行数，避免 prompt 太长
                sample_df = filtered_df.sample(min(100, len(filtered_df)))

                # 构建 Prompt
                prompt = f"""
You are a car market analyst. Analyze the following dataset based on this user question: "{user_question}".

Summarize price trends, model-year variations, and mileage impact. If the user asked about a specific brand/model (e.g., Camry), focus on those.

Here is the dataset (Brand, Model, Year, Price in AED, Kilometers):

{sample_df.to_csv(index=False)}

Return a clear summary and use Markdown tables if helpful.
"""

                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a data analyst specialized in car market trends in Dubai."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )

                st.markdown("### 📊 Analysis Result")
                st.markdown(response['choices'][0]['message']['content'])
