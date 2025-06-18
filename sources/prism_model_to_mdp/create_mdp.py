from itertools import product
from prism_model_to_mdp.dot_visualization import add_choice, add_nature_loop
from prism_model_to_mdp.dot_visualization import places_label, add_impacts, \
	is_passing_time, add_empty_transition
from prism_model_to_mdp.etl import find_next_state, find_exclusive_gateways


def decisions_combinations(exclusive_gateways):
	all_combinations = list(product(*exclusive_gateways.values()))
	return [
		dict(zip(exclusive_gateways.keys(), combination))
		for combination in all_combinations
	]


def manage_xor_splits(idx, idx_next, probability, choices, natures, loops):
	lines = []

	if len(choices) > 0 and len(loops) == 0 and len(natures) == 0:
		for decision_combination in decisions_combinations(choices):
			_, choices_lines = add_choice(decision_combination, idx, idx_next)
			lines.extend(choices_lines)

	elif len(choices) == 0 and len(loops) > 0  or len(natures) > 0:
		loops.update(natures)
		for decision_combination in decisions_combinations(loops):
			_, loops_natures_lines = add_nature_loop(decision_combination, idx, idx_next, probability)
			lines.extend(loops_natures_lines)

	else:
		for decision_combination in decisions_combinations(choices):
			idx_choice, choices_lines = add_choice(decision_combination, idx, idx_next)
			choices_lines.pop(2) # Removing useless edge

			loops.update(natures)
			for decision_combinations_nat in decisions_combinations(loops):
				_, loops_natures_lines = add_nature_loop(decision_combinations_nat, idx_choice, idx_next, probability)

				if all(str(v).startswith("true") or str(v) == "exit" for v in decision_combinations_nat.values()):
					lines.extend(choices_lines)

				lines.extend(loops_natures_lines)

	return lines


'''
CASE 1: deterministic, 2 states directly connected

CASE 2: time passage 2 states connected with label="{{∅}}" fillcolor=lightsalmon

Case 3: choice: red transition with internal writing some choice I take (1+) and saying true/false --> written in the next state

case 4 natural: as choice but green transition and label on the probability arcs

Case 5: nature and contemporary choice: double transition first choice and then nature
'''

def create_states_mdp(states, trans_dict, rewards_dict, save =False):
	lines = ['digraph LTS {', 'node [label="", shape="box"];']

	for idx, places in states.items():
		lines.append(places_label(idx, places)) # add node states

		next_states = find_next_state(idx, trans_dict, states)

		if len(next_states) == 1: # case 1 or case 2
			idx_next, _, label = next_states[0]
			next_places = states[idx_next]
			if label:
				lines.extend(add_impacts(idx, label, rewards_dict))
			if is_passing_time(places, next_places):# Case 2
				lines.extend(add_empty_transition(idx, idx_next))
			else:# Case 1
				lines.append(f'"{idx}" -> "{idx_next}";')
		else:
			for t in next_states:
				idx_next, probability, label = t
				next_places = states[idx_next]
				choices, natures, loops = find_exclusive_gateways(places, next_places)

				if len(choices) > 0 or len(loops) > 0 or len(natures) > 0:
					lines.extend(manage_xor_splits(idx, idx_next, probability, choices, natures, loops))
				else:
					raise Exception("Unexpected case, its a bug")


	lines.append('}')
	return "\n".join(lines)