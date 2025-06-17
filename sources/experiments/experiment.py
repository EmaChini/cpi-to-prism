import datetime
import json

from sources.refinements import refine_bounds
from experiments.telegram.telegram_bot import send_telegram_message


def single_execution(cursor, conn, x, y, w, bundle):
    # Check if the experiment already exists
    cursor.execute(
        "SELECT COUNT(*) FROM experiments WHERE x=? AND y=? AND w=?",
        (x, y, w)
    )
    if cursor.fetchone()[0] > 0:
        print(f"Experiment x={x}, y={y}, w={w} already exists, trying another...")
        return

    # Get dictionary and metadata
    D = bundle[w].copy()
    T = D.pop('metadata')

    # Write to current_benchmark.cpi
    with open('CPIs/current_benchmark.cpi', 'w') as f:
        json.dump(D, f)

    # Record start time
    vts = datetime.datetime.now().isoformat()

    # Insert initial record
    cursor.execute(
        """
		INSERT INTO experiments (
			x, y, w, z, num_impacts, choice_distribution, 
			generation_mode, duration_interval_min, duration_interval_max,
			vts
		) 
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		""",
        (
            x, y, w,
            T['z'],
            T['num_impacts'],
            T['choice_distribution'],
            T['generation_mode'],
            T['duration_interval'][0],
            T['duration_interval'][1],
            vts
        )
    )
    conn.commit()

    error = ""
    initial_bounds = {}
    final_bounds = {}
    # Run refinement analysis
    print(f"\nRunning benchmark for x={x}, y={y}, w={w}")

    try:
        initial_bounds, final_bounds, error = refine_bounds('current_benchmark', 10, verbose=True)
    except Exception as e:
        s = f"Error during benchmark x={x}, y={y}, w={w}: {str(e)}"
        send_telegram_message(s)
        error = s

    # Record end time
    vte = datetime.datetime.now().isoformat()

    # Update record with end time
    cursor.execute(
        """
		UPDATE experiments 
		SET vte = ?, initial_bounds = ?, final_bounds = ?, error = ?
		WHERE x = ? AND y = ? AND w = ?
		""",
        (vte, str(initial_bounds), str(final_bounds), error,
         x, y, w)
    )
    conn.commit()

    print(f"\nCompleted benchmark x={x}, y={y}, w={w}")
    print(f"Metadata: {T}")
    print(f"Start time: {vts}")
    print(f"End time: {vte}")
