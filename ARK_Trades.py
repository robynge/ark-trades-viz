"""ARK Trades Visualization — stock prices with buy/sell markers."""

import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TRADES_FILE = os.path.join(DATA_DIR, "ark_trades_summary.xlsx")
PRICES_DIR = os.path.join(DATA_DIR, "prices")

st.set_page_config(page_title="ARK Trades", page_icon="📈", layout="wide")


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
    # Flatten multi-level columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def build_chart(ticker: str, prices: pd.DataFrame, trades: pd.DataFrame):
    fig = go.Figure()

    # Price line
    fig.add_trace(
        go.Scatter(
            x=prices.index,
            y=prices["Close"],
            mode="lines",
            name="Close",
            line=dict(color="#636EFA", width=1.5),
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:.2f}<extra></extra>",
        )
    )

    # Buy/Sell markers — match trade dates to nearest price date
    for direction, color, symbol, label in [
        ("Buy", "#2CA02C", "triangle-up", "Buy"),
        ("Sell", "#D62728", "triangle-down", "Sell"),
    ]:
        mask = trades["Direction"] == direction
        dir_trades = trades[mask].copy()
        if dir_trades.empty:
            continue

        # For each trade date, find the closest price date
        marker_dates = []
        marker_prices = []
        hover_texts = []
        for _, row in dir_trades.iterrows():
            trade_date = row["Date"]
            # Find closest available price date
            idx = prices.index.searchsorted(trade_date)
            if idx >= len(prices):
                idx = len(prices) - 1
            price_date = prices.index[idx]
            marker_dates.append(price_date)
            marker_prices.append(prices.loc[price_date, "Close"])
            hover_texts.append(
                f"<b>{direction}</b><br>"
                f"Date: {trade_date.strftime('%Y-%m-%d')}<br>"
                f"ETF: {row['ETF']}<br>"
                f"Shares: {row['Shares Traded']:,.0f}<br>"
                f"% of ETF: {row['% of Total ETF']:.4f}"
            )

        fig.add_trace(
            go.Scatter(
                x=marker_dates,
                y=marker_prices,
                mode="markers",
                name=label,
                marker=dict(symbol=symbol, size=11, color=color, line=dict(width=1, color="white")),
                hovertemplate="%{text}<extra></extra>",
                text=hover_texts,
            )
        )

    fig.update_layout(
        title=f"{ticker} — Price & ARK Trades",
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=550,
    )
    return fig


def main():
    st.title("ARK Trades Visualization")

    trades = load_trades()

    # Build ticker → company name mapping
    ticker_company = (
        trades.drop_duplicates("Ticker")[["Ticker", "Company Name"]]
        .set_index("Ticker")["Company Name"]
        .to_dict()
    )

    # Only show tickers that have price data
    available = sorted(
        t for t in ticker_company if os.path.exists(os.path.join(PRICES_DIR, f"{t}.csv"))
    )

    if not available:
        st.error("No price data found. Run `python fetch_prices.py` first.")
        return

    # Sidebar — ticker selector
    st.sidebar.header("Select Stock")
    options = [f"{t} — {ticker_company[t]}" for t in available]
    selection = st.sidebar.selectbox("Ticker", options, index=0)
    ticker = selection.split(" — ")[0]

    # Load data
    prices = load_prices(ticker)
    if prices is None or prices.empty:
        st.warning(f"No price data for {ticker}.")
        return

    ticker_trades = trades[trades["Ticker"] == ticker].sort_values("Date")

    # Chart
    fig = build_chart(ticker, prices, ticker_trades)
    st.plotly_chart(fig, use_container_width=True)

    # Trade table
    st.subheader(f"Trade History ({len(ticker_trades)} trades)")
    display_df = ticker_trades[["Date", "ETF", "Direction", "Shares Traded", "% of Total ETF"]].copy()
    display_df["Date"] = display_df["Date"].dt.strftime("%Y-%m-%d")
    display_df["Shares Traded"] = display_df["Shares Traded"].apply(lambda x: f"{x:,.0f}")
    display_df["% of Total ETF"] = display_df["% of Total ETF"].apply(lambda x: f"{x:.4f}")
    st.dataframe(display_df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
