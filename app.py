import streamlit as st
import pandas as pd
import numpy as np
import random

# --- Configuration & Constants ---
MAX_WEEKS = 20
INITIAL_CASH = 10000
INITIAL_INVENTORY = 25 # Hard Mode: Lower start
UNIT_SELLING_PRICE = 100
INITIAL_MARKET_PRICE = 60
HOLDING_COST = 5
SHORTAGE_PENALTY = 10
WAREHOUSE_CAPACITY = 120
OVERFLOW_PENALTY = 50
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

def generate_forecast(week):
    """Generate a forecast range for the UPCOMING week."""
    # Base mean is 25.
    base_mean = 25
    
    # Event Awareness (Forecast should hint at events)
    if week == 8: # Gray Rhino
        base_mean += 30
        
    # Forecast Error: Randomly shift the center
    forecast_center = int(np.random.normal(base_mean, 3))
    forecast_min = max(0, forecast_center - random.randint(3, 8))
    forecast_max = forecast_center + random.randint(3, 8)
    
    return forecast_min, forecast_max

def init_game():
    """Initialize or reset the game state."""
    st.session_state.week = 1
    st.session_state.cash = INITIAL_CASH
    st.session_state.inventory = INITIAL_INVENTORY
    st.session_state.market_price = INITIAL_MARKET_PRICE
    st.session_state.sea_lead_time_base = 2
    st.session_state.game_over = False
    
    # Hard Mode State
    st.session_state.kpi_score = KPI_START
    st.session_state.upstream_congestion = False # If True, Sea LT +1 next turn
    st.session_state.forecast = generate_forecast(1) # Forecast for Week 1
    
    # History & Results
    st.session_state.history = []
    st.session_state.pending_orders = []
    st.session_state.last_results = None # Stores data for the "Result Reveal" section

def get_actual_demand(week):
    """Generate ACTUAL demand based on normal distribution and events."""
    # Base Demand: Mean=25, Std=8 (Hard Mode)
    demand = max(0, int(np.random.normal(25, 8)))
    
    # Event: Gray Rhino (Week 8 Spike)
    if week == 8:
        demand += 30
        
    return demand

def update_market_price(current_price):
    """Random walk for market price between $40 and $90."""
    change = random.choice([-5, 0, 5])
    new_price = current_price + change
    return max(40, min(90, new_price))

def check_events(week):
    """Check for persistent game events."""
    # Event: Black Swan (Week 12 Port Strike)
    if week == 12:
        st.session_state.sea_lead_time_base = 3
        return True
    return False

def process_turn(order_qty, ship_mode):
    """Execute the logic for a single week."""
    current_week = st.session_state.week
    
    # 1. Apply Events (Persistent)
    black_swan_triggered = check_events(current_week)
    
    # 2. Generate Actual Demand
    demand = get_actual_demand(current_week)
    
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
    kpi_change = -5 if missed_sales > 0 else 2
    st.session_state.kpi_score = max(0, min(100, st.session_state.kpi_score + kpi_change))
    
    # 7. Calculate Financials
    revenue = sales * UNIT_SELLING_PRICE
    
    # Cost of Goods Sold (Purchasing + Shipping)
    shipping_cost_unit = SEA_FREIGHT_COST if ship_mode == 'sea' else AIR_FREIGHT_COST
    procurement_cost = order_qty * (st.session_state.market_price + shipping_cost_unit)
    
    # Holding Cost
    holding_cost_total = ending_inventory * HOLDING_COST
    
    # Shortage Penalty
    shortage_penalty = missed_sales * SHORTAGE_PENALTY
    
    # Warehouse Overflow Penalty
    overflow_penalty = 0
    if ending_inventory > WAREHOUSE_CAPACITY:
        overflow_count = ending_inventory - WAREHOUSE_CAPACITY
        overflow_penalty = overflow_count * OVERFLOW_PENALTY
        
    # Franchise KPI Penalty
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
    
    # Update Market Price for NEXT week
    st.session_state.market_price = update_market_price(st.session_state.market_price)
    
    # 9. Place New Order & Handle Logistics
    # Determine Lead Time for THIS order
    current_sea_lt = st.session_state.sea_lead_time_base
    if st.session_state.upstream_congestion:
        current_sea_lt += 1 # Penalty from previous week
    
    lead_time = 1 if ship_mode == 'air' else current_sea_lt
    arrival_week = current_week + lead_time
    
    if order_qty > 0:
        st.session_state.pending_orders.append({'arrival_week': arrival_week, 'qty': order_qty})
        
    # Check for Shortage Gaming (Upstream Constraint) for NEXT week
    # If order > 60, NEXT week's sea orders will be delayed
    next_congestion = False
    if order_qty > UPSTREAM_CAPACITY:
        next_congestion = True
    
    # 10. Store Results for Display
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
        'Black Swan Triggered': black_swan_triggered,
        'KPI Fine': kpi_fine
    }
    
    # Record History
    st.session_state.history.append(st.session_state.last_results)
    
    # 11. Advance Week & Prepare Next Turn
    st.session_state.week += 1
    st.session_state.upstream_congestion = next_congestion
    st.session_state.forecast = generate_forecast(st.session_state.week)
    
    if st.session_state.week > MAX_WEEKS:
        st.session_state.game_over = True

