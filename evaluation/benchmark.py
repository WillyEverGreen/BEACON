import sys, os, time
sys.path.insert(0, os.path.abspath('rag-pipeline'))
from query import hybrid_retrieve, rerank

queries = [
    'img element missing alt attribute',
    'keyboard focus trap modal dialog',
    'color contrast ratio 4.5 minimum',
    'form label for id association',
    'skip navigation link bypass blocks',
]

print('='*60)
print('  LATENCY BENCHMARK (5 queries, warm cache)')
print('='*60)

# Warm-up (first call builds BM25 cache)
t0 = time.time()
print('  Initializing BM25 cache (cold start)...')
_ = hybrid_retrieve('warmup')
warmup = time.time() - t0
print(f'  Done in {warmup:.2f}s')
print()

times = []
for q in queries:
    t0 = time.time()
    candidates = hybrid_retrieve(q)
    top3 = rerank(q, candidates)
    elapsed = time.time() - t0
    times.append(elapsed)
    print(f'  {elapsed:.3f}s | {q[:45]}')

avg = sum(times) / len(times)
print()
print(f'  Average: {avg:.3f}s per query')
print(f'  Target:  < 2.000s')
print(f'  Status:  {"✅ TARGET MET" if avg < 2.0 else "❌ NEEDS WORK"} ')
print('='*60)
