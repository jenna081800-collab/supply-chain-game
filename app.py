import streamlit as st
import pandas as pd
import numpy as np
import random

# --- Configuration & Constants ---
MAX_WEEKS = 20
INITIAL_CASH = 10000
INITIAL_INVENTORY = 30 # Slightly easier start
UNIT_SELLING_PRICE = 120 # Increased to ensure profit
INITIAL_MARKET_PRICE = 60
HOLDING_COST = 2 # Reduced
SHORTAGE_PENALTY = 5 # Reduced
WAREHOUSE_CAPACITY = 120
OVERFLOW_PENALTY = 50
UPSTREAM_CAPACITY = 60 

# Shipping Costs
SEA_FREIGHT_COST = 2
AIR_FREIGHT_COST = 15

# KPI Constants
KPI_START = 100
KPI_PENALTY_THRESHOLD_YELLOW = 70
KPI_PENALTY_THRESHOLD_RED = 50
KPI_FINE_YELLOW = 500
KPI_FINE_RED = 2000

# Demand Schedule (Movie Release Pattern)
# Week 1-4: Calm
# Week 5-8: Blockbuster Movie (High Demand)
# Week 9-12: Sustained Interest
# Week 13-20: Normal
DEMAND_SCHEDULE = {
    1: 20, 2: 20, 3: 20, 4: 25,
    5: 55, 6: 60, 7: 55, 8: 50, # Blockbuster!
    9: 40, 10: 35, 11: 30, 12: 30,
    13: 25, 14: 25, 15: 25, 16: 25,
    17: 25, 18: 25, 19: 25, 20: 25
}

# --- Game Logic Functions ---

def generate_forecast(week):
    """Generate a forecast range based on the Schedule."""
    base = DEMAND_SCHEDULE.get(week, 25)
    
    # Add some uncertainty
    noise = random.randint(-5, 5)
    center = base + noise
    
    f_min = max(0, center - 5)
    f_max = center + 5
    
    return f_min, f_max

def get_actual_demand(week):
    """Generate ACTUAL demand based on Schedule + Randomness."""
    base = DEMAND_SCHEDULE.get(week, 25)
    # Actual demand varies around the base
    actual = int(np.random.normal(base, 5))
    return max(0, actual)

def init_game():
    """Initialize or reset the game state."""
    st.session_state.week = 1
    st.session_state.cash = INITIAL_CASH
    st.session_state.inventory = INITIAL_INVENTORY
    st.session_state.market_price = INITIAL_MARKET_PRICE
    st.session_state.sea_lead_time_base = 2
    st.session_state.game_over = False
    st.session_state.phase = 'decision' # 'decision' or 'result'
    
    st.session_state.kpi_score = KPI_START
    st.session_state.upstream_congestion = False 
    st.session_state.forecast = generate_forecast(1)
    
    st.session_state.history = []
    st.session_state.pending_orders = []
    st.session_state.last_results = None

def update_market_price(current_price):
    change = random.choice([-5, 0, 5])
    new_price = current_price + change
    return max(40, min(90, new_price))

def check_events(week):
    # Event: Black Swan (Week 12 Port Strike)
    if week == 12:
        st.session_state.sea_lead_time_base = 3
        return True
    return False

