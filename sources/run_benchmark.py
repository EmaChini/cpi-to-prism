from experiments.watchdog import run

if __name__ == '__main__':
	while True:
		#First argument is the current threshold (minutes) for the watchdog
		#Second is the check interval
		run(1, 20)