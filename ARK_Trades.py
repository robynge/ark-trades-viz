"""ARK Trades Visualization — K-line chart with buy/sell markers."""

import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TRADES_FILE = os.path.join(DATA_DIR, "ark_trades_summary.xlsx")
PRICES_DIR = os.path.join(DATA_DIR, "prices")

BG_COLOR = "#0E1117"
ARK_ETFS = ["ARKK", "ARKQ", "ARKW", "ARKG", "ARKF", "ARKX"]

MA_PERIODS = {8: "#F39C12", 13: "#E74C3C", 21: "#3498DB", 34: "#9B59B6"}

st.set_page_config(page_title="ARK Trades", page_icon="📈", layout="wide")


def format_shares(n):
    """Format share count: 32000 → '32K', 112 → '112'."""
    if n >= 1000:
        v = n / 1000
        return f"{v:.0f}K" if v >= 100 or v == int(v) else f"{v:.1f}K"
    return str(int(n))


@st.cache_data
def load_trades():
    df = pd.read_excel(TRADES_FILE)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


@st.cache_data
def load_prices(ticker: str):
    path = os.path.join(PRICES_DIR, f"{ticker}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def build_chart(ticker, company_name, prices, trades):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.8, 0.2], vertical_spacing=0.03,
    )

    # ── 1. Candlestick ──────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=prices.index,
        open=prices["Open"], high=prices["High"],
        low=prices["Low"], close=prices["Close"],
        increasing=dict(line=dict(color="#2ECC71"), fillcolor="#2ECC71"),
        decreasing=dict(line=dict(color="#E8E8E8"), fillcolor=BG_COLOR),
        name="K-line",
    ), row=1, col=1)

    # ── 2. Moving Averages ───────────────────────────────────────────
    for period, color in MA_PERIODS.items():
        ma = prices["Close"].rolling(period).mean()
        fig.add_trace(go.Scatter(
            x=prices.index, y=ma, mode="lines",
            line=dict(width=1, color=color),
            name=f"MA{period}", hoverinfo="skip",
        ), row=1, col=1)

    # ── 3. Volume ────────────────────────────────────────────────────
    vol_colors = [
        "#2ECC71" if c >= o else "#888888"
        for c, o in zip(prices["Close"], prices["Open"])
    ]
    fig.add_trace(go.Bar(
        x=prices.index, y=prices["Volume"],
        marker_color=vol_colors, name="Volume",
        hovertemplate="%{x|%Y-%m-%d}<br>Volume: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ── 4. Buy / Sell markers ────────────────────────────────────────
    price_range = prices["High"].max() - prices["Low"].min()
    offset_unit = price_range * 0.04

    for direction, marker_sym, fill_color in [
        ("Buy",  "triangle-up",   "rgba(46,204,113,0.85)"),
        ("Sell", "triangle-down", "rgba(240,100,120,0.85)"),
    ]:
        dir_trades = trades[trades["Direction"] == direction]
        if dir_trades.empty:
            continue

        xs, ys, labels, hovers = [], [], [], []
        date_stack: dict[tuple, int] = {}

        for _, row in dir_trades.iterrows():
            trade_date = row["Date"]
            idx = prices.index.searchsorted(trade_date)
            if idx >= len(prices):
                idx = len(prices) - 1
            pd_date = prices.index[idx]

            # stacking offset for multiple trades on same date
            key = (pd_date, direction)
            date_stack[key] = date_stack.get(key, 0) + 1
            stack_n = date_stack[key]

            if direction == "Buy":
                y = prices.loc[pd_date, "Low"] - offset_unit * stack_n
            else:
                y = prices.loc[pd_date, "High"] + offset_unit * stack_n

            xs.append(pd_date)
            ys.append(y)

            shares = row["Shares Traded"]
            labels.append(f"{'Buy' if direction == 'Buy' else 'Sell'}<br>{format_shares(shares)}")

            hovers.append(
                f"<b>{direction}</b><br>"
                f"Ticker: {ticker} ({company_name})<br>"
                f"Date: {trade_date.strftime('%Y-%m-%d')}<br>"
                f"ETF: {row['ETF']}<br>"
                f"Shares: {row['Shares Traded']:,.0f}<br>"
                f"% of ETF: {row['% of Total ETF']:.4f}"
            )

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            marker=dict(symbol=marker_sym, size=12, color=fill_color, line=dict(width=1, color="white")),
            text=labels,
            textfont=dict(color="white", size=8, family="Arial"),
            textposition="middle center",
            hovertext=hovers, hoverinfo="text",
            name=direction,
        ), row=1, col=1)

    # ── Layout ───────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        title=dict(text=f"{ticker} — {company_name}", font=dict(size=18)),
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=50, r=20, t=50, b=30),
        height=660,
        xaxis_rangeslider_visible=False,
        xaxis2_rangeslider_visible=True,
        xaxis2_rangeslider_thickness=0.06,
    )

    grid_color = "rgba(255,255,255,0.07)"
    fig.update_yaxes(gridcolor=grid_color)
    fig.update_xaxes(gridcolor=grid_color)

    return fig


def main():
    st.title("ARK Trades Visualization")

    trades = load_trades()

    ticker_company = (
        trades.drop_duplicates("Ticker")[["Ticker", "Company Name"]]
        .set_index("Ticker")["Company Name"]
        .to_dict()
    )

    available = sorted(
        t for t in ticker_company if os.path.exists(os.path.join(PRICES_DIR, f"{t}.csv"))
    )

    if not available:
        st.error("No price data found. Run `python fetch_prices.py` first.")
        return

    # Ticker selector on main page
    options = [f"{t} — {ticker_company[t]}" for t in available]
    selection = st.selectbox("Select Stock", options, index=0)
    ticker = selection.split(" — ")[0]
    company_name = ticker_company[ticker]

    prices = load_prices(ticker)
    if prices is None or prices.empty:
        st.warning(f"No price data for {ticker}.")
        return

    ticker_trades = trades[trades["Ticker"] == ticker].sort_values("Date")

    # ETF toggle buttons
    etfs_with_trades = set(ticker_trades["ETF"].unique())
    cols = st.columns(len(ARK_ETFS))
    active_etfs = []
    for i, etf in enumerate(ARK_ETFS):
        has_trades = etf in etfs_with_trades
        with cols[i]:
            on = st.toggle(etf, value=has_trades, disabled=not has_trades)
            if on:
                active_etfs.append(etf)

    # Filter trades by selected ETFs
    filtered_trades = ticker_trades[ticker_trades["ETF"].isin(active_etfs)]

    fig = build_chart(ticker, company_name, prices, filtered_trades)
    st.plotly_chart(fig, use_container_width=True)

    # Trade table
    st.subheader(f"Trade History ({len(filtered_trades)} trades)")
    display_df = filtered_trades[["Date", "ETF", "Direction", "Shares Traded", "% of Total ETF"]].copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    display_df["Shares Traded"] = display_df["Shares Traded"].apply(lambda x: f"{x:,.0f}")
    display_df["% of Total ETF"] = display_df["% of Total ETF"].apply(lambda x: f"{x:.4f}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
