import streamlit as st
import pandas as pd
import numpy as np

# --- Configuration & Constants ---
MAX_WEEKS = 20
INITIAL_CASH = 10000
INITIAL_INVENTORY = 50
UNIT_SELLING_PRICE = 100
UNIT_COST = 60
HOLDING_COST = 5
SHORTAGE_PENALTY = 10
INITIAL_LEAD_TIME = 2
MARKET_INTEL_COST = 500

# --- Game Logic Functions ---

def init_game():
    """Initialize or reset the game state."""
    st.session_state.week = 1
    st.session_state.cash = INITIAL_CASH
    st.session_state.inventory = INITIAL_INVENTORY
    st.session_state.lead_time = INITIAL_LEAD_TIME
    st.session_state.market_intel = False
    st.session_state.game_over = False
    
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

def check_events(week):
    """Check for and apply persistent game events."""
    messages = []
    
    # Event: Black Swan (Week 12 Port Strike)
    if week == 12:
        st.session_state.lead_time = 3
        messages.append("⚠️ **BLACK SWAN EVENT:** A port strike has occurred! Lead time has permanently increased to 3 weeks.")
        
    return messages

def process_turn(order_qty):
    """Execute the logic for a single week."""
    current_week = st.session_state.week
    
    # Apply Events (e.g., Black Swan)
    check_events(current_week)
    
    # 1. Generate Demand
    demand = get_demand(current_week)
    
    # 2. Receive Shipments (Orders arriving this week)
    # We sum up all orders scheduled to arrive at 'current_week'
    arrivals = sum(o['qty'] for o in st.session_state.pending_orders if o['arrival_week'] == current_week)
    
    # Clean up processed orders
    st.session_state.pending_orders = [o for o in st.session_state.pending_orders if o['arrival_week'] > current_week]
    
    # 3. Update Inventory (Available for sale)
    # Assumption: Shipments arrive at start of week and are available for sale
    available_inventory = st.session_state.inventory + arrivals
    
    # 4. Fulfill Demand
    sales = min(demand, available_inventory)
    missed_sales = demand - sales
    ending_inventory = available_inventory - sales
    
    # 5. Calculate Financials
    revenue = sales * UNIT_SELLING_PRICE
    cogs = order_qty * UNIT_COST # Cost is incurred when ORDER is placed (common simplification) or when received? 
    # Prompt says: "Profit Calculation: (Sales * Price) - (Order Qty * Cost) - ..."
    # So we pay for what we order immediately.
    
    holding_cost_total = ending_inventory * HOLDING_COST
    penalty_cost = missed_sales * SHORTAGE_PENALTY
    
    weekly_profit = revenue - (order_qty * UNIT_COST) - holding_cost_total - penalty_cost
    
    # 6. Update State
    st.session_state.cash += weekly_profit
    st.session_state.inventory = ending_inventory
    
    # 7. Place New Order
    arrival_week = current_week + st.session_state.lead_time
    st.session_state.pending_orders.append({'arrival_week': arrival_week, 'qty': order_qty})
    
    # 8. Log History
    record = {
        'Week': current_week,
        'Demand': demand,
        'Order Qty': order_qty,
        'Arrivals': arrivals,
        'Sales': sales,
        'Missed Sales': missed_sales,
        'Ending Inv': ending_inventory,
        'Profit': weekly_profit,
        'Cash': st.session_state.cash
    }
    st.session_state.history.append(record)
    st.session_state.last_week_metrics = record
    
    # 9. Advance Week
    st.session_state.week += 1
    if st.session_state.week > MAX_WEEKS:
        st.session_state.game_over = True

# --- UI Components ---

st.set_page_config(page_title="Supply Chain Resilience Commander", layout="wide")

# Initialize State
if 'week' not in st.session_state:
    init_game()

# --- Sidebar ---
with st.sidebar:
    st.title("🏭 SC Commander")
    
    st.markdown("### 📊 Status")
    st.metric("Current Week", f"{st.session_state.week} / {MAX_WEEKS}")
    st.metric("Cash Balance", f"${st.session_state.cash:,.0f}")
    st.metric("Lead Time", f"{st.session_state.lead_time} Weeks")
    
    st.markdown("---")
    
    # Market Intelligence Upgrade
    if not st.session_state.market_intel:
        st.markdown("### 🧠 Strategy")
        if st.button(f"Buy Market Intel (-${MARKET_INTEL_COST})"):
            if st.session_state.cash >= MARKET_INTEL_COST:
                st.session_state.cash -= MARKET_INTEL_COST
                st.session_state.market_intel = True
                st.success("Market Intelligence Purchased!")
                st.rerun()
            else:
                st.error("Insufficient Funds!")
    else:
        st.info("✅ Market Intelligence Active")
        
    st.markdown("---")
    if st.button("🔄 Reset Game"):
        init_game()
        st.rerun()

