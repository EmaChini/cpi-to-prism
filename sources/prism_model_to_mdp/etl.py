from collections import defaultdict
import pandas as pd
import re
from itertools import product

def load_prism_model(process_name: str):
	states_filenames = f"models/{process_name}_states.csv"
	transitions_filenames = f"models/{process_name}_trans.tra"
	reward_filename = f"models/{process_name}.nm"

	states = pd.read_csv(states_filenames)
	transitions = pd.read_csv(transitions_filenames, skiprows=1, header= None)
	with open(reward_filename, 'r') as file:
		rewards = file.readlines()


	states = parse_states(states)
	transitions = parse_transition(transitions)
	rewards = parse_rewards(rewards)

	'''
	dot_filename = f"models/{process_name}.dot"
	with open(dot_filename, 'r', encoding='utf-8') as f: #{process_name}/{process_name}.dot
		dot_content = f.read()
		dot = Source(dot_content).render(filename=f"models/{process_name}", format='svg', cleanup=True)
	'''
	return states, transitions, rewards#,dot

def parse_rewards(lines):
	rewards_dict = defaultdict(dict)
	current_impact = None

	for line in lines:
		line = line.strip()

		if line.startswith('rewards'):
			match = re.search(r'rewards\s+"([^"]+)"', line)
			if match:
				current_impact = match.group(1)

		elif line == 'endrewards':
			current_impact = None

		elif current_impact:
			match = re.match(r'\[([^\]]+)\]\s+true\s*:\s*([0-9.eE+-]+);', line)

			if match:
				task_name = match.group(1)
				value = float(match.group(2))
				rewards_dict[task_name][current_impact] = value

	return dict(rewards_dict)

def parse_transition(transitions:pd.DataFrame):
	trans = transitions[0].str.split(expand=True)

	has_prob = trans.shape[1] >= 5

	# Extract relevant columns
	if has_prob:
		source_dest = trans[[0, 2, 3, 4]]
		source_dest.columns = ['source', 'destination', 'prob', 'label']
	else:
		source_dest = trans[[0, 2, 3]]
		source_dest.columns = ['source', 'destination', 'label']

	trans_dict = defaultdict(list)
	for _, row in source_dest.iterrows():
		source = int(row['source'])
		destination = int(row['destination'])
		prob = float(row['prob']) if has_prob else 1.0  # Default prob to 1.0 if missing
		label = [row['label'] ]if row['label'] else []
		trans_dict[source].append((destination, prob,label))

	return dict(trans_dict)

def parse_states(states: pd.DataFrame): # Filter useless states
	states['STAGE'] = states['(STAGE'].apply(
		lambda x: x.split(':')[-1].split('(')[-1] if isinstance(x, str) else x
	)
	states.drop(columns=['(STAGE'], inplace=True)

	paren_cols = [col for col in states.columns if col.endswith(')')]

	for col in paren_cols:
		states[col.replace(')', '')] = states[col].apply(
			lambda x: x[-2] if isinstance(x, str) and len(x) >= 2 else x
		)
		states.drop(columns=[col], inplace=True)

	states = states.apply(pd.to_numeric)

	update_cols = [col for col in states.columns if col.endswith('_update')]
	state_cols = [col for col in states.columns if col.endswith('_state')]
	value_cols = [col for col in states.columns if col.endswith('_value')]

	stage_mask = states['STAGE'].isin([0])
	update_mask = (states[update_cols] == 0).all(axis=1)
	state_mask = (states[state_cols] == 0).all(axis=1)
	new_states_df = states[stage_mask & update_mask & state_mask]

	states = {}
	for idx, row in dict(new_states_df.iterrows()).items():
		places = {}
		for col in value_cols:
			if row[col] >= 0:
				places[col.replace('_value', '')] = int(row[col])

		states[idx] = places

	return states

def find_next_state(src:int, transition:dict, states: set):
	res = []
	for i in range(len(transition[src])):
		if src == transition[src][i][0]:
			return [] # it's final
		if transition[src][i][0] in states.keys():
			res.append(transition[src][i]) # questo significa che src e target sono collegati direttamente

	if len(res) > 0:
		return res

	for i in range(len(transition[src])):
		# continua a cercare ma la destinazione è diventata source
		l = transition[src][i][2]
		for r in find_next_state(transition[src][i][0], transition, states):
			l.extend(r[2])
			res.append((r[0], round(r[1] * transition[src][i][1], 3), l))
	return res

def find_exclusive_gateways(places:dict, next_places:dict):
	choices = defaultdict(list)
	natures = defaultdict(list)
	loops = defaultdict(list)
	for k in next_places.keys():
		if '_' not in k:
			continue
		type_split, t_f = k.split('_', 1)
		if "choice" in type_split:
			choices[type_split].append(t_f)
		elif "nature" in type_split:
			natures[type_split].append(t_f)
		elif "loop" in type_split:
			loops[type_split].append("repeat")

	for k in places.keys():#TODO
		if '_' not in k:
			continue
		type_split, t_f = k.split('_', 1)
		if "loop" in type_split and "decision" in t_f and type_split not in loops:
			loops[type_split].append("exit")


	return dict(choices), dict(natures), dict(loops)

def decisions_combinations(exclusive_gateways):
	all_combinations = list(product(*exclusive_gateways.values()))
	return [
		dict(zip(exclusive_gateways.keys(), combination))
		for combination in all_combinations
	]
