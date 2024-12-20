import logging
from fastapi import FastAPI, Form, Request, status, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from azure.servicebus import ServiceBusClient, ServiceBusMessage
import os
from dotenv import load_dotenv

# load .env.local
load_dotenv(".env.local")

# Azure Service Bus connection details
CONNECTION_STR = os.getenv("SERVICE_BUS_CONNECTION_STRING")
QUEUE_NAME = os.getenv("SERVICE_BUS_QUEUE_NAME")

logging.basicConfig(
    level=logging.INFO,  # Set the logging level to DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("fastapi-requests")
app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log request details
    logger.info(f"Request made to: {request.method} {request.url}")
    logger.info(f"Headers: {request.headers}")
    body = await request.body()
    if body:
        logger.info(f"Request body: {body.decode('utf-8')}")
    else:
        logger.info("No request body.")

    # Process the request and get the response
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    print('Request for index page received')
    return templates.TemplateResponse('index.html', {"request": request})

@app.get('/favicon.ico')
async def favicon():
    file_name = 'favicon.ico'
    file_path = './static/' + file_name
    return FileResponse(path=file_path, headers={'mimetype': 'image/vnd.microsoft.icon'})

@app.post('/hello', response_class=HTMLResponse)
async def hello(request: Request, name: str = Form(...)):
    if name:
        print('Request for hello page received with name=%s' % name)
        return templates.TemplateResponse('hello.html', {"request": request, 'name':name})
    else:
        print('Request for hello page received with no name or blank name -- redirecting')
        return RedirectResponse(request.url_for("index"), status_code=status.HTTP_302_FOUND)

@app.post("/enqueue")
async def enqueue_message(message: dict):

    print("POST /enqueue/ called with:", message)  # Add debug log
    try:
        with ServiceBusClient.from_connection_string(CONNECTION_STR) as client:
            sender = client.get_queue_sender(queue_name=QUEUE_NAME)
            with sender:
                service_bus_message = ServiceBusMessage(str(message))
                sender.send_messages(service_bus_message)
        return {"message": "Message enqueued successfully!"}
    except Exception as e:
        print(f"Error in enqueue_message: {e}")  # Log any exception
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dequeue")
async def dequeue_message():
    try:
        with ServiceBusClient.from_connection_string(CONNECTION_STR) as client:
            receiver = client.get_queue_receiver(queue_name=QUEUE_NAME, max_wait_time=5)
            with receiver:
                # Fetch the latest message
                messages = receiver.receive_messages(max_message_count=1)
                if not messages:
                    return {"message": "No messages in the queue."}

                # Process and remove the message
                for message in messages:
                    content = str(message)
                    receiver.complete_message(message)  # Remove the message from the queue
                    return {"message": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/env")
async def get_env():
    return {
        "CONNECTION_STR": CONNECTION_STR,
        "QUEUE_NAME": QUEUE_NAME
    }

@app.post("/test")
async def test_post(message: dict):
    return {"message": "POST request received", "data": message}



if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)