# --- Main Area ---

st.title("Supply Chain Resilience Commander")
st.markdown("Manage your inventory, anticipate risks, and maximize profit!")

# Game Over Screen
if st.session_state.game_over:
    st.balloons()
    st.header("🏁 Game Over!")
    
    final_cash = st.session_state.cash
    df_hist = pd.DataFrame(st.session_state.history)
    total_profit = df_hist['Profit'].sum() if not df_hist.empty else 0
    
    col1, col2 = st.columns(2)
    col1.metric("Final Cash", f"${final_cash:,.0f}")
    col2.metric("Net Profit Generated", f"${total_profit:,.0f}")
    
    st.subheader("Performance Review")
    st.line_chart(df_hist.set_index('Week')[['Demand', 'Order Qty']])
    
    st.dataframe(df_hist)
    
    if st.button("Play Again"):
        init_game()
        st.rerun()
    
    st.stop() # Stop execution here

# Active Game Dashboard

# 1. Notifications & Warnings
# Black Swan Warning (Week 12)
if st.session_state.week == 12:
    st.toast("⚠️ PORT STRIKE! Lead time increased to 3 weeks!", icon="⚓")
    st.error("⚠️ **BLACK SWAN EVENT:** A port strike has occurred! Lead time has permanently increased to 3 weeks.")

# Gray Rhino Warning (Week 7, if Intel purchased)
if st.session_state.market_intel and st.session_state.week == 7:
    st.warning("🕵️ **INTEL REPORT:** Market analysis predicts a massive demand spike next week due to a viral movie release!")

# 2. Metrics (Last Week's Performance)
if st.session_state.last_week_metrics:
    last = st.session_state.last_week_metrics
    st.markdown(f"### 📉 Week {last['Week']} Results")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sales", f"{last['Sales']} units")
    m2.metric("Missed Sales", f"{last['Missed Sales']} units", delta_color="inverse")
    m3.metric("Weekly Profit", f"${last['Profit']:,.0f}")
    m4.metric("Ending Inventory", f"{last['Ending Inv']} units")
else:
    st.info("👋 Welcome! Place your first order to start the simulation.")

# 3. Action Area
st.markdown("### 📝 Place Order")
with st.form("order_form"):
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        order_qty = st.number_input(
            f"Order Quantity for Week {st.session_state.week}", 
            min_value=0, 
            max_value=500, 
            value=20,
            step=5,
            help="Cost: $60/unit. Arrives in " + str(st.session_state.lead_time) + " weeks."
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True) # Spacing
        submitted = st.form_submit_button("Submit Order 🚚", type="primary")

if submitted:
    process_turn(order_qty)
    st.rerun()

# 4. Visualization (The Bullwhip Effect)
if st.session_state.history:
    st.markdown("### 🐂 The Bullwhip Effect Monitor")
    df = pd.DataFrame(st.session_state.history)
    
    # Chart: Demand vs Order Qty
    chart_data = df.set_index('Week')[['Demand', 'Order Qty']]
    st.line_chart(chart_data)
    
    with st.expander("📜 View Detailed History"):
        st.dataframe(df.style.format({
            'Profit': '${:,.0f}', 
            'Cash': '${:,.0f}'
        }))

# 5. Rules & Info
with st.expander("ℹ️ Game Rules & Parameters"):
    st.markdown(f"""
    - **Goal:** Maximize Cash by Week 20.
    - **Selling Price:** ${UNIT_SELLING_PRICE} | **Cost:** ${UNIT_COST}
    - **Holding Cost:** ${HOLDING_COST}/unit/week (on ending inventory)
    - **Shortage Penalty:** ${SHORTAGE_PENALTY}/unit (missed sales)
    - **Lead Time:** {INITIAL_LEAD_TIME} Weeks (Orders placed now arrive later)
    - **Events:** Watch out for market disruptions!
    """)
