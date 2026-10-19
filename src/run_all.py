"""Single entry point: fetch (or reuse cached) data, run all experiments, write figures and tables.

    python code/src/run_all.py            # uses cached data in code/data/ when present
"""
import time

import analysis
import fetch_data
import figures
import tables

if __name__ == "__main__":
    t0 = time.time()
    fetch_data.main()
    analysis.main()
    tables.main()
    figures.main()
    print(f"run_all finished in {time.time() - t0:.0f} s")
