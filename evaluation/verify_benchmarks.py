import json

files = [
    'benchmark_results_current.json',
    'benchmark_results_full_now.json',
    'benchmark_results_high_precision_recall_strict_after_link_nolang_full.json',
    'benchmark_results_high_precision_recall_balanced_full.json'
]

for file_name in files:
    try:
        with open('evaluation/' + file_name, 'r', encoding='utf-8') as f:
            data = json.load(f)
            ag = data.get('aggregate')
            if ag:
                p = ag.get('precision', 0) * 100
                r = ag.get('recall', 0) * 100
                f1 = ag.get('f1_score', 0) * 100
                tp = ag.get('true_positives', 0)
                fp = ag.get('false_positives', 0)
                fn = ag.get('false_negatives', 0)
                print(f'{file_name}: P={p:.2f}% R={r:.2f}% F1={f1:.2f}% (TP={tp}, FP={fp}, FN={fn})')
            else:
                print(f'{file_name}: No aggregate data found.')
    except Exception as e:
        print(f'Failed to open {file_name}: {e}')
