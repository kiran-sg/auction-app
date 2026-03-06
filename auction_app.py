import streamlit as st
import pandas as pd
import openpyxl
from datetime import datetime
import os

# File path
EXCEL_FILE = "HERO CUP - REGISTERED PLAYERS.xlsx"

# Auction configuration - Default values (will be overridden by Excel Team sheet if available)
TEAMS = ["TRIVANDRUM TUSKERS", "INVINCIBLE STRIKERS", "PORALI PADA", "MCC", "OVAL DRAGONS"]
TEAM_INFO = {
    "TRIVANDRUM TUSKERS": {"manager": "Pretheksh", "icon": "Gopi"},
    "INVINCIBLE STRIKERS": {"manager": "Ajith", "icon": "Ashok"},
    "PORALI PADA": {"manager": "Sakthi", "icon": "Akash"},
    "MCC": {"manager": "Girish", "icon": "KP"},
    "OVAL DRAGONS": {"manager": "Nithin", "icon": "Varun"}
}
INITIAL_BUDGET = 5000000  # 50 lakh
MIN_SQUAD_SIZE = 12  # Minimum players per team
MIN_PLAYER_PRICE = 100000  # 1 lakh (Category B base price)
BASE_PRICES = {
    "A+": 500000,  # 5 lakh
    "A": 250000,   # 2.5 lakh
    "B": 100000    # 1 lakh
}

# IP-based access control
# Add the IP addresses that are allowed to take actions (bid, sold, unsold)
# Leave empty to allow all IPs (no restrictions)
ADMIN_IPS = [
    # "192.168.1.100",  # Example: Add your admin IPs here
    # "10.0.0.50",
    "192.168.1.37"
]

