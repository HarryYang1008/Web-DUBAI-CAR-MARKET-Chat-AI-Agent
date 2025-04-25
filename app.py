import streamlit as st
import pandas as pd
import os
import re
from openai import OpenAI

# 初始化 OpenAI 客户端
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Dubai Car Market Q&A", layout="wide")
st.title("🚗 Dubai Used Car Price Assistant")

# 📂 显示当前数据文件名
with st.expander("📂 Show Data File Info"):
    if "current_filename" in st.session_state:
        st.write(f"**Current file name:** `{st.session_state['current_filename']}`")
    else:
        st.warning("No file has been loaded yet.")

# 📥 数据加载
data_source = st.radio("Select data source", ["📂 Upload CSV", "🌐 Load from GitHub"])
df = None

if data_source == "📂 Upload CSV":
    uploaded_files = st.file_uploader("Upload one or more CSVs", type=["csv"], accept_multiple_files=True)
    # ✅ 保存到 session_state，以便 history line 模式能识别
    if uploaded_files:
        st.session_state["uploaded_files"] = uploaded_files


if uploaded_files:
    dated_dfs = []
    for file in uploaded_files:
        try:
            temp_df = pd.read_csv(file)
            if "Date" in temp_df.columns:
                temp_df["Date"] = pd.to_datetime(temp_df["Date"])
                dated_dfs.append(temp_df)
            if df is None:
                df = temp_df  # 用第一个有效文件初始化显示
                st.session_state["current_filename"] = file.name
        except Exception as e:
            st.warning(f"Failed to load {file.name}: {e}")

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