def process_turn(order_qty, ship_mode):
    current_week = st.session_state.week
    
    # 1. Events
    black_swan = check_events(current_week)
    
    # 2. Demand
    demand = get_actual_demand(current_week)
    
    # 3. Arrivals
    arrivals = sum(o['qty'] for o in st.session_state.pending_orders if o['arrival_week'] == current_week)
    st.session_state.pending_orders = [o for o in st.session_state.pending_orders if o['arrival_week'] > current_week]
    
    # 4. Inventory
    available_inventory = st.session_state.inventory + arrivals
    
    # 5. Sales
    sales = min(demand, available_inventory)
    missed_sales = demand - sales
    ending_inventory = available_inventory - sales
    
    # 6. KPI
    kpi_change = -5 if missed_sales > 0 else 2
    st.session_state.kpi_score = max(0, min(100, st.session_state.kpi_score + kpi_change))
    
    # 7. Financials
    revenue = sales * UNIT_SELLING_PRICE
    shipping_cost_unit = SEA_FREIGHT_COST if ship_mode == 'sea' else AIR_FREIGHT_COST
    procurement_cost = order_qty * (st.session_state.market_price + shipping_cost_unit)
    holding_cost_total = ending_inventory * HOLDING_COST
    shortage_penalty = missed_sales * SHORTAGE_PENALTY
    
    overflow_penalty = 0
    if ending_inventory > WAREHOUSE_CAPACITY:
        overflow_count = ending_inventory - WAREHOUSE_CAPACITY
        overflow_penalty = overflow_count * OVERFLOW_PENALTY
        
    kpi_fine = 0
    if st.session_state.kpi_score < KPI_PENALTY_THRESHOLD_RED:
        kpi_fine = KPI_FINE_RED
    elif st.session_state.kpi_score < KPI_PENALTY_THRESHOLD_YELLOW:
        kpi_fine = KPI_FINE_YELLOW
    
    weekly_profit = revenue - procurement_cost - holding_cost_total - shortage_penalty - overflow_penalty - kpi_fine
    
    # 8. Update State
    prev_cash = st.session_state.cash
    st.session_state.cash += weekly_profit
    st.session_state.inventory = ending_inventory
    st.session_state.market_price = update_market_price(st.session_state.market_price)
    
    # 9. Logistics
    current_sea_lt = st.session_state.sea_lead_time_base
    if st.session_state.upstream_congestion:
        current_sea_lt += 1
    
    lead_time = 1 if ship_mode == 'air' else current_sea_lt
    arrival_week = current_week + lead_time
    
    if order_qty > 0:
        st.session_state.pending_orders.append({'arrival_week': arrival_week, 'qty': order_qty})
        
    next_congestion = False
    if order_qty > UPSTREAM_CAPACITY:
        next_congestion = True
        
    # 10. Store Results
    st.session_state.last_results = {
        'Week': current_week,
        'Demand': demand,
        'Order Qty': order_qty,
        'Sales': sales,
        'Missed Sales': missed_sales,
        'Ending Inv': ending_inventory,
        'KPI Score': st.session_state.kpi_score,
        'Net Profit': weekly_profit,
        'Cash': st.session_state.cash,
        'Cash Delta': st.session_state.cash - prev_cash,
        'Congestion Triggered': next_congestion,
        'Black Swan Triggered': black_swan,
        'KPI Fine': kpi_fine
    }
    
    st.session_state.history.append(st.session_state.last_results)
    st.session_state.upstream_congestion = next_congestion
    st.session_state.phase = 'result' # Switch to Result Phase

def advance_week():
    st.session_state.week += 1
    st.session_state.forecast = generate_forecast(st.session_state.week)
    st.session_state.phase = 'decision' # Switch back to Decision Phase
    
    if st.session_state.week > MAX_WEEKS:
        st.session_state.game_over = True

# --- UI Components ---

st.set_page_config(page_title="供應鏈韌性指揮官", layout="wide")

if 'week' not in st.session_state:
    init_game()

st.title("供應鏈韌性指揮官 (Supply Chain Resilience Commander)")

# Game Over
if st.session_state.game_over:
    st.balloons()
    st.header("🏁 遊戲結束 (Game Over)!")
    
    final_cash = st.session_state.cash
    df_hist = pd.DataFrame(st.session_state.history)
    total_profit = df_hist['Net Profit'].sum() if not df_hist.empty else 0
    final_kpi = st.session_state.kpi_score
    
    c1, c2, c3 = st.columns(3)
    c1.metric("最終現金", f"${final_cash:,.0f}")
    c2.metric("總獲利", f"${total_profit:,.0f}")
    c3.metric("最終 KPI", f"{final_kpi}")
    
    st.line_chart(df_hist.set_index('Week')[['Demand', 'Order Qty']])
    st.dataframe(df_hist)
    
    if st.button("再玩一次"):
        init_game()
        st.rerun()
    st.stop()

