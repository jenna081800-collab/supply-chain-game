import streamlit as st
import pandas as pd
import numpy as np
import random

# --- Configuration & Constants ---
MAX_WEEKS = 20
INITIAL_CASH = 10000
INITIAL_INVENTORY = 50
UNIT_SELLING_PRICE = 100
INITIAL_MARKET_PRICE = 60
HOLDING_COST = 5
SHORTAGE_PENALTY = 10
WAREHOUSE_CAPACITY = 120
OVERFLOW_PENALTY = 50
MARKET_INTEL_COST = 500
UPSTREAM_CAPACITY = 60 # Max units per week before congestion

# Shipping Costs
SEA_FREIGHT_COST = 2
AIR_FREIGHT_COST = 15

# KPI Constants
KPI_START = 100
KPI_PENALTY_THRESHOLD_YELLOW = 70
KPI_PENALTY_THRESHOLD_RED = 50
KPI_FINE_YELLOW = 500
KPI_FINE_RED = 2000

# --- Game Logic Functions ---

def init_game():
    """Initialize or reset the game state."""
    st.session_state.week = 1
    st.session_state.cash = INITIAL_CASH
    st.session_state.inventory = INITIAL_INVENTORY
    st.session_state.market_price = INITIAL_MARKET_PRICE
    st.session_state.sea_lead_time_base = 2  # Base lead time for Sea
    st.session_state.market_intel = False
    st.session_state.game_over = False
    
    # New V3.2 State
    st.session_state.kpi_score = KPI_START
    st.session_state.upstream_congestion = False # If True, Sea LT +1 next turn
    
    # History stores dictionaries of weekly results
    st.session_state.history = []
    
    # Pending orders: List of dictionaries {'arrival_week': int, 'qty': int}
    st.session_state.pending_orders = []
    
    # To display metrics of the *last* turn
    st.session_state.last_week_metrics = None

def get_demand(week):
    """Generate demand based on normal distribution and events."""
    # Base Demand
    demand = max(0, int(np.random.normal(20, 5)))
    
    # Event: Gray Rhino (Week 8 Spike)
    if week == 8:
        demand += 15
        
    return demand

def update_market_price(current_price):
    """Random walk for market price between $40 and $90."""
    change = random.choice([-5, 0, 5])
    new_price = current_price + change
    return max(40, min(90, new_price))

def check_events(week):
    """Check for and apply persistent game events."""
    messages = []
    
    # Event: Black Swan (Week 12 Port Strike)
    if week == 12:
        st.session_state.sea_lead_time_base = 3
        messages.append("⚠️ **黑天鵝事件 (Black Swan):** 港口發生罷工！海運前置時間永久增加至 3 週。")
        
    return messages

