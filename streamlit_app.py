"""
streamlit_app.py
Interactive Research Dashboard for Adaptive Concurrency Control.

Visualizes:
  - Dataset overview and scenario distributions
  - Model evaluation comparisons (MAE, RMSE, R2)
  - Real-time simulation of controller decisions and switching behavior
  - Comparative benchmark metrics (Static vs Reactive vs Predictive)

Run with:
  streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import yaml
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(
    page_title="Adaptive Concurrency Control Research",
    page_icon="⚡",
    layout="wide"
)

PROJECT_ROOT = Path(__file__).resolve().parent

# Header
st.title("⚡ Predictive Adaptive Concurrency Control Research Dashboard")
st.markdown("""
**Project:** *Predictive Network- and Contention-Aware Concurrency Control Switching with Switching-Cost Optimization in Distributed Databases.*
""")

# Sidebar
st.sidebar.header("Navigation & Configuration")
tabs = st.sidebar.radio("Go to:", [
    "Overview & Scenarios",
    "Model Evaluation",
    "Controller Decision Simulation",
    "Benchmark Strategy Comparison",
    "Artifacts & Visualizations"
])

# 1. Overview & Scenarios
if tabs == "Overview & Scenarios":
    st.header("📊 Dataset Overview & Experimental Matrix")
    data_path = PROJECT_ROOT / "data" / "processed" / "processed_data.csv"
    if not data_path.exists():
        data_path = PROJECT_ROOT / "data" / "sample" / "synthetic_experiment_data.csv"

    if data_path.exists():
        df = pd.read_csv(data_path)
        st.write(f"**Loaded Observations:** {len(df):,} | **Columns:** {len(df.columns)}")
        st.dataframe(df.head(10))

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Workload & Protocol Distribution")
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.countplot(data=df, x="workload_type", hue="active_protocol", ax=ax, palette="Set2")
            st.pyplot(fig)
        with col2:
            st.subheader("Conflict Rate vs Network RTT")
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.scatter(df["conflict_rate"], df["network_rtt_ms"], alpha=0.3, c="#1f77b4")
            ax.set_xlabel("Conflict Rate")
            ax.set_ylabel("Network RTT (ms)")
            st.pyplot(fig)
    else:
        st.warning("Processed dataset not found. Run `python scripts/preprocess_data.py`.")

# 2. Model Evaluation
elif tabs == "Model Evaluation":
    st.header("📈 ML Model Evaluation on Test Split (Chronological Holdout)")
    comp_path = PROJECT_ROOT / "results" / "model_comparison.csv"
    if comp_path.exists():
        comp_df = pd.read_csv(comp_path)
        st.dataframe(comp_df.style.highlight_min(subset=["MAE", "RMSE"], color="#d4edda")
                                 .highlight_max(subset=["R2"], color="#d4edda"))
        
        st.subheader("Model Error Metrics Comparison")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Contention Prediction ($R^2$ Score)**")
            cont_df = comp_df[comp_df["target"] == "contention"]
            fig, ax = plt.subplots(figsize=(6, 3.5))
            sns.barplot(data=cont_df, x="model", y="R2", ax=ax, palette="Blues_d")
            ax.set_ylim(0.9, 1.0)
            st.pyplot(fig)
        with col2:
            st.markdown("**Network RTT Prediction ($R^2$ Score)**")
            net_df = comp_df[comp_df["target"] == "network"]
            fig, ax = plt.subplots(figsize=(6, 3.5))
            sns.barplot(data=net_df, x="model", y="R2", ax=ax, palette="Greens_d")
            ax.set_ylim(0.9, 1.0)
            st.pyplot(fig)
    else:
        st.warning("Model comparison file not found. Run `python -m src.models.evaluate`.")

# 3. Controller Decision Simulation
elif tabs == "Controller Decision Simulation":
    st.header("🧠 Interactive Protocol Recommendation Engine")
    st.markdown("Simulate how the **Predictive Controller** balances upcoming conditions and switching costs.")

    col1, col2, col3 = st.columns(3)
    with col1:
        current_proto = st.selectbox("Current Active Protocol", ["OCC", "2PL", "MVCC"], index=0)
    with col2:
        pred_contention = st.slider("Predicted Future Conflict Rate", 0.0, 1.0, 0.35, step=0.01)
    with col3:
        pred_rtt = st.slider("Predicted Future Network RTT (ms)", 0.5, 200.0, 15.0, step=0.5)

    from src.controller.decision_engine import PredictiveController
    ctrl = PredictiveController()
    decision = ctrl.decide(
        current_protocol=current_proto,
        predicted_contention=pred_contention,
        predicted_network_rtt=pred_rtt
    )

    st.subheader("Controller Action Result")
    res_col1, res_col2, res_col3 = st.columns(3)
    res_col1.metric("Action", decision.action.upper(), delta="Switching Cost: " + str(decision.switching_cost_ms) + " ms" if decision.action == "switch" else "Zero Cost")
    res_col2.metric("Recommended Protocol", decision.recommended_protocol)
    res_col3.metric("Decision Confidence", f"{decision.confidence * 100:.1f}%")
    st.info(f"**Rationale:** {decision.reason}")

# 4. Benchmark Strategy Comparison
elif tabs == "Benchmark Strategy Comparison":
    st.header("🏆 Strategy Comparison: Static vs. Reactive vs. Predictive")
    bench_path = PROJECT_ROOT / "results" / "benchmark_comparison.csv"
    if bench_path.exists():
        bench_df = pd.read_csv(bench_path)
        st.dataframe(bench_df)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Mean Latency (ms) [Lower is Better]")
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.barplot(data=bench_df, x="strategy", y="mean_latency", ax=ax, palette="coolwarm")
            plt.xticks(rotation=20)
            st.pyplot(fig)
        with col2:
            st.subheader("Protocol Switching Overhead (ms)")
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.barplot(data=bench_df, x="strategy", y="total_switch_overhead", ax=ax, palette="magma")
            plt.xticks(rotation=20)
            st.pyplot(fig)
    else:
        st.warning("Benchmark comparison file not found. Run `python -m src.experiments.run_experiments`.")

# 5. Artifacts & Visualizations
elif tabs == "Artifacts & Visualizations":
    st.header("🖼️ Generated Research Figures")
    fig_dir = PROJECT_ROOT / "results" / "figures"
    images = sorted(list(fig_dir.glob("*.png")))
    if images:
        selected_img = st.selectbox("Select figure to inspect:", [img.name for img in images])
        st.image(str(fig_dir / selected_img), caption=selected_img, use_container_width=True)
    else:
        st.info("No figures found in results/figures/. Run `python scripts/generate_eda_visualizations.py`.")

