from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
import uvicorn
from cpi_to_spin.cpitospin import CPIToSPINConverter, create_cpi_visualization, create_spin_visualization


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
			print(cpi_dict)
			cpi_dot = create_cpi_visualization(cpi_dict)
			#cpi_dot = cpi_dict
			print(cpi_dot)
			#converter = CPIToSPINConverter()
			#spin_model = converter.convert_cpi_to_spin(cpi_dict)
			#spin_dot = create_spin_visualization(spin_model)

			#prism_model = spin_model.generate_prism_model()

		except Exception as e:
			raise HTTPException(status_code=400, detail=str(e))

		try:
			return { "cpi_dot": cpi_dot
					 #"spin_dot": spin_dot,
					 #"prism_model": prism_model
			}
		except Exception as e:
			raise HTTPException(status_code=500, detail=str(e))

	uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
	run()