def get_client_ip():
    """Get client IP address from Streamlit context"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        from streamlit.web.server.websocket_headers import _get_websocket_headers

        ctx = get_script_run_ctx()
        if ctx is not None:
            headers = _get_websocket_headers()
            if headers:
                # Try to get real IP from various headers
                ip = headers.get("X-Forwarded-For", headers.get("X-Real-Ip", ""))
                if ip:
                    return ip.split(",")[0].strip()
        return None
    except:
        return None

def is_admin_user():
    """Check if current user has admin access"""
    # If ADMIN_IPS is empty, allow all users
    if not ADMIN_IPS:
        return True

    client_ip = get_client_ip()
    if client_ip is None:
        # If we can't determine IP, allow access (for local development)
        return True

    return client_ip in ADMIN_IPS

def get_bid_increment(current_bid):
    """Calculate bid increment based on current bid"""
    if current_bid < 500000:  # Less than 5 lakh
        return 50000  # 50k increment
    else:  # 5 lakh or more
        return 100000  # 1 lakh increment

def calculate_max_bid(remaining_budget, players_count):
    """
    Calculate maximum allowed bid ensuring team can complete minimum squad

    Logic:
    - Team needs MIN_SQUAD_SIZE (12) players total
    - After buying this player, they'll have (players_count + 1) players
    - They still need (MIN_SQUAD_SIZE - players_count - 1) more players
    - Reserve amount = remaining_needed * MIN_PLAYER_PRICE
    - Max bid = remaining_budget - reserve_amount
    """
    remaining_needed = MIN_SQUAD_SIZE - players_count - 1  # -1 for the player being bid on

    if remaining_needed < 0:
        # Already have more than minimum squad
        return remaining_budget

    reserve_amount = remaining_needed * MIN_PLAYER_PRICE
    max_bid = remaining_budget - reserve_amount

    # Can't bid negative or less than minimum
    return max(0, max_bid)

def load_data():
    """Load player data and auction state"""
    # Load players
    df_players = pd.read_excel(EXCEL_FILE, sheet_name='Sheet1')

    # Load team information from Team sheet
    try:
        df_team_info = pd.read_excel(EXCEL_FILE, sheet_name='Team')
        teams_list = df_team_info['Team'].tolist()
        team_info_dict = {}
        for idx, row in df_team_info.iterrows():
            team_info_dict[row['Team']] = {
                'manager': row.get('Manager', 'N/A'),
                'icon': row.get('Icon', 'N/A')
            }
    except:
        # Fallback to default teams if Team sheet doesn't exist
        teams_list = TEAMS
        team_info_dict = TEAM_INFO

    # Try to load auction data if exists
    try:
        df_auction = pd.read_excel(EXCEL_FILE, sheet_name='Auction_Data')
        df_teams = pd.read_excel(EXCEL_FILE, sheet_name='Team_Budgets')
        df_sold = pd.read_excel(EXCEL_FILE, sheet_name='Sold_Players')
    except:
        # Initialize auction data - use Grade column as Category
        df_auction = df_players.copy()
        df_auction['Status'] = 'Pending'  # Pending, Sold, Unsold
        df_auction['Sold_To'] = None
        df_auction['Final_Price'] = None

        # Initialize team budgets
        df_teams = pd.DataFrame({
            'Team': teams_list,
            'Remaining_Budget': [INITIAL_BUDGET] * len(teams_list),
            'Players_Count': [0] * len(teams_list)
        })

        # Initialize sold players
        df_sold = pd.DataFrame(columns=['Player_Name', 'Category', 'Team', 'Price', 'Timestamp'])

    return df_players, df_auction, df_teams, df_sold, teams_list, team_info_dict

def save_data(df_auction, df_teams, df_sold):
    """Save all data to Excel"""
    try:
        # Load existing workbook
        book = openpyxl.load_workbook(EXCEL_FILE)

        # Remove auction sheets if they exist
        sheets_to_remove = ['Auction_Data', 'Team_Budgets', 'Sold_Players']
        for sheet_name in sheets_to_remove:
            if sheet_name in book.sheetnames:
                del book[sheet_name]

        # Save the workbook with removed sheets
        book.save(EXCEL_FILE)
        book.close()
    except Exception as e:
        print(f"Warning during sheet removal: {e}")

    # Write data with replace mode
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_auction.to_excel(writer, sheet_name='Auction_Data', index=False)
        df_teams.to_excel(writer, sheet_name='Team_Budgets', index=False)
        df_sold.to_excel(writer, sheet_name='Sold_Players', index=False)

def format_currency(amount):
    """Format amount in Indian currency (lakhs)"""
    lakhs = amount / 100000
    return f"₹{lakhs:.1f}L"

# Page config
st.set_page_config(page_title="Hero Cup Auction", layout="wide", page_icon="🏏")

# Custom CSS
st.markdown("""
<style>
    .big-font {
        font-size: 48px !important;
        font-weight: bold;
        color: #1f77b4;
    }
    .player-card {
        background-color: #f0f2f6;
        padding: 25px;
        border-radius: 10px;
        margin: 10px 0;
        border: 2px solid #ddd;
    }
    .player-card h2 {
        font-size: 32px !important;
        margin-bottom: 15px;
        color: #1f77b4;
    }
    .player-card p {
        font-size: 18px !important;
        margin: 8px 0;
        line-height: 1.6;
    }
    .team-budget {
        background-color: #e1f5e1;
        padding: 10px;
        border-radius: 8px;
        margin: 5px 0;
        text-align: center;
        border: 2px solid #90ee90;
    }
    .team-budget b {
        font-size: 20px !important;
        display: block;
        margin-bottom: 5px;
    }
    .team-budget-text {
        font-size: 18px !important;
        line-height: 1.3;
    }
    .team-budget-text div {
        margin: 2px 0;
    }
    .sold-player {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border: 2px solid #ffc107;
    }
    .sold-player b {
        font-size: 20px !important;
        color: #333;
    }
    .sold-player br + text {
        font-size: 16px !important;
    }
    .current-bid-section {
        background-color: #e3f2fd;
        padding: 20px;
        border-radius: 10px;
        margin: 15px 0;
        border: 3px solid #2196f3;
    }
    .bid-info {
        font-size: 20px !important;
        font-weight: bold;
    }
    /* Make bid buttons more prominent */
    .stButton > button[kind="primary"] {
        font-size: 18px !important;
        font-weight: bold !important;
        padding: 12px 24px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
        transition: all 0.3s ease !important;
    }
    .stButton > button[kind="primary"]:hover:not(:disabled) {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15) !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'current_player_idx' not in st.session_state:
    st.session_state.current_player_idx = None
if 'current_bid' not in st.session_state:
    st.session_state.current_bid = 0
if 'current_bidder' not in st.session_state:
    st.session_state.current_bidder = None
if 'selected_category' not in st.session_state:
    st.session_state.selected_category = 'A+'
if 'show_sold_dialog' not in st.session_state:
    st.session_state.show_sold_dialog = False
if 'sold_player_info' not in st.session_state:
    st.session_state.sold_player_info = None

