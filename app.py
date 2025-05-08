import streamlit as st
import pandas as pd
import os
import re
import streamlit_authenticator as stauth
from openai import OpenAI

# ✅ 使用 credentials 字典格式
credentials = {
    "usernames": {
        "admin": {
            "name": "Admin",
            "password": "$2b$12$lfPSGxdSO4roQUaPVqSDBORR8u7eq9AWld5vDkTO7eIFvytHInNTG"
        },
        "user1": {
            "name": "BusinessUser",
            "password": "$2b$12$2kRskGAYZ2ZBdq8S9tAwt.W5EucF1z1.zdBCY13FzYdkIgEETb89q"
        }
    }
}

# ✅ 创建 authenticator 对象（注意参数变了）
authenticator = stauth.Authenticate(
    credentials,
    "dubaicar_auth", "abcdef", cookie_expiry_days=1
)

# ✅ 登录逻辑
name, auth_status, username = authenticator.login("🔐 Login", "main")

if auth_status is False:
    st.error("❌ Username/password is incorrect")
    st.stop()
elif auth_status is None:
    st.warning("⚠️ Please enter your credentials")
    st.stop()

st.sidebar.success(f"✅ Logged in as: {name} ({username})")
authenticator.logout("Logout", "sidebar")

# ✅ 初始化 OpenAI 和主界面
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

# ================================================================================================================================================ #

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
                    
# ================================================================================================================================================ #

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

                            is_showroom = "showroom" in f.name.lower()

                            # ✅ 只有市场数据强制检查 Date 字段
                            if not is_showroom and "Date" not in df_temp.columns:
                                st.warning(f"⚠️ Skipped file {f.name}: No 'Date' column.")
                                continue

                            # ✅ 仅市场数据转换 Date 列
                            if not is_showroom:
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

                            # ⏬ 年份过滤机制：如果存在 year- 触发词
                            year_match = re.search(r'year-[\'"]?([\d,\s]+)[\'"]?', user_question, re.IGNORECASE)
                            if year_match:
                                year_list = [int(y.strip()) for y in year_match.group(1).split(",") if y.strip().isdigit()]
                                df_filtered = df_filtered[df_filtered["Year"].isin(year_list)]

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

                    st.subheader("📈 Price Distribution + Median Trend")

                    # 🚩区分 showroom 文件（无 Date）与市场文件（有 Date）
                    market_data_list = []
                    showroom_data_list = []

                    for f in st.session_state["uploaded_files"]:
                        f.seek(0)
                        df_temp = pd.read_csv(f, encoding="utf-8-sig")
                        if "Brand" not in df_temp.columns or "Model" not in df_temp.columns:
                            continue

                        # 标准化字段
                        df_temp["Brand"] = df_temp["Brand"].astype(str)
                        df_temp["Model"] = df_temp["Model"].astype(str)
                        df_temp["Price"] = df_temp["Price"].astype(str).str.replace(",", "").str.extract(r"(\d+)").astype(float)
                        df_temp["Kilometers"] = df_temp["Kilometers"].astype(str).str.replace(",", "").str.extract(r"(\d+)").astype(float)
                        df_temp["Year"] = df_temp["Year"].astype(float)

                        # 品牌&车型筛选
                        df_filtered = df_temp[
                            df_temp["Brand"].str.lower().str.contains(brand.lower(), na=False) &
                            df_temp["Model"].str.lower().str.contains(model.lower(), na=False)
                        ]

                        # ⏬ 年份筛选（如果指定了）
                        year_match = re.search(r'year-[\'"]?([\d,\s]+)[\'"]?', user_question, re.IGNORECASE)
                        if year_match:
                            year_list = [int(y.strip()) for y in year_match.group(1).split(",") if y.strip().isdigit()]
                            df_filtered = df_filtered[df_filtered["Year"].isin(year_list)]

                        # 区分 showroom 文件 vs 市场文件
                        if "date" in df_filtered.columns.str.lower().tolist():
                            df_filtered["Date"] = pd.to_datetime(df_filtered["Date"], errors="coerce")
                            market_data_list.append(df_filtered)
                        elif "showroom" in f.name.lower():
                            showroom_data_list.append(df_filtered)

                    # 合并
                    if not market_data_list:
                        st.warning("❗ No market data found.")
                        st.stop()

                    history_df = pd.concat(market_data_list)
                    history_df.sort_values("Date", inplace=True)

                    showroom_df = pd.concat(showroom_data_list) if showroom_data_list else pd.DataFrame(columns=history_df.columns)

                    # ✅ 计算每日中位数
                    median_df = history_df.groupby("Date").agg({
                        "Price": "median",
                        "Kilometers": "mean",
                        "Year": "mean"
                    }).reset_index().rename(columns={"Price": "MedianPrice"})

                    # 图层一：蓝色市场数据点
                    point_chart = alt.Chart(history_df).mark_circle(size=60, color='steelblue').encode(
                        x=alt.X('Date:T', title='Date'),
                        y=alt.Y('Price:Q', title='Price (AED)'),
                        tooltip=[
                            alt.Tooltip('Date:T'),
                            alt.Tooltip('Price:Q'),
                            alt.Tooltip('Kilometers:Q'),
                            alt.Tooltip('Year:Q')
                        ]
                    )

                    # 图层二：红色中位数点+线
                    median_line = alt.Chart(median_df).mark_line(color='red', strokeWidth=2).encode(
                        x='Date:T',
                        y='MedianPrice:Q'
                    )
                    median_point = alt.Chart(median_df).mark_point(color='red', size=80, filled=True).encode(
                        x='Date:T',
                        y='MedianPrice:Q',
                        tooltip=[
                            alt.Tooltip('Date:T'),
                            alt.Tooltip('MedianPrice:Q'),
                            alt.Tooltip('Kilometers:Q', title="Avg Mileage"),
                            alt.Tooltip('Year:Q', title="Avg Year")
                        ]
                    )

                    # 图层三：黄色 showroom 横线（跨所有日期范围）
                    # 图层三：黄色 showroom 横线（跨所有日期范围）
                    if not showroom_df.empty:
                        x_min = history_df["Date"].min()
                        x_max = history_df["Date"].max()

                        # 修正方式：用 transform_calculate 为每条 showroom 数据横跨整个图宽度
                        showroom_df["x_start"] = x_min
                        showroom_df["x_end"] = x_max

                        showroom_lines = alt.Chart(showroom_df).mark_rule(
                            color='gold',
                            strokeDash=[3, 3]
                        ).encode(
                            x='x_start:T',
                            x2='x_end:T',
                            y='Price:Q',
                            tooltip=[
                                alt.Tooltip('Price:Q', title="Showroom Price"),
                                alt.Tooltip('Kilometers:Q'),
                                alt.Tooltip('Year:Q')
                            ]
                        )

                        combined_chart = point_chart + median_line + median_point + showroom_lines
                    else:
                        combined_chart = point_chart + median_line + median_point

                    
                    # 📈 显示图表
                    st.altair_chart(combined_chart.properties(
                        width=700,
                        height=400
                    ).interactive(), use_container_width=True)




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