def process_turn(order_qty, ship_mode):
    """Execute the logic for a single week."""
    current_week = st.session_state.week
    
    # 1. Apply Events
    event_msgs = check_events(current_week)
    for msg in event_msgs:
        st.toast(msg, icon="🦢")
    
    # 2. Generate Demand
    demand = get_demand(current_week)
    
    # 3. Receive Shipments
    arrivals = sum(o['qty'] for o in st.session_state.pending_orders if o['arrival_week'] == current_week)
    st.session_state.pending_orders = [o for o in st.session_state.pending_orders if o['arrival_week'] > current_week]
    
    # 4. Update Inventory (Available for sale)
    available_inventory = st.session_state.inventory + arrivals
    
    # 5. Fulfill Demand
    sales = min(demand, available_inventory)
    missed_sales = demand - sales
    ending_inventory = available_inventory - sales
    
    # 6. Update KPI
    kpi_change = 0
    if missed_sales > 0:
        kpi_change = -5
    else:
        kpi_change = 2
    
    st.session_state.kpi_score = max(0, min(100, st.session_state.kpi_score + kpi_change))
    
    # 7. Calculate Financials
    revenue = sales * UNIT_SELLING_PRICE
    
    # Cost of Goods Sold (Purchasing + Shipping)
    shipping_cost_unit = SEA_FREIGHT_COST if ship_mode == 'sea' else AIR_FREIGHT_COST
    procurement_cost = order_qty * (st.session_state.market_price + shipping_cost_unit)
    
    # Holding Cost
    holding_cost_total = ending_inventory * HOLDING_COST
    
    # Shortage Penalty (Opportunity Cost)
    shortage_penalty = missed_sales * SHORTAGE_PENALTY
    
    # Warehouse Overflow Penalty
    overflow_penalty = 0
    if ending_inventory > WAREHOUSE_CAPACITY:
        overflow_count = ending_inventory - WAREHOUSE_CAPACITY
        overflow_penalty = overflow_count * OVERFLOW_PENALTY
        st.toast(f"💥 **爆倉警告 (Warehouse Overflow)!** 超出 {overflow_count} 單位，罰款 ${overflow_penalty}", icon="💥")
        
    # Franchise KPI Penalty
    kpi_fine = 0
    if st.session_state.kpi_score < KPI_PENALTY_THRESHOLD_RED:
        kpi_fine = KPI_FINE_RED
        st.toast(f"🚨 **品牌信譽違約金!** KPI < 50，扣款 ${KPI_FINE_RED}", icon="🚨")
    elif st.session_state.kpi_score < KPI_PENALTY_THRESHOLD_YELLOW:
        kpi_fine = KPI_FINE_YELLOW
        st.toast(f"⚠️ **重點輔導費!** KPI < 70，扣款 ${KPI_FINE_YELLOW}", icon="⚠️")
    
    weekly_profit = revenue - procurement_cost - holding_cost_total - shortage_penalty - overflow_penalty - kpi_fine
    
    # 8. Update State
    st.session_state.cash += weekly_profit
    st.session_state.inventory = ending_inventory
    
    # Update Market Price for NEXT week
    st.session_state.market_price = update_market_price(st.session_state.market_price)
    
    # 9. Place New Order & Handle Logistics
    # Determine Lead Time
    current_sea_lt = st.session_state.sea_lead_time_base
    if st.session_state.upstream_congestion:
        current_sea_lt += 1 # Penalty from previous week's large order
        st.toast("🐢 **上游塞車效應:** 本週海運時間 +1 週", icon="🐢")
    
    lead_time = 1 if ship_mode == 'air' else current_sea_lt
    arrival_week = current_week + lead_time
    
    if order_qty > 0:
        st.session_state.pending_orders.append({'arrival_week': arrival_week, 'qty': order_qty})
        
    # Check for Shortage Gaming (Upstream Constraint) for NEXT week
    if order_qty > UPSTREAM_CAPACITY:
        st.session_state.upstream_congestion = True
        st.toast("🚫 **訂單過大導致上游塞車！** 下週海運將延誤 (Shortage Gaming)", icon="🚫")
    else:
        st.session_state.upstream_congestion = False
    
    # 10. Log History
    record = {
        'Week': current_week,
        'Demand': demand,
        'Order Qty': order_qty,
        'Market Price': st.session_state.market_price, 
        'Ship Mode': 'Air' if ship_mode == 'air' else 'Sea',
        'Sales': sales,
        'Missed Sales': missed_sales,
        'Ending Inv': ending_inventory,
        'KPI Score': st.session_state.kpi_score,
        'Revenue': revenue,
        'Procurement Cost': procurement_cost,
        'Holding Cost': holding_cost_total,
        'Shortage Penalty': shortage_penalty,
        'Overflow Penalty': overflow_penalty,
        'KPI Fine': kpi_fine,
        'Net Profit': weekly_profit,
        'Cash': st.session_state.cash
    }
    st.session_state.history.append(record)
    st.session_state.last_week_metrics = record
    
    # 11. Advance Week
    st.session_state.week += 1
    if st.session_state.week > MAX_WEEKS:
        st.session_state.game_over = True

# --- UI Components ---

st.set_page_config(page_title="Supply Chain Resilience Commander V3.2", layout="wide")

# Initialize State
if 'week' not in st.session_state:
    init_game()

