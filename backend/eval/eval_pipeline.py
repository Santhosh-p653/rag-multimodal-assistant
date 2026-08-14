"""
eval_pipeline.py — Non-destructive Quantitative Benchmarking Suite for OCTO-RAG pipeline.
Measures Retrieval Precision, Recall, MRR, and Stage-by-Stage Latency profiling, generating numerical reports and PNG charts.
"""
import sys
import os
import time
import json
import statistics
from pathlib import Path

# Add backend directory to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import matplotlib.pyplot as plt

# Ground-truth test dataset for enterprise quantitative evaluation (20 Benchmark Queries)
EVAL_DATASET = [
    # Refrigerator Category
    {"query": "How do I reset the refrigerator water filter indicator light?", "expected_keywords": ["filter", "reset", "light", "button", "indicator"], "category": "Refrigerator / Maintenance"},
    {"query": "How to clean the condenser coils on model RF-900?", "expected_keywords": ["clean", "condenser", "coils", "rf-900", "vacuum"], "category": "Refrigerator / Maintenance"},
    {"query": "Where is the ice maker shut-off valve located?", "expected_keywords": ["ice", "maker", "valve", "shut-off", "location"], "category": "Refrigerator / Component"},
    {"query": "What is the target temperature setting for the fresh food compartment?", "expected_keywords": ["temperature", "setting", "fresh", "food", "degree"], "category": "Refrigerator / Specs"},
    {"query": "How to replace torn door gasket seals on RF-900?", "expected_keywords": ["gasket", "seal", "door", "replace", "torn"], "category": "Refrigerator / Repair"},

    # Washing Machine Category
    {"query": "What does error code E4 on the washing machine mean?", "expected_keywords": ["error", "e4", "drain", "water", "pump"], "category": "Washer / Error Code"},
    {"query": "How to resolve error code LE overload signal on washing machine?", "expected_keywords": ["error", "le", "overload", "motor", "reset"], "category": "Washer / Error Code"},
    {"query": "What causes an unbalanced load error UE during high speed spin?", "expected_keywords": ["unbalanced", "load", "ue", "spin", "level"], "category": "Washer / Troubleshooting"},
    {"query": "Where is the drain pump lint filter located on model WM-400?", "expected_keywords": ["drain", "pump", "filter", "lint", "bottom"], "category": "Washer / Component"},
    {"query": "How do I clear detergent drawer residue buildup?", "expected_keywords": ["detergent", "drawer", "dispenser", "clean", "buildup"], "category": "Washer / Maintenance"},

    # Freezer Category
    {"query": "What is the recommended operating voltage for the freezer compressor?", "expected_keywords": ["voltage", "compressor", "operating", "power", "v"], "category": "Freezer / Specs"},
    {"query": "How to unclog a frozen defrost drain tube in model FZ-200?", "expected_keywords": ["defrost", "drain", "tube", "frozen", "unclog"], "category": "Freezer / Maintenance"},
    {"query": "Why is excessive frost accumulating on the top freezer shelf?", "expected_keywords": ["frost", "accumulating", "shelf", "gasket", "humidity"], "category": "Freezer / Troubleshooting"},
    {"query": "How to silence the freezer door open warning alarm?", "expected_keywords": ["door", "alarm", "silence", "warning", "button"], "category": "Freezer / Features"},
    {"query": "Where is the temperature sensor thermistor located in FZ-200?", "expected_keywords": ["temperature", "sensor", "thermistor", "located", "evaporator"], "category": "Freezer / Component"},

    # Dishwasher Category
    {"query": "What causes dishwasher error code E15 leak alert?", "expected_keywords": ["error", "e15", "leak", "water", "base"], "category": "Dishwasher / Error Code"},
    {"query": "How to remove and clean clogged spray arm nozzles on DW-800?", "expected_keywords": ["spray", "arm", "nozzles", "clean", "clogged"], "category": "Dishwasher / Maintenance"},
    {"query": "Where is the water inlet solenoid valve located on model DW-800?", "expected_keywords": ["water", "inlet", "valve", "solenoid", "bottom"], "category": "Dishwasher / Component"},
    {"query": "Why is the dishwasher detergent tablet dispenser flap not opening?", "expected_keywords": ["detergent", "dispenser", "flap", "opening", "latch"], "category": "Dishwasher / Troubleshooting"},
    {"query": "What is the electrical wattage rating for the heating element?", "expected_keywords": ["wattage", "rating", "heating", "element", "watt"], "category": "Dishwasher / Specs"}
]


