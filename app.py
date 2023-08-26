import base64
import io
import os
import pickle
import re

from bs4 import BeautifulSoup
from flask import Flask, render_template, send_file, request
from google_auth_oauthlib import flow
from apiclient import discovery
from datetime import datetime, timedelta

from oauth2client import file

app = Flask(__name__)

# Set up Gmail API and OAuth2 flow
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

store = file.Storage('storage.json')
creds = store.get()

if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)
        if creds and not creds.expired and creds.valid:
            GMAIL = discovery.build('gmail', 'v1', credentials=creds)
else:
    # Initiate OAuth2 flow
    flow = flow.InstalledAppFlow.from_client_secrets_file(
        'credentials.json',

        SCOPES,
        # redirect_uri='http://localhost:5000/'  # Use port 5000 for OAuth2 callback
    )
    creds = flow.run_local_server(port=0)
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    GMAIL = discovery.build('gmail', 'v1', credentials=creds)


@app.route('/', methods=['GET', 'POST'])
def index():
    user_id = 'me'
    message_body = ""
    message_body_base64 = ""
    plain_text_body = ""  # Initialize plain_text_body here
    if request.method == 'POST':
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        print("Start Date:", start_date)
        print("End Date:", end_date)

        # Getting all the messages from Inbox from the past 5 days
        msgs = GMAIL.users().messages().list(userId='me', q=f'after:{start_date} before:{end_date}').execute()

        mssg_list = msgs.get('messages', [])
        final_list = []

        for mssg in mssg_list:
            temp_dict = {}
            m_id = mssg['id']
            message = GMAIL.users().messages().get(userId=user_id, id=m_id).execute()
            payld = message['payload']
            headr = payld['headers']

            # Initialize message_body variables
            message_body = ""
            message_body_base64 = ""

            for one in headr:
                if one['name'] == 'Subject':
                    msg_subject = one['value']
                    temp_dict['Subject'] = msg_subject
                elif one['name'] == 'Date':
                    msg_date = one['value']
                    temp_dict['Date'] = msg_date
                elif one['name'] == 'From':
                    msg_from = one['value']
                    temp_dict['Sender'] = msg_from

            temp_dict['Snippet'] = message['snippet']

            # Get the message body
            payload = message['payload']
            parts = payload.get('parts')
            attachments = []  # Create a list to store attachment information

            if parts:
                for part in parts:
                    if 'filename' in part:
                        attachment = {'filename': part['filename']}
                        if 'body' in part:
                            if 'attachmentId' in part['body']:
                                attachment_id = part['body']['attachmentId']
                                attachment_url = f'https://www.googleapis.com/gmail/v1/users/me/messages/{m_id}/attachments/{attachment_id}?alt=media'
                                attachment['url'] = attachment_url
                            elif 'data' in part['body']:
                                if 'data' in part['body']:
                                    # message_body_base64 = part['body']['data']
                                    # message_body = base64.urlsafe_b64decode(message_body_base64).decode('utf-8')
                                    message_body_base64 = part['body']['data']
                                    message_body = base64.urlsafe_b64decode(message_body_base64).decode('utf-8')
                                    # Use BeautifulSoup to parse HTML and extract plain text
                                    soup = BeautifulSoup(message_body, 'html.parser')
                                    plain_text_body = soup.get_text()
                                    # Remove extra whitespace and line breaks
                                    plain_text_body = re.sub(r'\s+', ' ', plain_text_body).strip()

                            attachments.append(attachment)
            temp_dict['Message_Body'] = plain_text_body
            temp_dict['Message_Body_Base64'] = message_body_base64
            final_list.append({'email': temp_dict, 'attachments': attachments})
        # print("Filtered Emails:", final_list)
        return render_template('index.html', email_details=final_list)
    else:
        return render_template('index.html', email_details=[])


@app.route('/attachment/<message_id>/<attachment_id>')
def attachment(message_id, attachment_id):
    attachment_data = GMAIL.users().messages().attachments().get(userId='me', messageId=message_id,
                                                                 id=attachment_id).execute()
    data = base64.urlsafe_b64decode(attachment_data['data'])
    return send_file(io.BytesIO(data), as_attachment=True, attachment_filename=attachment_data['filename'])


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