# --- UI Components ---

st.set_page_config(page_title="供應鏈韌性指揮官", layout="wide")

# Initialize State
if 'week' not in st.session_state:
    init_game()

st.title("供應鏈韌性指揮官 (Supply Chain Resilience Commander)")

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

# --- SECTION 1: Dashboard & Decision (Always Visible) ---

with st.container():
    # Top Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("目前週數 (Week)", f"{st.session_state.week} / {MAX_WEEKS}")
    
    kpi = st.session_state.kpi_score
    col2.metric("KPI 考核分數", f"{kpi}", delta=None) # Color handled by banner/text below if needed
    
    col3.metric("目前庫存 (Inventory)", f"{st.session_state.inventory}")
    col4.metric("現金餘額 (Cash)", f"${st.session_state.cash:,.0f}")

    st.markdown("---")

    # Decision Support Panel
    c_dec1, c_dec2 = st.columns([1, 1])
    
    with c_dec1:
        st.subheader("📊 決策支援 (Decision Support)")
        st.info(f"💰 **目前市場成本:** ${st.session_state.market_price} / 單位")
        
        f_min, f_max = st.session_state.forecast
        st.info(f"📈 **預計顧客需求:** {f_min} ~ {f_max} 單位")
        
        # Lead Time Info
        base_sea = st.session_state.sea_lead_time_base
        actual_sea = base_sea + (1 if st.session_state.upstream_congestion else 0)
        st.write(f"**海運前置時間:** {actual_sea} 週")
        if st.session_state.upstream_congestion:
            st.caption("🐢 (上游塞車中 +1)")
            
    with c_dec2:
        st.subheader("📝 下單 (Place Order)")
        with st.form("order_form"):
            order_qty = st.number_input("訂購數量 (Order Qty)", min_value=0, max_value=500, value=25, step=5)
            ship_mode_display = st.radio("運輸方式 (Shipping)", ("🐢 海運 (Sea) - $2", "✈️ 空運 (Air) - $15"))
            ship_mode = 'sea' if 'Sea' in ship_mode_display else 'air'
            
            submit = st.form_submit_button("送出訂單 (Submit Order) 🚚", type="primary")

if submit:
    process_turn(order_qty, ship_mode)
    st.rerun()

# --- SECTION 2: Result Reveal (Visible after first turn) ---

if st.session_state.last_results:
    res = st.session_state.last_results
    
    st.markdown("---")
    st.header(f"📉 第 {res['Week']} 週營運結果 (Results)")
    
    # Part A: Hero Metrics
    hm1, hm2 = st.columns(2)
    hm1.metric("累計現金 (Total Cash)", f"${res['Cash']:,.0f}", delta=f"${res['Cash Delta']:,.0f}")
    hm2.metric("本週淨利 (Weekly Net Profit)", f"${res['Net Profit']:,.0f}", 
               delta_color="normal" if res['Net Profit'] >= 0 else "inverse")
    
    # Part B: Operational Status Banners
    # Customer Status
    if res['Missed Sales'] == 0:
        st.success(f"✅ **完美達陣！** 顧客需求 {res['Demand']} 單位全數滿足。")
    else:
        st.error(f"⚠️ **顧客流失！** 實際需求 {res['Demand']}，錯失 {res['Missed Sales']} 筆訂單。")
        
    # Supplier Status
    if res['Congestion Triggered']:
        st.error("🚫 **訂單過大！** 供應商產能爆滿，下週海運將延誤。")
    else:
        st.info("✅ **供應商產能正常**")
        
    # Events & Penalties
    if res['Black Swan Triggered']:
        st.warning("⚓ **黑天鵝事件！** 港口罷工，海運時間永久 +1 週。")
    if res['KPI Fine'] > 0:
        st.warning(f"💸 **總部罰款！** KPI 過低，扣款 ${res['KPI Fine']}。")

    # Part C: Supporting Analysis
    st.markdown("### 📊 數據分析 (Analysis)")
    tab1, tab2, tab3 = st.tabs(["💰 獲利趨勢", "🐂 長鞭效應", "📜 詳細紀錄"])
    
    df = pd.DataFrame(st.session_state.history)
    
    with tab1:
        st.markdown("#### 每週獲利 (Weekly Profit)")
        st.bar_chart(df.set_index('Week')['Net Profit'])
        st.markdown("#### 累計現金 (Cumulative Cash)")
        st.line_chart(df.set_index('Week')['Cash'])
        
    with tab2:
        st.markdown("#### 實際需求 vs 訂購量 (Demand vs Order)")
        st.line_chart(df.set_index('Week')[['Demand', 'Order Qty']])
        
    with tab3:
        st.dataframe(df.style.format({
            'Net Profit': '${:,.0f}', 
            'Cash': '${:,.0f}',
            'Market Price': '${:,.0f}'
        }))