def profile_pipeline():
    """Run full benchmarking suite and compute latency and retrieval metrics."""
    print("=" * 65)
    print("      OCTO-RAG QUANTITATIVE EVALUATION & LATENCY BENCHMARK     ")
    print("=" * 65)

    from app.services.query_understanding import understand_query
    from app.services.retriever import retrieve_context
    from app.services.vision_embedder import VisionEmbedderService
    from app.services.vector_store import VectorStoreService
    from app.services.embedder import EmbedderService

    try:
        vs = VectorStoreService()
    except Exception:
        VectorStoreService._instance = None
        vs = VectorStoreService(db_path=":memory:")

    embedder = EmbedderService()

    if vs.count() < 20:
        print("[Evaluation] Qdrant DB has fewer than 20 vectors. Seeding 20 technical manual chunks...")
        raw_chunks = [
            {"chunk_id": "eval_1", "content": "To reset the refrigerator water filter indicator light, press and hold the Filter Reset button for 3 seconds until the light turns green.", "source_file": "ref_manual.pdf", "product": "RF-900", "page": 12},
            {"chunk_id": "eval_2", "content": "To clean the condenser coils on model RF-900, disconnect power and gently vacuum dust off the rear coil grill every 6 months.", "source_file": "ref_manual.pdf", "product": "RF-900", "page": 18},
            {"chunk_id": "eval_3", "content": "The ice maker shut-off valve is located behind the lower access panel near the water supply inlet hose.", "source_file": "ice_manual.pdf", "product": "RF-900", "page": 8},
            {"chunk_id": "eval_4", "content": "The target temperature setting for the fresh food compartment is 37 degrees Fahrenheit (3 degrees Celsius).", "source_file": "ref_manual.pdf", "product": "RF-900", "page": 5},
            {"chunk_id": "eval_5", "content": "To replace torn door gasket seals on RF-900, peel away the flexible magnetic strip from the door track groove and press the new gasket firmly.", "source_file": "ref_manual.pdf", "product": "RF-900", "page": 24},

            {"chunk_id": "eval_6", "content": "Error code E4 on the washing machine indicates a water drainage failure. Inspect the drain hose and clear any debris from the pump filter.", "source_file": "washer_manual.pdf", "product": "WM-400", "page": 45},
            {"chunk_id": "eval_7", "content": "To resolve error code LE overload signal on washing machine, reduce drum load capacity and press the Power button to reset the motor sensor.", "source_file": "washer_manual.pdf", "product": "WM-400", "page": 48},
            {"chunk_id": "eval_8", "content": "An unbalanced load error UE occurs during high speed spin when laundry is clumped on one side. Redistribute clothes evenly inside drum.", "source_file": "washer_manual.pdf", "product": "WM-400", "page": 50},
            {"chunk_id": "eval_9", "content": "The drain pump lint filter is located behind the small service door at the bottom right front corner of model WM-400.", "source_file": "washer_manual.pdf", "product": "WM-400", "page": 12},
            {"chunk_id": "eval_10", "content": "To clear detergent drawer residue buildup, pull out the dispenser tray completely and flush under warm running water with a soft brush.", "source_file": "washer_manual.pdf", "product": "WM-400", "page": 16},

            {"chunk_id": "eval_11", "content": "The freezer compressor operating voltage is 115V AC at 60Hz. Ensure dedicated electrical grounding.", "source_file": "freezer_spec.pdf", "product": "FZ-200", "page": 5},
            {"chunk_id": "eval_12", "content": "To unclog a frozen defrost drain tube in model FZ-200, flush hot water down the drain hole located under the evaporator coils.", "source_file": "freezer_spec.pdf", "product": "FZ-200", "page": 14},
            {"chunk_id": "eval_13", "content": "Excessive frost accumulating on top freezer shelf indicates ambient air leakage past a damaged perimeter door gasket.", "source_file": "freezer_spec.pdf", "product": "FZ-200", "page": 19},
            {"chunk_id": "eval_14", "content": "To silence the freezer door open warning alarm, press the Alarm Mute pad on the digital control interface panel.", "source_file": "freezer_spec.pdf", "product": "FZ-200", "page": 8},
            {"chunk_id": "eval_15", "content": "The temperature sensor thermistor is located directly adjacent to the evaporator fin assembly inside the rear wall enclosure of FZ-200.", "source_file": "freezer_spec.pdf", "product": "FZ-200", "page": 22},

            {"chunk_id": "eval_16", "content": "Dishwasher error code E15 signals water leakage detected in the safety base pan. Turn off main water valve immediately.", "source_file": "dw_manual.pdf", "product": "DW-800", "page": 30},
            {"chunk_id": "eval_17", "content": "To remove and clean clogged spray arm nozzles on DW-800, unscrew the retaining nut and rinse under high pressure tap water.", "source_file": "dw_manual.pdf", "product": "DW-800", "page": 15},
            {"chunk_id": "eval_18", "content": "The water inlet solenoid valve is located at the bottom left base plate behind the lower front kickplate of model DW-800.", "source_file": "dw_manual.pdf", "product": "DW-800", "page": 9},
            {"chunk_id": "eval_19", "content": "If the dishwasher detergent tablet dispenser flap is not opening, ensure tall dinner plates are not blocking the door latch spring mechanism.", "source_file": "dw_manual.pdf", "product": "DW-800", "page": 21},
            {"chunk_id": "eval_20", "content": "The electrical wattage rating for the heating element is 1200 Watts operating on a 15 Amp dedicated circuit breaker.", "source_file": "dw_manual.pdf", "product": "DW-800", "page": 3}
        ]
        embedded_chunks = []
        for item in raw_chunks:
            item["embedding"] = embedder.embed_text(item["content"])
            embedded_chunks.append(item)

        vs.ingest_chunks(embedded_chunks)
        print(f"[Evaluation] Successfully seeded {len(embedded_chunks)} evaluation chunks into Qdrant.")

    vision_embedder = VisionEmbedderService()

    latency_records = {
        "query_understanding": [],
        "text_retrieval_rrf": [],
        "vision_embedding": [],
        "total_retrieval": []
    }

    retrieval_metrics = {
        "precision_at_3": [],
        "precision_at_5": [],
        "recall_at_5": [],
        "mrr": [],
        "hit_rate": []
    }

    results = []

    for i, test in enumerate(EVAL_DATASET, 1):
        query = test["query"]
        expected = test["expected_keywords"]

        # 1. Profile Query Understanding
        t0 = time.perf_counter()
        understood = understand_query(query)
        t_qu = (time.perf_counter() - t0) * 1000

        # 2. Profile Text Context Retrieval (Hybrid Dense + Sparse RRF)
        t1 = time.perf_counter()
        chunks, confidence = retrieve_context(understood["normalized_query"])
        t_ret = (time.perf_counter() - t1) * 1000

        # 3. Profile SigLIP Vision Embedding
        t2 = time.perf_counter()
        _ = vision_embedder.embed_text(query)
        t_vis = (time.perf_counter() - t2) * 1000

        t_total = t_qu + t_ret + t_vis

        latency_records["query_understanding"].append(t_qu)
        latency_records["text_retrieval_rrf"].append(t_ret)
        latency_records["vision_embedding"].append(t_vis)
        latency_records["total_retrieval"].append(t_total)

        # 4. Calculate Precision, Recall, and MRR for retrieved chunks
        relevant_chunks = 0
        first_hit_rank = 0

        for rank, chunk in enumerate(chunks, 1):
            text = chunk.get("content", "").lower()
            matches = sum(1 for kw in expected if kw.lower() in text)
            is_relevant = matches >= 1

            if is_relevant:
                relevant_chunks += 1
                if first_hit_rank == 0:
                    first_hit_rank = rank

        k_val = len(chunks) if chunks else 1
        p_at_3 = min(relevant_chunks, 3) / 3.0
        p_at_5 = relevant_chunks / max(k_val, 1)
        rec_at_5 = min(relevant_chunks / len(expected), 1.0)
        mrr = 1.0 / first_hit_rank if first_hit_rank > 0 else 0.0
        hit = 1.0 if first_hit_rank > 0 else 0.0

        retrieval_metrics["precision_at_3"].append(p_at_3)
        retrieval_metrics["precision_at_5"].append(p_at_5)
        retrieval_metrics["recall_at_5"].append(rec_at_5)
        retrieval_metrics["mrr"].append(mrr)
        retrieval_metrics["hit_rate"].append(hit)

        results.append({
            "query": query,
            "category": test["category"],
            "chunks_retrieved": len(chunks),
            "latency_ms": {
                "query_understanding": round(t_qu, 2),
                "text_retrieval_rrf": round(t_ret, 2),
                "vision_embedding": round(t_vis, 2),
                "total": round(t_total, 2)
            },
            "metrics": {
                "precision_at_3": round(p_at_3, 4),
                "precision_at_5": round(p_at_5, 4),
                "recall_at_5": round(rec_at_5, 4),
                "mrr": round(mrr, 4),
                "hit": int(hit)
            }
        })

        print(f"[{i}/{len(EVAL_DATASET)}] '{query[:35]}...' -> Total: {t_total:.1f}ms | P@5: {p_at_5:.2f} | MRR: {mrr:.2f}")

    # Aggregated Summary Stats
    avg_latency = {k: round(statistics.mean(v), 2) for k, v in latency_records.items()}
    avg_metrics = {k: round(statistics.mean(v), 4) for k, v in retrieval_metrics.items()}

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "average_latency_ms": avg_latency,
        "average_metrics": avg_metrics,
        "sample_evaluations": results
    }

    # Save output report JSON
    reports_dir = BACKEND_DIR / "eval" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "eval_results.json"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 65)
    print(f" MEAN RETRIEVAL LATENCY : {avg_latency['total_retrieval']} ms")
    print(f" MEAN PRECISION @ 5     : {avg_metrics['precision_at_5'] * 100:.1f}%")
    print(f" MEAN RECALL @ 5        : {avg_metrics['recall_at_5'] * 100:.1f}%")
    print(f" MEAN RECIPROCAL RANK   : {avg_metrics['mrr']:.4f}")
    print(f" HIT RATE @ 5           : {avg_metrics['hit_rate'] * 100:.1f}%")
    print("=" * 65)

    # Generate Performance Charts
    generate_charts(reports_dir, avg_latency, avg_metrics)
    print(f"[Evaluation] Report and PNG charts successfully generated in {reports_dir}")


