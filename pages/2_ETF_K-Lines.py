"""ARK ETF K-line charts with daily trade details on hover."""

import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
TRADES_FILE = os.path.join(DATA_DIR, "ark_trades_summary.xlsx")
PRICES_DIR = os.path.join(DATA_DIR, "prices")

BG_COLOR = "#0E1117"
ARK_ETFS = ["ARKK", "ARKQ", "ARKW", "ARKG", "ARKF", "ARKX"]
MA_PERIODS = {8: "#F39C12", 13: "#E74C3C", 21: "#3498DB", 34: "#9B59B6"}

st.set_page_config(page_title="ETF K-Lines", page_icon="📊", layout="wide")


def format_shares(n):
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


def build_daily_hover(etf_trades: pd.DataFrame, price_dates: pd.DatetimeIndex):
    """Build hover text for each trading day, showing what was bought/sold."""
    hover_texts = []
    for date in price_dates:
        day_trades = etf_trades[etf_trades["Date"] == date]
        if day_trades.empty:
            hover_texts.append("")
            continue

        lines = [f"<b>{date.strftime('%Y-%m-%d')} Trades:</b>"]
        buys = day_trades[day_trades["Direction"] == "Buy"]
        sells = day_trades[day_trades["Direction"] == "Sell"]

        if not buys.empty:
            buy_items = [f"{r['Ticker']} ({format_shares(r['Shares Traded'])})" for _, r in buys.iterrows()]
            lines.append(f"<span style='color:#2ECC71'>Buy:</span> {', '.join(buy_items)}")
        if not sells.empty:
            sell_items = [f"{r['Ticker']} ({format_shares(r['Shares Traded'])})" for _, r in sells.iterrows()]
            lines.append(f"<span style='color:#F06478'>Sell:</span> {', '.join(sell_items)}")

        hover_texts.append("<br>".join(lines))
    return hover_texts


def build_etf_chart(etf: str, prices: pd.DataFrame, trades: pd.DataFrame):
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

    # ── 3. Full-width invisible trace for trade-detail hover ─────────
    hover_texts = build_daily_hover(trades, prices.index)
    # Show date for no-trade days, trade details for trade days
    full_hover = []
    for i, txt in enumerate(hover_texts):
        if txt:
            full_hover.append(txt)
        else:
            full_hover.append(f"{prices.index[i].strftime('%Y-%m-%d')}<br>No trades")

    fig.add_trace(go.Scatter(
        x=prices.index, y=prices["Close"],
        mode="lines", line=dict(width=0, color="rgba(0,0,0,0)"),
        hovertext=full_hover, hoverinfo="text",
        name="Trades", showlegend=False,
    ), row=1, col=1)

    # ── 4. Volume ────────────────────────────────────────────────────
    vol_colors = [
        "#2ECC71" if c >= o else "#888888"
        for c, o in zip(prices["Close"], prices["Open"])
    ]
    fig.add_trace(go.Bar(
        x=prices.index, y=prices["Volume"],
        marker_color=vol_colors, name="Volume",
        hovertemplate="%{x|%Y-%m-%d}<br>Volume: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    # ── Layout ───────────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        title=dict(text=f"{etf} — K-Line & Daily Trades", font=dict(size=18)),
        hovermode="x unified",
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
    st.title("ARK ETF K-Lines")

    trades = load_trades()

    etf = st.selectbox("Select ETF", ARK_ETFS, index=0)

    prices = load_prices(etf)
    if prices is None or prices.empty:
        st.warning(f"No price data for {etf}.")
        return

    etf_trades = trades[trades["ETF"] == etf].sort_values("Date")

    fig = build_etf_chart(etf, prices, etf_trades)
    st.plotly_chart(fig, width="stretch")

    # Trade summary table for the selected ETF
    st.subheader(f"{etf} Trade History ({len(etf_trades)} trades)")
    display_df = etf_trades[["Date", "Direction", "Ticker", "Company Name", "Shares Traded", "% of Total ETF"]].copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    display_df["Shares Traded"] = display_df["Shares Traded"].apply(lambda x: f"{x:,.0f}")
    display_df["% of Total ETF"] = display_df["% of Total ETF"].apply(lambda x: f"{x:.4f}")
    st.dataframe(display_df, width="stretch", hide_index=True)


if __name__ == "__main__":
    main()