# --- PHASE 1: DECISION ---
if st.session_state.phase == 'decision':
    
    # Top Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("目前週數", f"{st.session_state.week} / {MAX_WEEKS}")
    col2.metric("KPI 分數", f"{st.session_state.kpi_score}")
    col3.metric("庫存", f"{st.session_state.inventory}")
    col4.metric("現金", f"${st.session_state.cash:,.0f}")
    
    st.markdown("---")
    
    # Warehouse Bar
    inv = st.session_state.inventory
    util = min(1.0, inv / WAREHOUSE_CAPACITY)
    st.write(f"🏭 **倉庫狀態:** {inv}/{WAREHOUSE_CAPACITY}")
    st.progress(util)
    if inv > WAREHOUSE_CAPACITY * 0.9:
        st.warning("⚠️ 倉庫快滿了！(Near Capacity)")
        
    st.markdown("---")
    
    # Event & Schedule Info
    c_info, c_input = st.columns([1, 1])
    
    with c_info:
        st.subheader("📅 市場情報 (Market Info)")
        
        # Movie Schedule
        if 4 <= st.session_state.week <= 8:
            st.error("🔥 **強檔電影上映中！** 爆米花需求暴增！(High Demand)")
        elif st.session_state.week == 3:
            st.warning("📢 **預告:** 下週起強檔電影上映，請備貨！")
        else:
            st.info("☁️ 市場需求平穩 (Normal Demand)")
            
        # Black Swan Warning
        if st.session_state.week >= 12:
            st.error("⚓ **港口罷工持續中！** 海運時間 +1 週 (Black Swan)")
            
        # Forecast
        f_min, f_max = st.session_state.forecast
        st.write(f"📈 **本週預估需求:** {f_min} ~ {f_max} 單位")
        st.write(f"💰 **目前進貨成本:** ${st.session_state.market_price}")
        
        # Lead Time
        base_sea = st.session_state.sea_lead_time_base
        actual_sea = base_sea + (1 if st.session_state.upstream_congestion else 0)
        st.write(f"🐢 **海運需:** {actual_sea} 週")
        if st.session_state.upstream_congestion:
            st.caption("🚫 (上游塞車延誤中)")
            
    with c_input:
        st.subheader("📝 下單決策 (Decision)")
        with st.form("order_form"):
            qty = st.number_input("訂購數量", 0, 500, 25, 5)
            mode = st.radio("運輸方式", ("🐢 海運 ($2)", "✈️ 空運 ($15)"))
            submit = st.form_submit_button("送出訂單 (Submit) 🚚", type="primary")
            
    if submit:
        ship_mode = 'sea' if '海運' in mode else 'air'
        process_turn(qty, ship_mode)
        st.rerun()

# --- PHASE 2: RESULT ---
elif st.session_state.phase == 'result':
    res = st.session_state.last_results
    
    st.header(f"📉 第 {res['Week']} 週結果 (Results)")
    
    # Hero Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("本週損益", f"${res['Net Profit']:,.0f}", delta_color="normal" if res['Net Profit']>=0 else "inverse")
    m2.metric("現金變動", f"${res['Cash Delta']:,.0f}")
    m3.metric("實際需求", f"{res['Demand']} 單位")
    
    st.markdown("---")
    
    # Status Banners
    if res['Missed Sales'] > 0:
        st.error(f"⚠️ **缺貨！** 錯失 {res['Missed Sales']} 筆訂單 (KPI -5)")
    else:
        st.success("✅ **完美達陣！** 滿足所有需求 (KPI +2)")
        
    if res['Congestion Triggered']:
        st.warning("🚫 **訂單過大！** 下週海運將延誤 (Shortage Gaming)")
        
    if res['KPI Fine'] > 0:
        st.error(f"💸 **總部罰款！** 扣款 ${res['KPI Fine']}")
        
    st.markdown("---")
    
    if st.button("下一週 (Next Week) ➡️", type="primary"):
        advance_week()
        st.rerun()