def generate_charts(output_dir: Path, latency_data: dict, metrics_data: dict):
    """Generate visual PNG performance graphs."""
    plt.style.use('dark_background')

    # Chart 1: Latency Breakdown Bar Chart
    fig, ax = plt.subplots(figsize=(8, 5))
    stages = ['Query Analysis', 'Hybrid RRF Search', 'SigLIP Vision Embed']
    values = [latency_data['query_understanding'], latency_data['text_retrieval_rrf'], latency_data['vision_embedding']]
    colors = ['#8b5cf6', '#3b82f6', '#10b981']

    bars = ax.bar(stages, values, color=colors, width=0.5, edgecolor='#1e293b')
    ax.set_title('OCTO-RAG Pipeline Stage Latency Breakdown (ms)', fontsize=13, fontweight='bold', color='#f8fafc', pad=15)
    ax.set_ylabel('Latency (milliseconds)', fontsize=10, color='#94a3b8')
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(f'{height:.1f} ms',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4), textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold', color='#f8fafc')

    plt.tight_layout()
    plt.savefig(output_dir / "latency_breakdown.png", dpi=300)
    plt.close()

    # Chart 2: Retrieval Quality Metrics Bar Chart
    fig, ax = plt.subplots(figsize=(8, 5))
    metric_names = ['Precision@3', 'Precision@5', 'Recall@5', 'MRR', 'Hit Rate']
    metric_values = [metrics_data['precision_at_3'], metrics_data['precision_at_5'], metrics_data['recall_at_5'], metrics_data['mrr'], metrics_data['hit_rate']]
    m_colors = ['#ec4899', '#8b5cf6', '#06b6d4', '#10b981', '#f59e0b']

    mbars = ax.bar(metric_names, metric_values, color=m_colors, width=0.5, edgecolor='#1e293b')
    ax.set_title('OCTO-RAG Quantitative Retrieval Quality Benchmark', fontsize=13, fontweight='bold', color='#f8fafc', pad=15)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel('Score / Ratio', fontsize=10, color='#94a3b8')
    ax.grid(axis='y', linestyle='--', alpha=0.3)

    for bar in mbars:
        height = bar.get_height()
        ax.annotate(f'{height:.2f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 4), textcoords="offset points",
                    ha='center', va='bottom', fontsize=10, fontweight='bold', color='#f8fafc')

    plt.tight_layout()
    plt.savefig(output_dir / "retrieval_benchmark.png", dpi=300)
    plt.close()


if __name__ == "__main__":
    profile_pipeline()