# --- Sidebar ---
with st.sidebar:
    st.title("🏭 供應鏈指揮官 V3.2")
    
    st.markdown("### 📊 狀態 (Status)")
    st.metric("目前週數 (Week)", f"{st.session_state.week} / {MAX_WEEKS}")
    st.metric("現金餘額 (Cash)", f"${st.session_state.cash:,.0f}")
    
    # KPI Display
    kpi = st.session_state.kpi_score
    kpi_color = "normal"
    if kpi < 70: kpi_color = "off" # Streamlit metric doesn't support custom colors easily, using delta
    st.metric("加盟 KPI (Franchise Score)", f"{kpi}", delta=None)
    if kpi < 50:
        st.error("🚨 品牌信譽危機！(Critical)")
    elif kpi < 70:
        st.warning("⚠️ 需要重點輔導 (Warning)")
    else:
        st.success("✅ 表現優良 (Good)")
        
    st.markdown("---")
    
    # Lead Time Display
    base_sea = st.session_state.sea_lead_time_base
    actual_sea = base_sea + (1 if st.session_state.upstream_congestion else 0)
    st.markdown(f"**海運前置時間 (Sea Lead Time):** {actual_sea} 週")
    if st.session_state.upstream_congestion:
        st.caption("🐢 (因上週訂單過大延誤 +1)")
    st.markdown(f"**空運前置時間 (Air Lead Time):** 1 週")
    
    st.markdown("---")
    
    # Market Intelligence Upgrade
    if not st.session_state.market_intel:
        st.markdown("### 🧠 策略 (Strategy)")
        if st.button(f"購買市場情報 (-${MARKET_INTEL_COST})"):
            if st.session_state.cash >= MARKET_INTEL_COST:
                st.session_state.cash -= MARKET_INTEL_COST
                st.session_state.market_intel = True
                st.success("已購買市場情報！")
                st.rerun()
            else:
                st.error("資金不足！")
    else:
        st.info("✅ 市場情報已啟用")
        
    st.markdown("---")
    if st.button("🔄 重置遊戲 (Reset)"):
        init_game()
        st.rerun()

# --- Main Area ---

st.title("Supply Chain Resilience Commander V3.2")
st.markdown("加盟總部考核中！請維持高 KPI，避免斷貨與爆倉。(Maintain high KPI, avoid stockouts and overflow!)")

# Game Over Screen
if st.session_state.game_over:
    st.balloons()
    st.header("🏁 遊戲結束 (Game Over)!")
    
    final_cash = st.session_state.cash
    df_hist = pd.DataFrame(st.session_state.history)
    total_profit = df_hist['Net Profit'].sum() if not df_hist.empty else 0
    final_kpi = st.session_state.kpi_score
    
    c1, c2, c3 = st.columns(3)
    c1.metric("最終現金 (Final Cash)", f"${final_cash:,.0f}")
    c2.metric("總獲利 (Total Profit)", f"${total_profit:,.0f}")
    c3.metric("最終 KPI", f"{final_kpi}")
    
    st.subheader("績效回顧 (Performance Review)")
    st.line_chart(df_hist.set_index('Week')[['Demand', 'Order Qty']])
    
    st.dataframe(df_hist)
    
    if st.button("再玩一次 (Play Again)"):
        init_game()
        st.rerun()
    
    st.stop()

# Active Game Dashboard

# 1. Notifications & Warnings
# Black Swan Warning (Week 12)
if st.session_state.week == 12:
    st.error("⚠️ **黑天鵝事件 (Black Swan):** 港口罷工！海運變慢了！")

# Gray Rhino Warning (Week 7, if Intel purchased)
if st.session_state.market_intel and st.session_state.week == 7:
    st.warning("🕵️ **情報報告:** 分析師預測下週需求將因電影上映而暴增！(Demand Spike Incoming)")

# 2. Metrics (Last Week's Performance)
if st.session_state.last_week_metrics:
    last = st.session_state.last_week_metrics
    st.markdown(f"### 📉 第 {last['Week']} 週財務報表")
    
    # Financial Breakdown
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("本週營收 (Revenue)", f"${last['Revenue']:,.0f}")
    col2.metric("進貨成本 (COGS)", f"${last['Procurement Cost']:,.0f}")
    col3.metric("淨利 (Net Profit)", f"${last['Net Profit']:,.0f}")
    col4.metric("期末庫存 (Ending Inv)", f"{last['Ending Inv']}")
    
    with st.expander("查看詳細扣款 (Deductions Detail)"):
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("庫存持有成本", f"${last['Holding Cost']:,.0f}")
        d2.metric("缺貨機會成本", f"${last['Shortage Penalty']:,.0f}")
        d3.metric("爆倉罰款", f"${last['Overflow Penalty']:,.0f}")
        d4.metric("總部 KPI 罰款", f"${last['KPI Fine']:,.0f}", delta_color="inverse")

else:
    st.info("👋 歡迎！請下達您的第一個訂單。")

# 3. Action Area
st.markdown("### 📝 下單決策 (Order Decision)")

