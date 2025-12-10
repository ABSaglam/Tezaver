"""
Kartal Göz - 4h Rally Verification Script

BTC 4h Rally'lerini görselleştirerek kontrol eder.
User'la beraber eksik rally'leri tespit etmek için kullanılır.
"""

import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys

# Bootstrap
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from tezaver.core import coin_cell_paths

def load_price_data_4h(symbol: str, lookback_days: int = 730) -> pd.DataFrame:
    """Load 4h OHLCV data for the symbol."""
    # Use features_4h.parquet if available
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    features_path = data_dir / "features_4h.parquet"
    
    if not features_path.exists():
        raise FileNotFoundError(f"4h features not found for {symbol}")
    
    df = pd.read_parquet(features_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Filter to lookback period
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days)
    df = df[df['timestamp'] >= cutoff].copy()
    
    return df

def visualize_4h_rallies(symbol: str = "BTCUSDT"):
    """
    Create Plotly chart showing all 4h rallies as yellow boxes.
    """
    # Load price data
    df_price = load_price_data_4h(symbol, lookback_days=730)
    
    # Load 4h rallies
    rallies_path = coin_cell_paths.get_time_labs_rallies_path(symbol, "4h")
    df_rallies = pd.read_parquet(rallies_path)
    df_rallies['event_time'] = pd.to_datetime(df_rallies['event_time'])
    
    # Create figure
    fig = go.Figure()
    
    # Add candlestick
    fig.add_trace(go.Candlestick(
        x=df_price['timestamp'],
        open=df_price['open'],
        high=df_price['high'],
        low=df_price['low'],
        close=df_price['close'],
        name="BTC 4h"
    ))
    
    # Add rally boxes (yellow)
    for idx, rally in df_rallies.iterrows():
        start_time = rally['event_time']
        peak_time = start_time + pd.Timedelta(hours=4 * rally['bars_to_peak'])
        gain_pct = rally['future_max_gain_pct'] * 100
        
        fig.add_vrect(
            x0=start_time,
            x1=peak_time,
            fillcolor="yellow",
            opacity=0.2,
            layer="below",
            annotation_text=f"+{gain_pct:.1f}%",
            annotation_position="top left"
        )
    
    # Layout
    fig.update_layout(
        title=f"{symbol} - 4h Rallies (Son 2 Yıl)",
        xaxis_title="Zaman",
        yaxis_title="Fiyat (USD)",
        height=800,
        xaxis_rangeslider_visible=True,
        template="plotly_dark"
    )
    
    # Save to HTML

    output_path = Path("library") / "kartal_goz_4h_verify.html"
    fig.write_html(str(output_path))
    print(f"✅ Grafik kaydedildi: {output_path}")
    print(f"Tarayıcınızda açmak için: open {output_path}")
    
    # Stats
    print(f"\n📊 İstatistikler:")
    print(f"Toplam 4h Rally: {len(df_rallies)}")
    print(f"Ortalama Kazanç: %{df_rallies['future_max_gain_pct'].mean() * 100:.1f}")
    print(f"Dönem: {df_rallies['event_time'].min().date()} → {df_rallies['event_time'].max().date()}")

if __name__ == "__main__":
    visualize_4h_rallies("BTCUSDT")