# Dialog function for sold notification
@st.dialog("🎉 PLAYER SOLD! 🎉", width="large")
def show_sold_notification():
    if st.session_state.sold_player_info:
        info = st.session_state.sold_player_info
        st.balloons()

        # Create columns for photo and info
        col1, col2 = st.columns([1, 2])

        with col1:
            st.image(info['photo_url'], width=250, caption="")

        with col2:
            st.markdown(f"""
            <div style="text-align: center; padding: 20px;">
                <div style="font-size: 48px; font-weight: bold; color: #1f77b4; margin: 20px 0;">
                    {info['player_name']}
                </div>
                <div style="font-size: 32px; color: #28a745; margin: 20px 0;">
                    Sold to: <b>{info['team']}</b>
                </div>
                <div style="font-size: 32px; color: #ff6600; margin: 20px 0;">
                    Price: <b>{info['price']}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ Continue to Next Player", type="primary", use_container_width=True):
            st.session_state.show_sold_dialog = False
            st.session_state.sold_player_info = None
            st.rerun()

# Main app
st.title("🏏 HERO CUP - Player Auction")

# Load data
df_players, df_auction, df_teams, df_sold, TEAMS, TEAM_INFO = load_data()

# Show sold dialog if needed
if st.session_state.show_sold_dialog:
    show_sold_notification()

# Sidebar navigation
page = st.sidebar.radio("Navigation", ["Auction", "Team Overview", "Auction History", "All Players"])

if page == "Auction":
    st.header("Live Auction")

    # Check if user has admin access
    is_admin = is_admin_user()

    # Show view-only message if user doesn't have admin access
    if not is_admin:
        st.warning("🔒 **View-Only Mode:** You are viewing the auction in read-only mode. Only authorized IPs can place bids and mark players as sold/unsold.")

    # Display team budgets
    st.subheader("💰 Team Budgets")
    cols = st.columns(len(TEAMS))
    for i, (idx, team_row) in enumerate(df_teams.iterrows()):
        with cols[i]:
            spent = INITIAL_BUDGET - team_row['Remaining_Budget']
            team_name = team_row['Team']
            team_details = TEAM_INFO.get(team_name, {"manager": "N/A", "icon": "N/A"})
            st.markdown(f"""
            <div class="team-budget">
                <b>{team_name}</b>
                <div style="font-size: 16px; font-weight: bold; color: #333; margin: 5px 0;">Manager: {team_details['manager']} | Icon: {team_details['icon']}</div>
                <div class="team-budget-text">
                    <div>💵 Budget: <b>{format_currency(team_row['Remaining_Budget'])}</b></div>
                    <div>💸 Spent: <b>{format_currency(spent)}</b></div>
                    <div>👥 Players: <b>{team_row['Players_Count']}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Category Selection
    st.subheader("🎭 Select Category")

    # Category stats
    cat_cols = st.columns([1, 1, 1, 1])
    categories = ['A+', 'A', 'B']

    for i, cat in enumerate(categories):
        with cat_cols[i]:
            total_cat = len(df_auction[df_auction['Grade'] == cat])
            pending_cat = len(df_auction[(df_auction['Grade'] == cat) & (df_auction['Status'] == 'Pending')])
            st.metric(f"{cat} Players", f"{pending_cat}/{total_cat}")

    # Unsold players count
    with cat_cols[3]:
        unsold_count = len(df_auction[df_auction['Status'] == 'Unsold'])
        st.metric("Unsold", f"{unsold_count}")

    # Category selection buttons
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    with col1:
        if st.button("Category A+", type="primary" if st.session_state.selected_category == 'A+' else "secondary", use_container_width=True):
            st.session_state.selected_category = 'A+'
            st.session_state.current_player_idx = 0
            st.session_state.current_bid = 0
            st.session_state.current_bidder = None
            st.rerun()

    with col2:
        if st.button("Category A", type="primary" if st.session_state.selected_category == 'A' else "secondary", use_container_width=True):
            st.session_state.selected_category = 'A'
            st.session_state.current_player_idx = 0
            st.session_state.current_bid = 0
            st.session_state.current_bidder = None
            st.rerun()

    with col3:
        if st.button("Category B", type="primary" if st.session_state.selected_category == 'B' else "secondary", use_container_width=True):
            st.session_state.selected_category = 'B'
            st.session_state.current_player_idx = 0
            st.session_state.current_bid = 0
            st.session_state.current_bidder = None
            st.rerun()

    with col4:
        unsold_count = len(df_auction[df_auction['Status'] == 'Unsold'])
        if st.button("Unsold Players", type="primary" if st.session_state.selected_category == 'Unsold' else "secondary", use_container_width=True, disabled=unsold_count == 0):
            st.session_state.selected_category = 'Unsold'
            st.session_state.current_player_idx = 0
            st.session_state.current_bid = 0
            st.session_state.current_bidder = None
            st.rerun()

    st.divider()

    # Get pending players for selected category
    if st.session_state.selected_category == 'Unsold':
        # Get all unsold players regardless of grade
        pending_players = df_auction[df_auction['Status'] == 'Unsold'].copy()
    else:
        # Get pending players for the specific grade
        pending_players = df_auction[
            (df_auction['Status'] == 'Pending') &
            (df_auction['Grade'] == st.session_state.selected_category)
        ].copy()

    if len(pending_players) == 0:
        if st.session_state.selected_category == 'Unsold':
            st.info(f"✅ All unsold players have been processed!")
        else:
            st.info(f"✅ All Category {st.session_state.selected_category} players have been processed!")
        st.info("Switch to another category to continue the auction.")
    else:
        # Display current category
        if st.session_state.selected_category == 'Unsold':
            st.markdown(f"""
            <div style="background-color: #ff6b6b; color: white; padding: 15px; border-radius: 8px; text-align: center; margin: 10px 0;">
                <h2 style="margin: 0; font-size: 28px;">Current Category: Unsold Players (from all categories)</h2>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background-color: #4CAF50; color: white; padding: 15px; border-radius: 8px; text-align: center; margin: 10px 0;">
                <h2 style="margin: 0; font-size: 28px;">Current Category: {st.session_state.selected_category} - Base Price: {format_currency(BASE_PRICES[st.session_state.selected_category])}</h2>
            </div>
            """, unsafe_allow_html=True)

        # Select player for auction
        col1, col2 = st.columns([3, 1])
        with col1:
            player_options = pending_players.apply(
                lambda x: f"{x['Name']} - {x['Team']} - Category: {x['Grade']}",
                axis=1
            ).tolist()

            if st.session_state.current_player_idx is None or st.session_state.current_player_idx >= len(pending_players):
                default_idx = 0
            else:
                default_idx = st.session_state.current_player_idx

            selected_player = st.selectbox(
                f"Select Player ({len(pending_players)} remaining)",
                range(len(pending_players)),
                format_func=lambda x: player_options[x],
                index=min(default_idx, len(pending_players)-1) if len(pending_players) > 0 else 0
            )

            st.session_state.current_player_idx = selected_player

        with col2:
            if st.button("🔄 Refresh Data"):
                st.rerun()

        # Current player details
        current_player = pending_players.iloc[selected_player]
        # For unsold players, base price is 1 lakh regardless of original grade
        if st.session_state.selected_category == 'Unsold':
            base_price = 100000  # 1 lakh
        else:
            base_price = BASE_PRICES.get(current_player['Grade'], 0)

        if st.session_state.current_bid == 0:
            st.session_state.current_bid = base_price

        # Show unsold badge if this is from unsold category
        unsold_badge = ""
        if st.session_state.selected_category == 'Unsold':
            unsold_badge = ' 🔴 Previously Unsold'

        # Get availability info
        available_march20 = current_player.get('Are you available on March 20 (Friday)?', 'N/A')
        available_time = current_player.get('Available Time (e.g., 6 PM - 8 PM)', 'N/A')

        # Show time only if partially available
        if available_march20 == "Partially available":
            availability_text = f"{available_march20} | Time: {available_time}"
        else:
            availability_text = f"{available_march20}"

        # Get additional skills info
        batting_hand = current_player.get('Batting Hand', '')
        bowling_arm = current_player.get('Bowling Arm', '')
        bowling_style = current_player.get('Bowling Style', '')

        # Build skills text
        skills_text = f"Batter: {current_player['Are you a Batter?']} | Bowler: {current_player['Are you a Bowler?']} | WK: {current_player['Wicket Keeper (WK)']}"

        # Add optional fields if available
        if batting_hand and str(batting_hand).strip() not in ['', 'nan', 'None']:
            skills_text += f" | Batting Hand: {batting_hand}"
        if bowling_arm and str(bowling_arm).strip() not in ['', 'nan', 'None']:
            skills_text += f" | Bowling Arm: {bowling_arm}"
        if bowling_style and str(bowling_style).strip() not in ['', 'nan', 'None']:
            skills_text += f" | Bowling Style: {bowling_style}"

        # Get player photo
        player_photo = current_player.get('Upload Player Photo', '')
        # Default user icon
        default_photo = "https://cdn-icons-png.flaticon.com/512/149/149071.png"

        # Use player photo if available, otherwise default
        photo_url = player_photo if player_photo and str(player_photo).strip() not in ['', 'nan', 'None'] else default_photo

        st.divider()

        # Merged Player Details and Bidding section
        st.subheader("🎯 Current Bid & Player Details")

        # Calculate next bid amount
        if st.session_state.current_bidder is None:
            next_bid_amount = st.session_state.current_bid  # First bid at base price
            next_bid_label = "First Bid (Base Price)"
        else:
            increment = get_bid_increment(st.session_state.current_bid)
            next_bid_amount = st.session_state.current_bid + increment
            next_bid_label = "Next Bid"

        # Create the card with columns using container
        with st.container():
            st.markdown("""
            <style>
            .stContainer > div {
                background-color: #e3f2fd;
                padding: 20px;
                border-radius: 10px;
                border: 3px solid #2196f3;
            }
            </style>
            """, unsafe_allow_html=True)

            col_left, col_center, col_right = st.columns([2, 2, 1])

            with col_left:
                st.markdown(f"<h2 style='color: #1f77b4; font-size: 28px;'>{current_player['Name']}{unsold_badge}</h2>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 16px; margin: 5px 0;'><b>Category:</b> {current_player['Grade']} | <b>Base Price:</b> {format_currency(base_price)}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 16px; margin: 5px 0;'><b>Original Team:</b> {current_player['Team']}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 16px; margin: 5px 0;'><b>Skills:</b> {skills_text}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 16px; margin: 5px 0;'><b>Available on March 20:</b> {availability_text}</p>", unsafe_allow_html=True)

            with col_center:
                st.markdown("<div style='text-align: center; padding-top: 20px;'>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 22px; color: #555;'>Current Bid Amount</p>", unsafe_allow_html=True)
                st.markdown(f"<p class='big-font'>{format_currency(st.session_state.current_bid)}</p>", unsafe_allow_html=True)
                if st.session_state.current_bidder:
                    st.markdown(f"<p style='font-size: 30px; font-weight: bold; color: #28a745; margin-top: 15px;'>CURRENT BID: {st.session_state.current_bidder}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-size: 18px; color: #666; margin-top: 10px;'>{next_bid_label}: <b>{format_currency(next_bid_amount)}</b></p>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with col_right:
                st.image(photo_url, width=200, caption="Player Photo")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🔄 Reset Bid", use_container_width=True, disabled=not is_admin):
                st.session_state.current_bid = base_price
                st.session_state.current_bidder = None
                st.rerun()

        # Bidding buttons
        st.subheader("📢 Place Bid")

        # Info about squad requirements
        st.markdown(f"""
        <div style="background-color: #d1ecf1; padding: 15px; border-radius: 8px; border-left: 5px solid #0c5460; margin: 10px 0;">
            <span style="font-size: 18px; color: #0c5460;">
                💡 <b>Important:</b> Each team must maintain enough budget to complete a minimum squad of {MIN_SQUAD_SIZE} players. Maximum bid shown accounts for remaining squad needs.
            </span>
        </div>
        """, unsafe_allow_html=True)

        bid_cols = st.columns(len(TEAMS))

        for i, team in enumerate(TEAMS):
            with bid_cols[i]:
                team_data = df_teams[df_teams['Team'] == team].iloc[0]
                team_budget = team_data['Remaining_Budget']
                team_players = team_data['Players_Count']

                # Calculate maximum allowed bid
                max_allowed_bid = calculate_max_bid(team_budget, team_players)

                # First bid should be at base price, subsequent bids add increment
                if st.session_state.current_bidder is None:
                    next_bid = st.session_state.current_bid  # First bid at base price
                else:
                    next_bid = st.session_state.current_bid + get_bid_increment(st.session_state.current_bid)

                # Check minimum budget requirements
                can_bid = True
                reason = ""

                # Check if team budget is less than minimum player price (1 lakh)
                if team_budget < MIN_PLAYER_PRICE:
                    can_bid = False
                    reason = f"Budget below minimum (₹{format_currency(MIN_PLAYER_PRICE)})"
                # Check if team budget is less than player's base price
                elif team_budget < base_price:
                    can_bid = False
                    reason = f"Budget below base price ({format_currency(base_price)})"
                # Prevent same team from bidding consecutively
                elif st.session_state.current_bidder == team:
                    can_bid = False
                    reason = "Already leading - wait for another team"
                # Check if team has enough budget for next bid
                elif team_budget < next_bid:
                    can_bid = False
                    reason = "Insufficient budget"
                # Check if next bid exceeds max allowed bid (squad completion rule)
                elif next_bid > max_allowed_bid:
                    can_bid = False
                    slots_needed = MIN_SQUAD_SIZE - team_players
                    reason = f"Max bid: {format_currency(max_allowed_bid)}\n({slots_needed} slots to fill)"
                # All checks passed
                else:
                    can_bid = (team_budget >= next_bid) and (next_bid <= max_allowed_bid)

                # Disable bidding for non-admin users
                can_bid = can_bid and is_admin

                if st.button(
                    f"💰 BID - {team}",
                    key=f"bid_{team}",
                    disabled=not can_bid,
                    type="primary",
                    use_container_width=True
                ):
                    st.session_state.current_bid = next_bid
                    st.session_state.current_bidder = team
                    st.rerun()

                # Show team info
                slots_remaining = MIN_SQUAD_SIZE - team_players
                st.markdown(f"<div style='font-size: 20px; margin-top: 8px;'><b>Budget:</b> {format_currency(team_budget)}</div>", unsafe_allow_html=True)
                if slots_remaining > 0:
                    st.markdown(f"<div style='font-size: 20px;'><b>Max Bid:</b> {format_currency(max_allowed_bid)}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 20px; color: #ff6600;'><b>{slots_remaining} slots left</b></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-size: 20px; color: #28a745;'><b>✓ Squad complete</b></div>", unsafe_allow_html=True)

                if not can_bid:
                    if not is_admin:
                        st.markdown(f"<div style='font-size: 14px; color: #dc3545; margin-top: 5px;'>⚠️ View-only mode</div>", unsafe_allow_html=True)
                    elif reason:
                        st.markdown(f"<div style='font-size: 14px; color: #dc3545; margin-top: 5px;'>⚠️ {reason}</div>", unsafe_allow_html=True)

        st.divider()

        # Finalize actions
        col1, col2 = st.columns(2)

        with col1:
            # Disable SOLD button if there's no current bid or user is not admin
            sold_disabled = (st.session_state.current_bidder is None) or (not is_admin)
            if st.button("✅ SOLD", type="primary", use_container_width=True, disabled=sold_disabled):
                # Update auction data
                player_idx = current_player.name
                df_auction.at[player_idx, 'Status'] = 'Sold'
                df_auction.at[player_idx, 'Sold_To'] = st.session_state.current_bidder
                df_auction.at[player_idx, 'Final_Price'] = st.session_state.current_bid

                # Update team budget
                team_idx = df_teams[df_teams['Team'] == st.session_state.current_bidder].index[0]
                df_teams.at[team_idx, 'Remaining_Budget'] -= st.session_state.current_bid
                df_teams.at[team_idx, 'Players_Count'] += 1

                # Add to sold players
                new_sold = pd.DataFrame({
                    'Player_Name': [current_player['Name']],
                    'Category': [current_player['Grade']],
                    'Team': [st.session_state.current_bidder],
                    'Price': [st.session_state.current_bid],
                    'Timestamp': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                })
                df_sold = pd.concat([df_sold, new_sold], ignore_index=True)

                # Save
                save_data(df_auction, df_teams, df_sold)

                # Store sold information for dialog
                st.session_state.sold_player_info = {
                    'player_name': current_player['Name'],
                    'team': st.session_state.current_bidder,
                    'price': format_currency(st.session_state.current_bid),
                    'photo_url': photo_url
                }

                # Reset state and move to next player
                st.session_state.current_bid = 0
                st.session_state.current_bidder = None
                # Reset to first player (the list will be updated after rerun)
                st.session_state.current_player_idx = 0

                # Show dialog
                st.session_state.show_sold_dialog = True
                st.rerun()

            # Show message when SOLD is disabled
            if sold_disabled:
                if not is_admin:
                    st.caption("⚠️ View-only mode")
                else:
                    st.caption("⚠️ No bid placed yet")

        with col2:
            # Disable UNSOLD button if there's a current bid or user is not admin
            unsold_disabled = (st.session_state.current_bidder is not None) or (not is_admin)
            if st.button("❌ UNSOLD", use_container_width=True, disabled=unsold_disabled):
                player_idx = current_player.name
                df_auction.at[player_idx, 'Status'] = 'Unsold'
                save_data(df_auction, df_teams, df_sold)

                # Reset state and move to next player
                st.session_state.current_bid = 0
                st.session_state.current_bidder = None
                st.session_state.current_player_idx = 0

                st.info(f"{current_player['Name']} marked as UNSOLD")
                st.rerun()

            # Show message when UNSOLD is disabled
            if unsold_disabled:
                if not is_admin:
                    st.caption("⚠️ View-only mode")
                else:
                    st.caption("⚠️ Cannot mark as unsold - bid already placed")

elif page == "Team Overview":
    st.header("Team Overview")

    # Team selection
    selected_team = st.selectbox("Select Team", TEAMS)

    team_data = df_teams[df_teams['Team'] == selected_team].iloc[0]
    team_players = df_auction[df_auction['Sold_To'] == selected_team]

    # Team stats
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Remaining Budget", format_currency(team_data['Remaining_Budget']))
    with col2:
        st.metric("Spent", format_currency(INITIAL_BUDGET - team_data['Remaining_Budget']))
    with col3:
        st.metric("Players", team_data['Players_Count'])
    with col4:
        slots_remaining = MIN_SQUAD_SIZE - team_data['Players_Count']
        st.metric("Slots Remaining", slots_remaining)
    with col5:
        max_bid = calculate_max_bid(team_data['Remaining_Budget'], team_data['Players_Count'])
        st.metric("Max Bid Allowed", format_currency(max_bid))

    # Squad status
    st.divider()
    if slots_remaining > 0:
        reserve_needed = slots_remaining * MIN_PLAYER_PRICE
        st.info(f"📊 **Squad Status:** {team_data['Players_Count']}/{MIN_SQUAD_SIZE} players | "
                f"Must reserve {format_currency(reserve_needed)} for {slots_remaining} remaining slots (@ {format_currency(MIN_PLAYER_PRICE)} minimum each)")
    else:
        st.success(f"✅ **Squad Complete!** {team_data['Players_Count']} players acquired. Can use full budget for additional players.")

    # Player list
    if len(team_players) > 0:
        st.subheader("👥 Players")
        for idx, player in team_players.iterrows():
            available_march20 = player.get('Are you available on March 20 (Friday)?', 'N/A')
            available_time = player.get('Available Time (e.g., 6 PM - 8 PM)', 'N/A')

            # Show time only if partially available
            availability_text = f"<span style='font-size: 16px;'>📅 Availability: <b>{available_march20}</b></span>"
            if available_march20 == "Partially available":
                availability_text += f" | <span style='font-size: 16px;'>⏰ Time: <b>{available_time}</b></span>"

            # Build skills text with optional fields
            player_skills = f"Batter: <b>{player['Are you a Batter?']}</b>, Bowler: <b>{player['Are you a Bowler?']}</b>, WK: <b>{player['Wicket Keeper (WK)']}</b>"

            batting_hand = player.get('Batting Hand', '')
            bowling_arm = player.get('Bowling Arm', '')
            bowling_style = player.get('Bowling Style', '')

            if batting_hand and str(batting_hand).strip() not in ['', 'nan', 'None']:
                player_skills += f", Batting Hand: <b>{batting_hand}</b>"
            if bowling_arm and str(bowling_arm).strip() not in ['', 'nan', 'None']:
                player_skills += f", Bowling Arm: <b>{bowling_arm}</b>"
            if bowling_style and str(bowling_style).strip() not in ['', 'nan', 'None']:
                player_skills += f", Bowling Style: <b>{bowling_style}</b>"

            st.markdown(f"""
            <div class="sold-player">
                <b>{player['Name']}</b> - Category: <b>{player['Grade']}</b><br>
                <span style='font-size: 16px;'>💰 Price: <b>{format_currency(player['Final_Price'])}</b></span><br>
                <span style='font-size: 16px;'>🏏 Skills: {player_skills}</span><br>
                {availability_text}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No players yet")

elif page == "Auction History":
    st.header("Auction History")

    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        team_filter = st.selectbox("Filter by Team", ["All"] + TEAMS)
    with col2:
        category_filter = st.selectbox("Filter by Category", ["All", "A+", "A", "B"])
    with col3:
        status_filter = st.selectbox("Filter by Status", ["All", "Sold", "Unsold"])

    # Apply filters
    filtered_df = df_auction.copy()
    if team_filter != "All":
        filtered_df = filtered_df[filtered_df['Sold_To'] == team_filter]
    if category_filter != "All":
        filtered_df = filtered_df[filtered_df['Grade'] == category_filter]
    if status_filter != "All":
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]

    # Display sold players
    sold_df = filtered_df[filtered_df['Status'] == 'Sold'].copy()
    if len(sold_df) > 0:
        sold_df['Final_Price_Formatted'] = sold_df['Final_Price'].apply(format_currency)
        sold_df['Category'] = sold_df['Grade']
        display_cols = ['Name', 'Category', 'Sold_To', 'Final_Price_Formatted', 'Team']
        st.dataframe(sold_df[display_cols], use_container_width=True, hide_index=True)

        # Summary stats
        st.subheader("Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Players Sold", len(sold_df))
        with col2:
            st.metric("Total Amount", format_currency(sold_df['Final_Price'].sum()))
        with col3:
            st.metric("Average Price", format_currency(sold_df['Final_Price'].mean()))
    else:
        st.info("No sold players match the filters")

    # Display unsold players
    unsold_df = filtered_df[filtered_df['Status'] == 'Unsold'].copy()
    if len(unsold_df) > 0:
        st.subheader("Unsold Players")
        unsold_df['Category'] = unsold_df['Grade']
        display_cols = ['Name', 'Category', 'Team']
        st.dataframe(unsold_df[display_cols], use_container_width=True, hide_index=True)

elif page == "All Players":
    st.header("📋 All Players")

    # Filters and sorting
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        category_filter = st.selectbox("Filter by Category", ["All", "A+", "A", "B"])
    with col2:
        status_filter = st.selectbox("Filter by Status", ["All", "Sold", "Unsold", "Pending"])
    with col3:
        team_filter = st.selectbox("Filter by Sold To Team", ["All"] + TEAMS)
    with col4:
        sort_by = st.selectbox("Sort by", ["Name", "Category", "Status", "Sold To", "Price (High to Low)", "Price (Low to High)"])

    # Apply filters
    filtered_df = df_auction.copy()

    # Exclude MANAGER and ICON players by their actual names
    exclude_names = []
    for team_info in TEAM_INFO.values():
        exclude_names.append(team_info['manager'])
        exclude_names.append(team_info['icon'])

    filtered_df = filtered_df[~filtered_df['Name'].isin(exclude_names)]

    if category_filter != "All":
        filtered_df = filtered_df[filtered_df['Grade'] == category_filter]

    if status_filter != "All":
        filtered_df = filtered_df[filtered_df['Status'] == status_filter]

    if team_filter != "All":
        filtered_df = filtered_df[filtered_df['Sold_To'] == team_filter]

    # Apply sorting
    if sort_by == "Name":
        filtered_df = filtered_df.sort_values('Name')
    elif sort_by == "Category":
        # Custom sort order for categories
        category_order = {'A+': 0, 'A': 1, 'B': 2}
        filtered_df['Category_Order'] = filtered_df['Grade'].map(category_order)
        filtered_df = filtered_df.sort_values('Category_Order')
        filtered_df = filtered_df.drop('Category_Order', axis=1)
    elif sort_by == "Status":
        filtered_df = filtered_df.sort_values('Status')
    elif sort_by == "Sold To":
        filtered_df = filtered_df.sort_values('Sold_To', na_position='last')
    elif sort_by == "Price (High to Low)":
        filtered_df = filtered_df.sort_values('Final_Price', ascending=False, na_position='last')
    elif sort_by == "Price (Low to High)":
        filtered_df = filtered_df.sort_values('Final_Price', ascending=True, na_position='last')

    # Prepare display dataframe
    display_df = filtered_df.copy()
    display_df['Category'] = display_df['Grade']

    # Format price for display
    display_df['Price'] = display_df['Final_Price'].apply(
        lambda x: format_currency(x) if pd.notna(x) else '-'
    )

    # Replace NaN in Sold_To with '-'
    display_df['Sold To'] = display_df['Sold_To'].fillna('-')

    # Select columns to display
    display_cols = ['Name', 'Category', 'Team', 'Status', 'Sold To', 'Price']

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Players", len(filtered_df))
    with col2:
        sold_count = len(filtered_df[filtered_df['Status'] == 'Sold'])
        st.metric("Sold", sold_count)
    with col3:
        unsold_count = len(filtered_df[filtered_df['Status'] == 'Unsold'])
        st.metric("Unsold", unsold_count)
    with col4:
        pending_count = len(filtered_df[filtered_df['Status'] == 'Pending'])
        st.metric("Pending", pending_count)

    st.divider()

    # Display the dataframe
    if len(display_df) > 0:
        st.dataframe(
            display_df[display_cols],
            use_container_width=True,
            hide_index=True,
            height=600
        )
    else:
        st.info("No players match the selected filters")

# Footer
st.sidebar.divider()
st.sidebar.info("""
**Auction Rules:**
- Budget per team: ₹50L
- Minimum squad: 12 players
- Base prices: A+ (₹5L), A (₹2.5L), B (₹1L)
- Bid increment:
  - ₹1L-₹5L: ₹50k
  - ≥₹5L: ₹1L

**Smart Budget Control:**
- Max bid = Budget - (Slots left × ₹1L)
- Ensures teams can complete squads
""")
