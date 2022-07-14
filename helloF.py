from fastapi import FastAPI

app = FastAPI()

@app.get("/")
@app.get("/me")
async def root():
    return {"message": "Hello World"}


@app.get("/users/{_id}")
async def _user(_id: str):
    print(_id)
    return {"oh oh": _id}