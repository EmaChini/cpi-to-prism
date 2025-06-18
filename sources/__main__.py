import json
import os
import re
import subprocess

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
import uvicorn
from cpi_to_spin.cpitospin import CPIToSPINConverter, create_cpi_visualization, create_spin_visualization
from env import PRISM_PATH
from prism import get_task_impacts
from prism_model_to_mdp.create_mdp import create_states_mdp
from prism_model_to_mdp.etl import load_prism_model


def run(port: int = 8001):
	app = FastAPI()
	app.add_middleware(
		CORSMiddleware,
		allow_origins=["*"],
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"]
	)

	@app.get("/")
	async def get():
		"""
		Root endpoint that returns a welcome message
		Returns:
			str: Welcome message
		"""
		return f"welcome to CPI-to_PRISM server"


	@app.get("/create_spin")
	async def check_bpmn(request: dict) -> dict:
		cpi_dict = request.get("cpi_dict")
		if cpi_dict is None:
			raise HTTPException(status_code=400, detail="No cpi dict found")

		try:
			cpi_dot = create_cpi_visualization(cpi_dict)
			converter = CPIToSPINConverter()
			spin_model = converter.convert_cpi_to_spin(cpi_dict)
			spin_dot = create_spin_visualization(spin_model)

			prism_model = spin_model.generate_prism_model()

		except Exception as e:
			raise HTTPException(status_code=400, detail=str(e))

		try:
			return { "cpi_dot": str(cpi_dot),
					 "spin_dot": str(spin_dot),
					 "prism_model": prism_model
					 }
		except Exception as e:
			raise HTTPException(status_code=500, detail=str(e))



	@app.get("/run_prism_analysis")
	async def run_prism_analysis(request: dict) -> dict:
		cpi_dict = request.get("cpi_dict")
		if cpi_dict is None:
			raise HTTPException(
				status_code=400, detail="No cpi dict found")

		import uuid
		process_name = f"tmp_{uuid.uuid4()}"

		os.makedirs("models", exist_ok=True)
		os.makedirs("CPIs", exist_ok=True)

		model_path = os.path.join("models", f"{process_name}.nm")
		states_path = os.path.join("models", f"{process_name}_states.csv")
		trans_path = os.path.join("models", f"{process_name}_trans.tra")
		cpi_path = os.path.join("CPIs", f"{process_name}.cpi")

		try:
			with open(cpi_path, 'w') as f:
				json.dump(cpi_dict, f)

			converter = CPIToSPINConverter()
			spin_model = converter.convert_cpi_to_spin(cpi_dict)
			prism_model = spin_model.generate_prism_model()

			with open(model_path, 'w') as f:
				f.write(prism_model)
		except Exception as e:
			raise HTTPException(status_code=500, detail=str(e))

		# Run PRISM command
		cmd = [os.path.abspath(PRISM_PATH) if PRISM_PATH else "prism",
			   os.path.abspath(model_path),
			   "-exporttransdotstates", os.path.abspath(f"{process_name}.dot")]

		cmd += ["-exportstates", os.path.abspath(states_path),
				"-exporttrans", os.path.abspath(trans_path)]

		cmd.append("-verbose")

		try:
			result = subprocess.run(cmd,
									capture_output=True,
									text=True,
									check=True)

			output = result.stdout

			# Extract information using regex
			modules_match = re.search(r'Modules:\s+(.+?)\n', output)
			variables_match = re.search(r'Variables:\s+(.+?)\n', output)

			states, transitions, rewards = load_prism_model(process_name)

			mdp_dot = create_states_mdp(states, transitions, rewards)

			# Compile information
			return {
				'modules': modules_match.group(1).split() if modules_match else [],
				'variables': variables_match.group(1).split() if variables_match else [],
				'task_impacts': get_task_impacts(cpi_dict),
				'command': ' '.join(cmd),
				'prism_output': output,
				"mdp_dot": str(mdp_dot)
			}

		except Exception as e:
			raise HTTPException(status_code=500, detail=str(e))

		# except subprocess.CalledProcessError as e:
		#   print(f"Error running PRISM: {e}")
		#   print(f"PRISM output: {e.output}")

	uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
	run()