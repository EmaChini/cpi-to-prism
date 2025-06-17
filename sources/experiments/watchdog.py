import os
import shutil
import signal
import sys
import threading
import time
import subprocess
import sqlite3
from datetime import datetime
from experiments.benchmark import BENCHMARKS_DB, LOG_FILENAME
from experiments.telegram.telegram_bot import send_telegram_message, TELEGRAM_BOT_TOKEN, listen_for_messages


def clean_stuck_rows(current_threshold):
	conn = sqlite3.connect(BENCHMARKS_DB)
	cursor = conn.cursor()
	cursor.execute("DELETE FROM experiments WHERE vte IS NULL")
	print(f"Removed {cursor.rowcount} stuck rows with NULL vte from the database.")
	conn.commit()
	conn.close()

	shutil.copy(BENCHMARKS_DB, f"{current_threshold}_{BENCHMARKS_DB}")


process = None

def watchdog_handle_termination(signum, frame):
	process.terminate()
	s = "Experiment terminated"
	print(str(datetime.now()) + " " + s)
	send_telegram_message(s)
	sys.exit(0)


def execute_benchmark():
	with open(LOG_FILENAME, 'a') as log_file:
		benchmark_path = os.path.join(
			os.path.dirname(os.path.abspath(__file__)),
			"benchmark.py")

		if not os.path.exists(benchmark_path):
			raise FileNotFoundError(f"benchmark.py not found at {benchmark_path}")

		return subprocess.Popen([os.sys.executable, benchmark_path], stdout=log_file, stderr=log_file, cwd=os.getcwd())




def run(current_threshold, check_interval):
	global process

	signal.signal(signal.SIGTERM, watchdog_handle_termination)
	signal.signal(signal.SIGINT, watchdog_handle_termination)

	#Telegram Bot
	if TELEGRAM_BOT_TOKEN != '':
		threading.Thread(target=listen_for_messages, daemon=True).start()

	try:

		while True:
			process = execute_benchmark()

			while True:
				time.sleep(check_interval)

				if process.poll() is not None:
					#s = f"Benchmark with {current_threshold} minutes threshold done"
					#print(str(datetime.now()) + " " + s)
					#send_telegram_message(s)
					clean_stuck_rows(current_threshold)
					current_threshold *= 2
					break

				if os.path.getmtime(BENCHMARKS_DB) < time.time() - 60 * current_threshold:
					s = f"A experiment was stuck for {current_threshold} min and I killed it"
					print(str(datetime.now()) + " " + s)
					send_telegram_message(s)

					process.terminate()
					process.wait()
					time.sleep(1)
					break

				if current_threshold > 60 * 5:
					s = "Watchdog reached the maximum threshold of 5 hours"
					print(str(datetime.now()) + " " + s)
					send_telegram_message(s)
					sys.exit(0)


	except Exception as e:
		process.terminate()
		process.wait()
		s = "Watchdog terminated by exception: " + str(e)
		print(str(datetime.now()) + " " + s)
		send_telegram_message(s)