# ================================================================================================================================================ #

                # 🚗 品牌市场分析模块（新触发逻辑：brand market + brand-"XXX" 格式）
                elif "brand market" in user_question.lower():
                    brand_match = re.search(r'brand-[\'"]?([\w\s\-]+)[\'"]?', user_question, re.IGNORECASE)

                    if not brand_match:
                        st.warning("⚠️ Could not detect brand from your query. Please use format like: brand market brand-\"Toyota\"")
                        prompt_data = data.sample(min(100, len(data)))
                        matched_brands = []
                    else:
                        brand_name = brand_match.group(1).strip()
                        matched_brands = [brand_name]
                        prompt_data = data[data["Brand"].str.lower().str.contains(brand_name.lower(), na=False)]
                        st.info(f"📌 Detected brand: {brand_name}. Analyzing {len(prompt_data)} records.")

                    brand_group = prompt_data.groupby("Brand").agg({
                        "Price": "mean", "Year": "mean", "Kilometers": "mean"
                    }).reset_index()

                    model_group = prompt_data.groupby(["Brand", "Model"]).agg({
                        "Price": "mean",
                        "Year": "mean",
                        "Kilometers": "mean",
                        "Model": "count"
                    }).rename(columns={"Model": "Count"}).reset_index()

                    model_group.columns = ["Brand", "Model", "Avg Price", "Avg Year", "Avg Km", "Count"]


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



# ================================================================================================================================================ #

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

                

                