# Market Price Trend
if st.session_state.history:
    prices = [h['Market Price'] for h in st.session_state.history]
    prices.append(st.session_state.market_price)
    chart_data = pd.DataFrame({'Week': range(1, len(prices) + 1), 'Market Price': prices})
    st.line_chart(chart_data.set_index('Week'), height=200)
else:
    st.markdown(f"**目前市場成本:** ${st.session_state.market_price}")

with st.form("order_form"):
    c1, c2, c3 = st.columns([2, 2, 1])
    
    with c1:
        st.markdown(f"#### 1. 採購數量")
        st.markdown(f"目前單價: **${st.session_state.market_price}**")
        order_qty = st.number_input(
            "數量 (Qty)", 
            min_value=0, 
            max_value=500, 
            value=20,
            step=5,
            help=f"注意：單筆超過 {UPSTREAM_CAPACITY} 單位將導致上游塞車！"
        )
        
    with c2:
        st.markdown(f"#### 2. 物流模式")
        ship_mode_display = st.radio(
            "選擇運輸方式 (Select Mode)",
            ("🐢 海運 (Sea) - $2/unit", "✈️ 空運 (Air) - $15/unit"),
            index=0
        )
        ship_mode = 'sea' if 'Sea' in ship_mode_display else 'air'
        
        # Calculate expected arrival for display
        base = st.session_state.sea_lead_time_base
        congestion = 1 if st.session_state.upstream_congestion else 0
        sea_time = base + congestion
        
        current_lt = sea_time if ship_mode == 'sea' else 1
        st.caption(f"預計抵達時間: {current_lt} 週後")

    with c3:
        st.markdown("<br><br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("送出訂單 (Submit) 🚚", type="primary")

if submitted:
    process_turn(order_qty, ship_mode)
    st.rerun()

# 4. Warehouse Status
st.markdown("### 🏭 倉庫狀態 (Warehouse Status)")
inv = st.session_state.inventory
utilization = min(1.0, inv / WAREHOUSE_CAPACITY)

st.progress(utilization, text=f"使用率: {int(utilization*100)}% ({inv}/{WAREHOUSE_CAPACITY})")
if inv > WAREHOUSE_CAPACITY:
    st.caption(f"⚠️ 爆倉！超出 {inv - WAREHOUSE_CAPACITY} 單位將被罰款。")

# 5. Visualization
if st.session_state.history:
    c_chart1, c_chart2 = st.columns(2)
    
    with c_chart1:
        st.markdown("#### 庫存 vs 上限 (Inventory Level)")
        df = pd.DataFrame(st.session_state.history)
        chart_inv = df[['Week', 'Ending Inv']].copy()
        chart_inv['Capacity'] = WAREHOUSE_CAPACITY
        st.line_chart(chart_inv.set_index('Week'))

    with c_chart2:
        st.markdown("#### 長鞭效應 (Bullwhip Effect)")
        chart_bull = df[['Week', 'Demand', 'Order Qty']]
        st.line_chart(chart_bull.set_index('Week'))
    
    with st.expander("📜 查看詳細歷史紀錄 (History Log)"):
        st.dataframe(df.style.format({
            'Net Profit': '${:,.0f}', 
            'Cash': '${:,.0f}',
            'Market Price': '${:,.0f}'
        }))

# 6. Rules
with st.expander("ℹ️ 遊戲規則 (Game Rules)"):
    st.markdown(f"""
    - **目標 (Goal):** 在 20 週內最大化現金。
    - **KPI 考核:** 缺貨扣 5 分，不缺貨加 2 分。
        - ⚠️ **< 70 分:** 罰款 ${KPI_FINE_YELLOW}/週。
        - 🚨 **< 50 分:** 罰款 ${KPI_FINE_RED}/週。
    - **上游限制:** 單筆訂單 > {UPSTREAM_CAPACITY} 單位，下週海運延誤 1 週。
    - **售價 (Price):** ${UNIT_SELLING_PRICE}
    - **成本 (Cost):** 浮動市場價格 ($40-$90) + 運費。
    - **運費 (Shipping):** 海運 $2 (慢), 空運 $15 (快)。
    - **爆倉罰款 (Overflow):** 超過 {WAREHOUSE_CAPACITY} 單位，每單位罰款 ${OVERFLOW_PENALTY}。
    """)
