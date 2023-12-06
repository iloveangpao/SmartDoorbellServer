from flask import Flask, request, jsonify, render_template
from flask_mqtt import Mqtt
from flask_socketio import SocketIO, emit, send
from flask_cors import CORS
import ssl
import eventlet
import base64
import json
from email.mime.text import MIMEText
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from requests import HTTPError

eventlet.monkey_patch()
async_mode = None
app = Flask(__name__)
CORS(app)
 
import smtplib, ssl
import os

port = 465  # For SSL
smtp_server = os.environ.get("SMTP_SERVER")
sender_email = os.environ.get("SENDER_EMAIL")
receiver_email = os.environ.get("RECEIVER_EMAIL")
password = os.environ.get("EMAIL_PASSWORD")
context = ssl.create_default_context()

app.config['MQTT_TLS_VERSION'] = ssl.PROTOCOL_TLSv1_2
app.config['MQTT_BROKER_URL'] = os.environ.get("MQTT_BROKER_URL")
app.config['MQTT_BROKER_PORT'] = 8883
app.config['MQTT_USERNAME'] = os.environ.get("MQTT_USERNAME")
app.config['MQTT_PASSWORD'] = os.environ.get("MQTT_PASSWORD")
app.config['MQTT_KEEPALIVE'] = 5
app.config['MQTT_TLS_ENABLED'] = True
topic_reading = 'doorbell/reading'

mqtt_client = Mqtt(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=async_mode)

COMMANDMAP = {'lockCommand': 
{'delivery': 
{'topic' : 'doorbell/instruction', 'payload' : [0, 1]},
'visitor': {'topic' : 'doorbell/instruction', 'payload' : [1, 1]}},
'unlockCommand':
{'delivery': 
{'topic' : 'doorbell/instruction', 'payload' : [0, 0]},
'visitor': {'topic' : 'doorbell/instruction', 'payload' : [1, 0]}},
'bellCommand':
{'off': 
{'topic' : 'doorbell/instruction', 'payload' : [2, 0]}}
}

@mqtt_client.on_connect()
def handle_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected successfully')
        mqtt_client.subscribe(topic_reading)
    else:
        print('Bad connection. Code:', rc)

@mqtt_client.on_message()
def handle_mqtt_message(client, userdata, message):
    data = {
        'topic': message.topic,
        'payload': message.payload.decode()
    }
    print('Received message on topic: {topic} with payload: {payload}'.format(**data))
    
    # Emit notifications to web clients based on MQTT messages
    socketio.emit('mqtt_message', data=data)
    # socketio.send (message.payload.decode())

    # Send email notifications based on MQTT messages
    with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, data['payload'])
        print('done')

def send_email_notification(event):
    message = MIMEText(f'This is the body of the email for {event}')
    message['to'] = 'yanrui.lim@gmail.com'
    message['subject'] = f'Doorbell Alert: {event} detected'
    create_message = {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

    try:
        message = service.users().messages().send(userId="me", body=create_message).execute()
        print(f'Sent message to {message}. Message Id: {message["id"]}')
    except HTTPError as error:
        print(f'An error occurred: {error}')
        message = None

@socketio.event
def my_event(message):
    session['receive_count'] = session.get('receive_count', 0) + 1
    emit('my_response',
         {'data': message['data'], 'count': session['receive_count']})

# Receive the test request from client and send back a test response
@socketio.on('test_message')
def handle_message(data):
    print('received message: ' + str(data))
    emit('test_response', {'data': 'Test response sent'})

@socketio.on('connect')
def test_connect(auth):
    emit('my response', {'data': 'Connected'})

@app.route('/')
def index():
    return render_template('index.html', async_mode=socketio.async_mode)

@app.route('/publish', methods=['POST'])
def publish_message():
    request_data = request.get_json()
    print(request_data)
    cmd = request_data['command']
    cmdObject = request_data['msg']
    topic = COMMANDMAP[cmd][cmdObject]['topic']
    payload = bytearray(COMMANDMAP[cmd][cmdObject]['payload'])
    print(payload)
    print(topic)
    result = mqtt_client.publish(topic, payload)  # Publish to instructions topic
    return jsonify(result)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, use_reloader=False)


