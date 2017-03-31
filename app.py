import os
import sys
import json

import requests
from flask import Flask, request

import urllib
import numpy as np
import cv2
import sys

from googlenet import *

if sys.version_info[0] == 3:
    from urllib.request import urlopen
else:
    # Not Python 3 - today, it is most likely to be Python 2
    # But note that this might need an update when Python 4
    # might be around one day
    from urllib import urlopen


# METHOD #1: OpenCV, NumPy, and urllib
def url_to_image(url):
    # download the image, convert it to a NumPy array, and then read
    # it into OpenCV format
    resp = urlopen(url)
    image = np.asarray(bytearray(resp.read()), dtype="uint8")
    image = cv2.imdecode(image, cv2.IMREAD_COLOR)
 
    # return the image
    return image

def evaluateImg(image):
    width, height, _ = image.shape
    image = image.astype(np.float32)
    image_processed = process_image(cv2.resize(image,(224,224)))
    out = model.predict(image_processed)

    scores = out[0]
    weights = np.array([1,2,3,4,5,6,7,8,9,10])
    mean_score = (scores * weights).sum(axis=1)


    top_3_hits = np.argsort(out[1], axis=1)[0][::-1][:3]
    semantic_tags = [ semantics.ix[hit + 1].semantic[1:] for hit in top_3_hits]

    return mean_score, semantic_tags


model = create_googlenet('googlenet_aesthetics_weights_distribution_2016-12-06 23-04-37.h5')
semantics = pd.read_table('tags.txt',delimiter="(\d+)", usecols=[1,2], index_col=0, header=None,names=['index','semantic'])

app = Flask(__name__)


@app.route('/', methods=['GET'])
def verify():
    # when the endpoint is registered as a webhook, it must echo back
    # the 'hub.challenge' value it receives in the query arguments
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == os.environ["VERIFY_TOKEN"]:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200

    return "Hello world", 200

accepted_filetypes = ['.jpg','.png','.JPG','.JPEG', '.PNG','.bmp','.BMP']
@app.route('/', methods=['POST'])
def webhook():

    # endpoint for processing incoming messaging events

    data = request.get_json()
    log(data)  # you may not want to log every incoming message in production, but it's good for testing

    if data["object"] == "page":

        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:

                if messaging_event.get("message"):  # someone sent us a message

                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    # message_text = messaging_event["message"]["text"]  # the message's text
                    if "attachments" in messaging_event["message"]:
                        send_message(sender_id, "An image eh? I will be right on it, just give me a moment while i ...")

                        image_url = messaging_event["message"]["attachments"][0]["payload"]["url"]
                        if any(ext in image_url for ext in accepted_filetypes):
                            image = url_to_image(image_url)
                            score, semantic_tags = evaluateImg(image)
                            score = score + (score-5) * (2.5)

                            score = min(10, score)
                            score = max(0, score)


                            if score >= 10:
                                send_message(sender_id, "A perfect shot! Couldnt have done better myself, a perfect 10 out of 10!"%score )
                            if score >= 9:
                                send_message(sender_id, "Truly a remarkable capture, %.1f out of ten !"%score )
                            elif score >= 8:
                                send_message(sender_id, "What an amazing image, i have decided to rate it a %.1f"%score )
                            elif score >= 6:
                                send_message(sender_id, "A pretty good picture, i award it a %.1f"%score )
                            elif score >= 5:
                                send_message(sender_id, "A decent shot, i rate it %.1f out of 10"%score )
                            elif score >= 4:
                                send_message(sender_id, "A reasonable attempt, i give it a %.1f out of 10"%score )
                            elif score >= 3:
                                send_message(sender_id, "I must say, this is a pretty poor image, looks about a %.1f"%score )
                            elif score >= 2:
                                send_message(sender_id, "A poor effort, surely you can do better? %.1f"%score )
                            elif score >= 1:
                                send_message(sender_id, "This is frankly an embarrassing effort, %.1f !" %score)
                            else:
                                send_message(sender_id, "Truly awful, %.1f")

                            send_message(sender_id, "Possible semantic tags include: {}".format(", ".join(semantic_tags)) )
                        else:
                            send_message(sender_id, "That is not one of my accepted filetypes, sorry...")


                        ### Style detection
                        import requests
                        import json
                        headers = {"Content-Type": "application/json"}
                        data = {"urls":[image_url]}
                        url = "http://0.0.0.0:5005/classify"
                        r = requests.post(url, headers=headers, data=json.dumps(data))

                        if not (r.status_code == 404 or r.status_code == 500):
                            tags = ['Detailed',
                            'Pastel',
                            'Melancholy',
                            'Noir',
                            'HDR',
                            'Vintage',
                            'Long Exposure',
                            'Horror',
                            'Sunny',
                            'Bright',
                            'Hazy',
                            'Bokeh',
                            'Serene',
                            'Texture',
                            'Ethereal',
                            'Macro',
                            'Depth of Field',
                            'Geometric Composition',
                            'Minimal',
                            'Romantic']


                            prediction = json.loads(r.text)['predictions'][0]
                            predicted_tag = tags[prediction]

                            send_message(sender_id, "Detected style: {}".format(predicted_tag))

                    ## End of Style Detection

                    send_message(sender_id, "Have a nice day!")

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200


def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {
        "access_token": os.environ["PAGE_ACCESS_TOKEN"]
    }
    headers = {
        "Content-Type": "application/json"
    }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)


def log(message):  # simple wrapper for logging to stdout on heroku
    print(str(message))
    sys.stdout.flush()


if __name__ == '__main__':
    app.run(debug=False)


                    # sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    # recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    # if "text" in messaging_event["message"]:
                    #     message_text = messaging_event["message"]["text"]  # the message's text
                    #     send_message(sender_id, "got it ( a text ), thanks!")
                    # elif "attachments" in messaging_event["message"]:
                    #     image_url = messaging_event["message"]["attachments"][0]["payload"]["url"]
                    #     print(image_url)
                    # else:
                    #     send_message(sender_id, "got it ( unknown ), thanks!")