# 🧠 用户提问处理逻辑
if df is not None:
    with st.expander("🔍 Preview Data"):
        st.dataframe(df.head())

    user_question = st.text_input("Ask a question about the car market:", placeholder="e.g., condition: under 120000km, BMW or Lexus, below 90k AED")

    if user_question and st.button("🔎 Analyze"):
        with st.spinner("Analyzing data with GPT-4o..."):

            required_cols = ['Brand', 'Model', 'Price', 'Year', 'Kilometers']
            if not all(col in df.columns for col in required_cols):
                st.error(f"Missing required columns: {required_cols}")
            else:
                data = df[required_cols].dropna().copy()
                data['Price'] = data['Price'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)
                data['Kilometers'] = data['Kilometers'].astype(str).str.replace(",", "").str.extract('(\d+)').astype(float)

                # 🚨 Condition 模式：自然语言筛选请求
                if "condition" in user_question.lower():
                    price_match = re.search(r'(?:under|below|less than)?\s*\$?(\d{4,6})\s*(?:to|-|and)?\s*\$?(\d{4,6})?', user_question)

                    km_match = re.search(r'(?:under|below|less than)?\s*(\d{2,3},?\d{3})\s*(?:km|kilometers)', user_question, re.IGNORECASE)


                    all_brands = data["Brand"].dropna().unique().tolist()
                    brand_selected = [b for b in all_brands if re.search(rf"\\b{re.escape(b)}\\b", user_question, re.IGNORECASE)]

                    price_min, price_max, km_limit = None, None, None
                    if price_match:
                        price_min = float(price_match.group(1).replace(',', ''))
                        if price_match.group(2):
                            price_max = float(price_match.group(2).replace(',', ''))
                    if km_match:
                        km_limit = float(km_match.group(1).replace(',', ''))

                    filtered_data = data.copy()
                    if price_min:
                        filtered_data = filtered_data[filtered_data["Price"] >= price_min]
                    if price_max:
                        filtered_data = filtered_data[filtered_data["Price"] <= price_max]
                    if km_limit:
                        filtered_data = filtered_data[filtered_data["Kilometers"] <= km_limit]
                    if brand_selected:
                        filtered_data = filtered_data[filtered_data["Brand"].isin(brand_selected)]

                    st.info(f"🔍 Detected conditions → Price: {price_min}-{price_max}, KM: {km_limit}, Brands: {', '.join(brand_selected) if brand_selected else 'Not specified'}")

                    prompt = f"""
You are a car market assistant in Dubai.

A user asked: "{user_question}"

Step 1: Identify cars that match the filters below.

Step 2: Must Create Markdown TABLES with frame and highlight differences in price, age, mileage.Summarize the matched cars by model, including their average price, year, and mileage.

Step 3: Summarize the matched cars by model, including their average price, year, and mileage.

Step 4: Write clear and helpful suggestions based on your analysis:

- For BUYERS: Which models offer the best value for money, combining price, mileage and year?
- For SELLERS: What should sellers emphasize in these listings? Which models are appealing and why?

⚠️ Do NOT skip these suggestions. The user is a business decision-maker and needs your recommendations.

Here is the dataset:

{filtered_data.to_csv(index=False)}
"""
                 # 📈 新模式：历史趋势图分析
                elif "history line" in user_question.lower():
                    # 🧠 新版引号匹配
                    brand_match = re.search(r'brand-[\'"]?([\w\s\-]+)[\'"]?', user_question, re.IGNORECASE)
                    model_match = re.search(r'model-[\'"]?([\w\s\-]+)[\'"]?', user_question, re.IGNORECASE)

                    if not brand_match or not model_match:
                        st.error("❌ Format must be like: 'history line brand-\"Tesla\" model-\"Model Y\"'")
                        st.stop()

                    brand = brand_match.group(1).strip()
                    model = model_match.group(1).strip()
                    st.info(f"📌 Searching historical trend for **{brand} {model}**")

                    if "uploaded_files" not in st.session_state or not st.session_state["uploaded_files"]:
                        st.error("❌ No history files uploaded. Please upload multiple dated CSVs.")
                        st.stop()

                    all_history_df = []

                    for f in st.session_state["uploaded_files"]:
                        try:
                            f.seek(0)
                            df_temp = pd.read_csv(f, encoding="utf-8-sig")

                            if "Date" not in df_temp.columns:
                                st.warning(f"⚠️ Skipped file {f.name}: No 'Date' column.")
                                continue

                            df_temp["Date"] = pd.to_datetime(df_temp["Date"], errors="coerce")
                            df_temp["Brand"] = df_temp["Brand"].astype(str)
                            df_temp["Model"] = df_temp["Model"].astype(str)
                            df_temp["Price"] = df_temp["Price"].astype(str).str.replace(",", "").str.extract(r"(\d+)").astype(float)
                            df_temp["Kilometers"] = df_temp["Kilometers"].astype(str).str.replace(",", "").str.extract(r"(\d+)").astype(float)

                            # 🔍 模糊筛选
                            df_filtered = df_temp[
                                df_temp["Brand"].str.lower().str.contains(brand.lower(), na=False) &
                                df_temp["Model"].str.lower().str.contains(model.lower(), na=False)
                            ]

                            if df_filtered.empty:
                                st.warning(f"⚠️ No match in {f.name}, skipped.")
                                continue

                            all_history_df.append(df_filtered)

                        except Exception as e:
                            st.warning(f"⚠️ Skipped file {f.name}: {e}")

                    if not all_history_df:
                        st.error("❌ No valid records found in any file for the given brand/model.")
                        st.stop()

                    history_df = pd.concat(all_history_df)
                    history_df.sort_values("Date", inplace=True)

                    import altair as alt

                    st.subheader("📈 Median Price Trend Over Time")

                    # 计算每日中位数价格
                    median_df = history_df.groupby("Date")["Price"].median().reset_index()

                    # 使用 Altair 绘制红点 + 连线图
                    chart = alt.Chart(median_df).mark_line(point=alt.OverlayMarkDef(color='red')).encode(
                        x=alt.X('Date:T', title='Date'),
                        y=alt.Y('Price:Q', title='Median Price (AED)'),
                        tooltip=['Date:T', 'Price:Q']
                    ).properties(
                        width=700,
                        height=400
                    ).interactive()

                    st.altair_chart(chart, use_container_width=True)



                    trend_prompt = f"""
                You are a professional automotive data analyst in Dubai.

                A user requested a historical analysis with the following filters:
                Brand: {brand}
                Model: {model}

                Here is the historical dataset:
                {history_df.to_csv(index=False)}

                Please:
                1. Identify whether the price is increasing or decreasing.
                2. Discuss how mileage trend evolves over time.
                3. Comment on whether average manufacturing year is getting newer or older.
                4. Make recommendations for buyers based on these trends.
                """

                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": "You are a data analyst specialized in car market trends in Dubai."},
                            {"role": "user", "content": trend_prompt}
                        ],
                        temperature=0.3,
                        max_tokens=3000
                    )

                    st.markdown("### 📊 Historical Trend GPT Analysis")
                    st.markdown(response.choices[0].message.content)
                    st.stop()

                                   
                # 🌍 全局市场趋势模式
                elif any(kw in user_question.lower() for kw in ['overall', 'market', 'all brands', 'general trend', 'whole market', 'total', '总览', '整体', '全部', '所有', '市场', '平均']):
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

                # 🚗 指定品牌分析
                else:
                    all_brands = data["Brand"].dropna().unique().tolist()
                    matched_brands = [brand for brand in all_brands if re.search(rf"\\b{re.escape(brand)}\\b", user_question, re.IGNORECASE)]

                    if matched_brands:
                        prompt_data = data[data["Brand"].str.contains('|'.join(re.escape(b) for b in matched_brands), case=False)]
                        st.info(f"📌 Detected brands: {', '.join(matched_brands)}. Analyzing {len(prompt_data)} records.")
                    else:
                        prompt_data = data.sample(min(100, len(data)))
                        st.info(f"⚠️ No specific brand detected. Using random sample of {len(prompt_data)} records.")

                    brand_group = prompt_data.groupby("Brand").agg({
                        "Price": "mean", "Year": "mean", "Kilometers": "mean"
                    }).reset_index()

                    model_group = prompt_data.groupby(["Brand", "Model"]).agg({
                        "Price": "mean", "Year": "mean", "Kilometers": "mean"
                    }).reset_index()
                    model_group.columns = ["Brand", "Model", "Avg Price", "Avg Year", "Avg Km"]

                    prompt = f"""
You are a professional car market analyst in Dubai.

A user asked: "{user_question}"

Here is the dataset filtered by brand(s): {', '.join(matched_brands) if matched_brands else 'Random Sample'}.

First, a brand-level summary:

{brand_group.to_markdown(index=False)}

Then, model-level details:

{model_group.to_markdown(index=False)}

Please perform the following:
1. Compare all mentioned brands and their models.
2. Create Markdown tables and highlight differences in price, age, mileage.
3. Analyze differences between the models and which stand out.
4. Provide summary recommendation.
5. Based on the analysis, provide practical suggestions for buyers (e.g., which models or years offer the best value, which to avoid, etc.)
"""

                # 🔁 调用 OpenAI
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a data analyst specialized in car market trends in Dubai."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=5000
                )

                st.markdown("### 📊 GPT-4 Analysis Result")
                st.markdown(response.choices[0].message.content)
                
